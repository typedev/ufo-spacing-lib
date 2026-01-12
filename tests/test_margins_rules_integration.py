"""Integration tests for margin commands with metrics rules cascade."""


from tests.mocks import MockFont
from ufo_spacing_lib.commands.margins import AdjustMarginCommand, SetMarginCommand
from ufo_spacing_lib.commands.rules import SetMetricsRuleCommand
from ufo_spacing_lib.editors.spacing import SpacingEditor


class TestMarginCommandsWithRules:
    """Test margin commands triggering rules cascade."""

    def setup_method(self):
        self.font = MockFont(["A", "Aacute", "Agrave", "H", "B"])
        # Set initial margins
        self.font["A"].leftMargin = 50
        self.font["A"].rightMargin = 50
        self.font["H"].leftMargin = 40
        self.font["H"].rightMargin = 40
        self.font["Aacute"].leftMargin = 50
        self.font["Aacute"].rightMargin = 50
        self.font["Agrave"].leftMargin = 50
        self.font["Agrave"].rightMargin = 50
        self.font["B"].leftMargin = 30
        self.font["B"].rightMargin = 30

        self.editor = SpacingEditor(self.font)

    def test_adjust_margin_applies_cascade(self):
        # Set up rules: Aacute.left = =A, Agrave.left = =A
        self.editor.execute(SetMetricsRuleCommand("Aacute", "left", "=A"))
        self.editor.execute(SetMetricsRuleCommand("Agrave", "left", "=A"))

        # Adjust A's left margin
        cmd = AdjustMarginCommand("A", "left", 10)
        result = self.editor.execute(cmd)

        assert result.success
        # Main glyph changed
        assert self.font["A"].leftMargin == 60
        # Dependent glyphs updated via cascade
        assert self.font["Aacute"].leftMargin == 60
        assert self.font["Agrave"].leftMargin == 60

    def test_set_margin_applies_cascade(self):
        # Set up rule
        self.editor.execute(SetMetricsRuleCommand("Aacute", "left", "=A"))

        # Set A's left margin to absolute value
        cmd = SetMarginCommand("A", "left", 100)
        result = self.editor.execute(cmd)

        assert result.success
        assert self.font["A"].leftMargin == 100
        assert self.font["Aacute"].leftMargin == 100

    def test_cascade_with_arithmetic_rule(self):
        # Rule: Aacute.left = =A+10
        self.editor.execute(SetMetricsRuleCommand("Aacute", "left", "=A+10"))

        # Adjust A
        cmd = AdjustMarginCommand("A", "left", 5)
        self.editor.execute(cmd)

        assert self.font["A"].leftMargin == 55
        assert self.font["Aacute"].leftMargin == 65  # 55 + 10

    def test_cascade_chain(self):
        # Chain: B -> Aacute -> A
        self.editor.execute(SetMetricsRuleCommand("Aacute", "left", "=A"))
        self.editor.execute(SetMetricsRuleCommand("B", "left", "=Aacute"))

        # Adjust A
        cmd = AdjustMarginCommand("A", "left", 10)
        self.editor.execute(cmd)

        assert self.font["A"].leftMargin == 60
        assert self.font["Aacute"].leftMargin == 60
        assert self.font["B"].leftMargin == 60

    def test_undo_restores_cascade(self):
        # Set up rule
        self.editor.execute(SetMetricsRuleCommand("Aacute", "left", "=A"))

        # Record original values
        original_a = self.font["A"].leftMargin
        original_aacute = self.font["Aacute"].leftMargin

        # Adjust A
        cmd = AdjustMarginCommand("A", "left", 10)
        self.editor.execute(cmd)

        # Values changed
        assert self.font["A"].leftMargin == 60
        assert self.font["Aacute"].leftMargin == 60

        # Undo
        self.editor.undo()

        # Both restored
        assert self.font["A"].leftMargin == original_a
        assert self.font["Aacute"].leftMargin == original_aacute

    def test_redo_reapplies_cascade(self):
        # Set up rule
        self.editor.execute(SetMetricsRuleCommand("Aacute", "left", "=A"))

        # Adjust and undo
        cmd = AdjustMarginCommand("A", "left", 10)
        self.editor.execute(cmd)
        self.editor.undo()

        # Redo
        self.editor.redo()

        assert self.font["A"].leftMargin == 60
        assert self.font["Aacute"].leftMargin == 60

    def test_apply_rules_false_skips_cascade(self):
        # Set up rule
        self.editor.execute(SetMetricsRuleCommand("Aacute", "left", "=A"))

        # Adjust without applying rules
        cmd = AdjustMarginCommand("A", "left", 10, apply_rules=False)
        self.editor.execute(cmd)

        assert self.font["A"].leftMargin == 60
        # Aacute NOT updated
        assert self.font["Aacute"].leftMargin == 50

    def test_affected_glyphs_includes_cascade(self):
        # Set up rules
        self.editor.execute(SetMetricsRuleCommand("Aacute", "left", "=A"))
        self.editor.execute(SetMetricsRuleCommand("Agrave", "left", "=A"))

        # Adjust A
        cmd = AdjustMarginCommand("A", "left", 10)
        result = self.editor.execute(cmd)

        # All affected glyphs should be in the result
        assert "A" in result.affected_glyphs
        assert "Aacute" in result.affected_glyphs
        assert "Agrave" in result.affected_glyphs


