"""Tests for SpacingEditor integration with metrics rules."""

import pytest

from tests.mocks import MockFont
from ufo_spacing_lib.commands.rules import (
    RemoveMetricsRuleCommand,
    SetMetricsRuleCommand,
)
from ufo_spacing_lib.contexts import FontContext
from ufo_spacing_lib.editors.spacing import SpacingEditor


class TestSpacingEditorInitialization:
    """Test SpacingEditor initialization with fonts."""

    def test_single_font(self):
        font = MockFont(["A", "B"])
        editor = SpacingEditor(font)

        assert editor.font is font
        assert editor.fonts == [font]
        assert len(editor._rules_managers) == 1

    def test_multiple_fonts(self):
        font1 = MockFont(["A"])
        font2 = MockFont(["A"])
        editor = SpacingEditor([font1, font2])

        assert editor.font is font1  # Primary is first
        assert editor.fonts == [font1, font2]
        assert len(editor._rules_managers) == 2

    def test_with_scales(self):
        font1 = MockFont(["A"])
        font2 = MockFont(["A"])
        editor = SpacingEditor(
            [font1, font2],
            scales={font1: 1.0, font2: 1.2},
        )

        assert editor._context.get_scale(font1) == 1.0
        assert editor._context.get_scale(font2) == 1.2

    def test_with_primary_font(self):
        font1 = MockFont(["A"])
        font2 = MockFont(["A"])
        editor = SpacingEditor([font1, font2], primary_font=font2)

        assert editor.font is font2

    def test_legacy_mode_no_fonts(self):
        editor = SpacingEditor()

        assert editor.font is None
        assert editor.fonts == []
        assert len(editor._rules_managers) == 0

    def test_repr(self):
        font = MockFont(["A"])
        editor = SpacingEditor(font)
        assert "fonts=1" in repr(editor)


class TestSpacingEditorActiveFonts:
    """Test active_fonts functionality."""

    def setup_method(self):
        self.font1 = MockFont(["A"])
        self.font2 = MockFont(["A"])
        self.editor = SpacingEditor([self.font1, self.font2])

    def test_active_fonts_default_all(self):
        assert self.editor.active_fonts == [self.font1, self.font2]

    def test_set_active_fonts_list(self):
        self.editor.set_active_fonts([self.font2])
        assert self.editor.active_fonts == [self.font2]

    def test_set_active_fonts_single(self):
        self.editor.set_active_fonts(self.font1)
        assert self.editor.active_fonts == [self.font1]

    def test_set_active_fonts_none_resets(self):
        self.editor.set_active_fonts([self.font2])
        self.editor.set_active_fonts(None)
        assert self.editor.active_fonts == [self.font1, self.font2]


class TestSpacingEditorRulesManager:
    """Test rules manager access."""

    def setup_method(self):
        self.font = MockFont(["A", "Aacute"])
        self.editor = SpacingEditor(self.font)

    def test_get_rules_manager_default(self):
        manager = self.editor.get_rules_manager()
        assert manager.font is self.font

    def test_get_rules_manager_specific_font(self):
        font2 = MockFont(["B"])
        editor = SpacingEditor([self.font, font2])

        manager = editor.get_rules_manager(font2)
        assert manager.font is font2

    def test_get_rules_manager_not_found(self):
        other_font = MockFont(["X"])
        with pytest.raises(KeyError):
            self.editor.get_rules_manager(other_font)

    def test_get_rules_manager_no_fonts_error(self):
        editor = SpacingEditor()
        with pytest.raises(ValueError):
            editor.get_rules_manager()


class TestSpacingEditorRuleCommands:
    """Test executing rule commands through SpacingEditor."""

    def setup_method(self):
        self.font = MockFont(["A", "Aacute", "Agrave"])
        self.editor = SpacingEditor(self.font)

    def test_execute_set_rule(self):
        cmd = SetMetricsRuleCommand("Aacute", "left", "=A")
        result = self.editor.execute(cmd)

        assert result.success
        manager = self.editor.get_rules_manager()
        assert manager.get_rule("Aacute", "left") == "=A"

    def test_execute_remove_rule(self):
        # First set a rule
        self.editor.execute(SetMetricsRuleCommand("Aacute", "left", "=A"))

        # Then remove it
        cmd = RemoveMetricsRuleCommand("Aacute", "left")
        result = self.editor.execute(cmd)

        assert result.success
        manager = self.editor.get_rules_manager()
        assert manager.get_rule("Aacute", "left") is None

    def test_undo_set_rule(self):
        cmd = SetMetricsRuleCommand("Aacute", "left", "=A")
        self.editor.execute(cmd)
        self.editor.undo()

        manager = self.editor.get_rules_manager()
        assert manager.get_rule("Aacute", "left") is None

    def test_redo_set_rule(self):
        cmd = SetMetricsRuleCommand("Aacute", "left", "=A")
        self.editor.execute(cmd)
        self.editor.undo()
        self.editor.redo()

        manager = self.editor.get_rules_manager()
        assert manager.get_rule("Aacute", "left") == "=A"

    def test_undo_remove_rule(self):
        # Set a rule
        self.editor.execute(SetMetricsRuleCommand("Aacute", "left", "=A"))
        self.editor.clear_history()

        # Remove it
        cmd = RemoveMetricsRuleCommand("Aacute", "left")
        self.editor.execute(cmd)
        self.editor.undo()

        manager = self.editor.get_rules_manager()
        assert manager.get_rule("Aacute", "left") == "=A"

    def test_history_tracking(self):
        self.editor.execute(SetMetricsRuleCommand("Aacute", "left", "=A"))
        self.editor.execute(SetMetricsRuleCommand("Agrave", "left", "=A"))

        assert self.editor.history_count == 2
        assert self.editor.can_undo

        history = self.editor.get_history()
        assert len(history) == 2
        assert "Aacute" in history[0]
        assert "Agrave" in history[1]


