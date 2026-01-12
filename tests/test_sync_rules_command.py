"""Tests for SyncRulesCommand."""

from tests.mocks import MockFont
from ufo_spacing_lib.commands.margins import AdjustMarginCommand
from ufo_spacing_lib.commands.rules import SetMetricsRuleCommand, SyncRulesCommand
from ufo_spacing_lib.editors.spacing import SpacingEditor


class TestSyncRulesCommand:
    """Test SyncRulesCommand for batch rule synchronization."""

    def setup_method(self):
        self.font = MockFont(["A", "Aacute", "Agrave", "H", "B"])
        # Set initial margins
        self.font["A"].leftMargin = 50
        self.font["A"].rightMargin = 50
        self.font["Aacute"].leftMargin = 50
        self.font["Aacute"].rightMargin = 50
        self.font["Agrave"].leftMargin = 50
        self.font["Agrave"].rightMargin = 50
        self.font["H"].leftMargin = 40
        self.font["H"].rightMargin = 40
        self.font["B"].leftMargin = 30
        self.font["B"].rightMargin = 30

        self.editor = SpacingEditor(self.font)

    def test_sync_after_deferred_changes(self):
        """Test syncing rules after making changes with apply_rules=False."""
        # Set up rules
        self.editor.execute(SetMetricsRuleCommand("Aacute", "left", "=A"))
        self.editor.execute(SetMetricsRuleCommand("Agrave", "left", "=A"))

        # Make changes without triggering rules
        cmd = AdjustMarginCommand("A", "left", 20, apply_rules=False)
        self.editor.execute(cmd)

        # A changed but dependents not yet
        assert self.font["A"].leftMargin == 70
        assert self.font["Aacute"].leftMargin == 50  # Still old value
        assert self.font["Agrave"].leftMargin == 50  # Still old value

        # Now sync
        result = self.editor.execute(SyncRulesCommand(["A"]))

        assert result.success
        assert self.font["Aacute"].leftMargin == 70
        assert self.font["Agrave"].leftMargin == 70

    def test_sync_all_rules(self):
        """Test syncing all rules without specifying source glyphs."""
        # Set up rules
        self.editor.execute(SetMetricsRuleCommand("Aacute", "left", "=A"))
        self.editor.execute(SetMetricsRuleCommand("B", "left", "=H"))

        # Make changes without triggering rules
        self.editor.execute(AdjustMarginCommand("A", "left", 10, apply_rules=False))
        self.editor.execute(AdjustMarginCommand("H", "left", 10, apply_rules=False))

        # Sync all
        result = self.editor.execute(SyncRulesCommand())

        assert result.success
        assert self.font["Aacute"].leftMargin == 60  # A is now 60
        assert self.font["B"].leftMargin == 50  # H is now 50

    def test_sync_with_arithmetic_rules(self):
        """Test syncing rules with arithmetic operations."""
        self.editor.execute(SetMetricsRuleCommand("Aacute", "left", "=A+10"))

        # Change A without cascade
        self.editor.execute(AdjustMarginCommand("A", "left", 20, apply_rules=False))

        # A is 70, Aacute should be 50 still
        assert self.font["A"].leftMargin == 70
        assert self.font["Aacute"].leftMargin == 50

        # Sync
        self.editor.execute(SyncRulesCommand(["A"]))

        # Aacute should be 70 + 10 = 80
        assert self.font["Aacute"].leftMargin == 80

    def test_sync_chain(self):
        """Test syncing a chain of rules."""
        # Chain: A -> Aacute -> Agrave
        self.editor.execute(SetMetricsRuleCommand("Aacute", "left", "=A"))
        self.editor.execute(SetMetricsRuleCommand("Agrave", "left", "=Aacute"))

        # Change A
        self.editor.execute(AdjustMarginCommand("A", "left", 20, apply_rules=False))

        # Nothing synced yet
        assert self.font["Aacute"].leftMargin == 50
        assert self.font["Agrave"].leftMargin == 50

        # Sync - should handle chain correctly
        result = self.editor.execute(SyncRulesCommand(["A"]))

        assert result.success
        assert self.font["Aacute"].leftMargin == 70
        assert self.font["Agrave"].leftMargin == 70

    def test_sync_undo(self):
        """Test undo of sync command."""
        self.editor.execute(SetMetricsRuleCommand("Aacute", "left", "=A"))

        # Original values
        original_aacute = self.font["Aacute"].leftMargin

        # Change A and sync
        self.editor.execute(AdjustMarginCommand("A", "left", 20, apply_rules=False))
        self.editor.execute(SyncRulesCommand(["A"]))

        # Aacute changed
        assert self.font["Aacute"].leftMargin == 70

        # Undo sync
        self.editor.undo()

        # Aacute restored
        assert self.font["Aacute"].leftMargin == original_aacute

    def test_sync_redo(self):
        """Test redo of sync command."""
        self.editor.execute(SetMetricsRuleCommand("Aacute", "left", "=A"))

        # Change A and sync
        self.editor.execute(AdjustMarginCommand("A", "left", 20, apply_rules=False))
        self.editor.execute(SyncRulesCommand(["A"]))

        # Undo and redo
        self.editor.undo()
        self.editor.redo()

        assert self.font["Aacute"].leftMargin == 70

    def test_sync_no_changes_needed(self):
        """Test sync when values are already correct."""
        self.editor.execute(SetMetricsRuleCommand("Aacute", "left", "=A"))

        # Values already match, sync should report no changes
        result = self.editor.execute(SyncRulesCommand(["A"]))

        assert result.success
        assert "No changes" in result.message

    def test_sync_affected_glyphs_in_result(self):
        """Test that affected glyphs are returned in result."""
        self.editor.execute(SetMetricsRuleCommand("Aacute", "left", "=A"))
        self.editor.execute(SetMetricsRuleCommand("Agrave", "left", "=A"))

        self.editor.execute(AdjustMarginCommand("A", "left", 20, apply_rules=False))
        result = self.editor.execute(SyncRulesCommand(["A"]))

        assert "Aacute" in result.affected_glyphs
        assert "Agrave" in result.affected_glyphs


class TestSyncRulesPerformance:
    """Test performance benefits of batch sync."""

    def setup_method(self):
        # Create font with many glyphs
        glyph_names = ["A", "H"] + [f"Glyph{i}" for i in range(100)]
        self.font = MockFont(glyph_names)

        for name in glyph_names:
            self.font[name].leftMargin = 50
            self.font[name].rightMargin = 50

        self.editor = SpacingEditor(self.font)

    def test_batch_sync_vs_individual_cascade(self):
        """Verify batch sync works correctly with many glyphs."""
        # Set up rules: all Glyph* depend on A
        for i in range(100):
            self.editor.execute(
                SetMetricsRuleCommand(f"Glyph{i}", "left", "=A")
            )

        # Change A without cascade
        self.editor.execute(AdjustMarginCommand("A", "left", 10, apply_rules=False))

        # All glyphs should still be 50
        for i in range(100):
            assert self.font[f"Glyph{i}"].leftMargin == 50

        # Single sync operation
        result = self.editor.execute(SyncRulesCommand(["A"]))

        # All should now be 60
        for i in range(100):
            assert self.font[f"Glyph{i}"].leftMargin == 60

        assert len(result.affected_glyphs) == 100