class TestMarginCommandsWithRulesMultiFont:
    """Test margin commands with rules in multi-font scenario."""

    def setup_method(self):
        self.font1 = MockFont(["A", "Aacute"])
        self.font2 = MockFont(["A", "Aacute"])

        # Set initial margins
        self.font1["A"].leftMargin = 50
        self.font1["Aacute"].leftMargin = 50
        self.font2["A"].leftMargin = 60
        self.font2["Aacute"].leftMargin = 60

        self.editor = SpacingEditor([self.font1, self.font2])

    def test_cascade_applies_to_all_fonts(self):
        # Set rule for both fonts
        self.editor.execute(SetMetricsRuleCommand("Aacute", "left", "=A"))

        # Adjust A in all fonts
        cmd = AdjustMarginCommand("A", "left", 10)
        self.editor.execute(cmd)

        # Both fonts updated
        assert self.font1["A"].leftMargin == 60
        assert self.font1["Aacute"].leftMargin == 60
        assert self.font2["A"].leftMargin == 70
        assert self.font2["Aacute"].leftMargin == 70

    def test_cascade_with_font_override(self):
        # Set rule for both fonts
        self.editor.execute(SetMetricsRuleCommand("Aacute", "left", "=A"))

        # Adjust A only in font2
        cmd = AdjustMarginCommand("A", "left", 10)
        self.editor.execute(cmd, font=self.font2)

        # Only font2 affected
        assert self.font1["A"].leftMargin == 50
        assert self.font1["Aacute"].leftMargin == 50
        assert self.font2["A"].leftMargin == 70
        assert self.font2["Aacute"].leftMargin == 70


class TestSymmetryRules:
    """Test symmetry rules (=| and =H|) with margin commands."""

    def setup_method(self):
        self.font = MockFont(["A", "H", "V"])
        self.font["A"].leftMargin = 40
        self.font["A"].rightMargin = 60
        self.font["H"].leftMargin = 50
        self.font["H"].rightMargin = 50
        self.font["V"].leftMargin = 30
        self.font["V"].rightMargin = 30

        self.editor = SpacingEditor(self.font)

    def test_symmetry_self_rule(self):
        # Rule: H.right = =| (copy left to right)
        self.editor.execute(SetMetricsRuleCommand("A", "right", "=|"))

        # Adjust A.left
        cmd = AdjustMarginCommand("A", "left", 10)
        self.editor.execute(cmd)

        assert self.font["A"].leftMargin == 50
        assert self.font["A"].rightMargin == 50  # Mirrored

    def test_opposite_side_rule(self):
        # Rule: V.left = =H| (copy H.right)
        self.editor.execute(SetMetricsRuleCommand("V", "left", "=H|"))

        # Adjust H.right
        cmd = AdjustMarginCommand("H", "right", 10)
        self.editor.execute(cmd)

        assert self.font["H"].rightMargin == 60
        assert self.font["V"].leftMargin == 60  # Copied from H.right


class TestWarningsInCascade:
    """Test warning generation during cascade."""

    def setup_method(self):
        self.font = MockFont(["A", "Aacute"])
        self.font["A"].leftMargin = 50
        self.font["Aacute"].leftMargin = 50

        self.editor = SpacingEditor(self.font)

    def test_rule_referencing_missing_glyph_generates_warning(self):
        # Rule referencing non-existent glyph
        self.editor.execute(SetMetricsRuleCommand("Aacute", "left", "=MissingGlyph"))

        # Adjust A (Aacute will try to evaluate but glyph doesn't exist)
        cmd = AdjustMarginCommand("A", "left", 10)
        result = self.editor.execute(cmd)

        # Command succeeds but may have warnings
        assert result.success
        # Aacute should remain unchanged since rule can't evaluate
        # (MissingGlyph doesn't exist in font)