class TestSpacingEditorRuleCommandsMultiFont:
    """Test rule commands with multiple fonts."""

    def setup_method(self):
        self.font1 = MockFont(["A", "Aacute"])
        self.font2 = MockFont(["A", "Aacute"])
        self.editor = SpacingEditor([self.font1, self.font2])

    def test_set_rule_applies_to_all_fonts(self):
        cmd = SetMetricsRuleCommand("Aacute", "left", "=A")
        self.editor.execute(cmd)

        manager1 = self.editor.get_rules_manager(self.font1)
        manager2 = self.editor.get_rules_manager(self.font2)

        assert manager1.get_rule("Aacute", "left") == "=A"
        assert manager2.get_rule("Aacute", "left") == "=A"

    def test_set_rule_with_font_override(self):
        cmd = SetMetricsRuleCommand("Aacute", "left", "=A")
        self.editor.execute(cmd, font=self.font2)

        manager1 = self.editor.get_rules_manager(self.font1)
        manager2 = self.editor.get_rules_manager(self.font2)

        assert manager1.get_rule("Aacute", "left") is None
        assert manager2.get_rule("Aacute", "left") == "=A"

    def test_undo_multi_font_preserves_individual_state(self):
        # Set different rules for each font
        manager1 = self.editor.get_rules_manager(self.font1)
        manager2 = self.editor.get_rules_manager(self.font2)
        manager1.set_rule("Aacute", "left", "=A")
        manager2.set_rule("Aacute", "left", "=A+10")

        # Execute command that affects both
        cmd = SetMetricsRuleCommand("Aacute", "left", "=H")
        self.editor.execute(cmd)

        # Undo
        self.editor.undo()

        # Each font should have its original rule
        assert manager1.get_rule("Aacute", "left") == "=A"
        assert manager2.get_rule("Aacute", "left") == "=A+10"


class TestSpacingEditorCallbacks:
    """Test callbacks with rule commands."""

    def setup_method(self):
        self.font = MockFont(["A", "Aacute"])
        self.editor = SpacingEditor(self.font)
        self.callback_calls = []

    def test_on_change_callback(self):
        def on_change(cmd, result):
            self.callback_calls.append(("change", cmd, result))

        self.editor.on_change = on_change
        cmd = SetMetricsRuleCommand("Aacute", "left", "=A")
        self.editor.execute(cmd)

        assert len(self.callback_calls) == 1
        assert self.callback_calls[0][0] == "change"
        assert self.callback_calls[0][1] is cmd

    def test_on_undo_callback(self):
        def on_undo(cmd, result):
            self.callback_calls.append(("undo", cmd, result))

        self.editor.on_undo = on_undo
        cmd = SetMetricsRuleCommand("Aacute", "left", "=A")
        self.editor.execute(cmd)
        self.editor.undo()

        assert len(self.callback_calls) == 1
        assert self.callback_calls[0][0] == "undo"

    def test_on_redo_callback(self):
        def on_redo(cmd, result):
            self.callback_calls.append(("redo", cmd, result))

        self.editor.on_redo = on_redo
        cmd = SetMetricsRuleCommand("Aacute", "left", "=A")
        self.editor.execute(cmd)
        self.editor.undo()
        self.editor.redo()

        assert len(self.callback_calls) == 1
        assert self.callback_calls[0][0] == "redo"


class TestSpacingEditorLegacyMode:
    """Test backward compatibility with legacy API."""

    def test_execute_with_context(self):
        font = MockFont(["A", "Aacute"])
        editor = SpacingEditor()  # No fonts
        context = FontContext.from_single_font(font)

        # This should fail because editor has no rules managers for this font
        cmd = SetMetricsRuleCommand("Aacute", "left", "=A")
        result = editor.execute(cmd, context)

        # The command should not find a rules manager
        assert result.success  # Command executes but does nothing

    def test_execute_without_fonts_raises(self):
        editor = SpacingEditor()

        cmd = SetMetricsRuleCommand("Aacute", "left", "=A")
        with pytest.raises(ValueError, match="No fonts configured"):
            editor.execute(cmd)


class TestSpacingEditorValidation:
    """Test validation through SpacingEditor."""

    def setup_method(self):
        self.font = MockFont(["A", "Aacute", "B"])
        self.editor = SpacingEditor(self.font)

    def test_validate_rules(self):
        manager = self.editor.get_rules_manager()
        manager.set_rule("Aacute", "left", "=A")

        report = manager.validate()
        assert report.is_valid

    def test_validate_detects_cycle(self):
        manager = self.editor.get_rules_manager()
        manager.set_rule("A", "left", "=B")
        manager.set_rule("B", "left", "=A")

        report = manager.validate()
        assert not report.is_valid
        cycle_errors = report.get_issues_by_code("E02")
        assert len(cycle_errors) >= 1
