"""Tests for rule commands."""


from tests.mocks import MockFont
from ufo_spacing_lib.commands.rules import (
    RemoveMetricsRuleCommand,
    SetMetricsRuleCommand,
)
from ufo_spacing_lib.contexts import FontContext
from ufo_spacing_lib.rules_manager import MetricsRulesManager


class TestSetMetricsRuleCommand:
    """Test SetMetricsRuleCommand."""

    def setup_method(self):
        self.font = MockFont(["A", "Aacute", "Agrave"])
        self.context = FontContext.from_single_font(self.font)
        self.manager = MetricsRulesManager(self.font)
        self.managers = {id(self.font): self.manager}

    def test_set_rule_left(self):
        cmd = SetMetricsRuleCommand("Aacute", "left", "=A")
        result = cmd.execute(self.context, self.managers)

        assert result.success
        assert self.manager.get_rule("Aacute", "left") == "=A"
        assert self.manager.get_rule("Aacute", "right") is None

    def test_set_rule_right(self):
        cmd = SetMetricsRuleCommand("Aacute", "right", "=A+5")
        result = cmd.execute(self.context, self.managers)

        assert result.success
        assert self.manager.get_rule("Aacute", "right") == "=A+5"

    def test_set_rule_both(self):
        cmd = SetMetricsRuleCommand("Aacute", "both", "=A")
        result = cmd.execute(self.context, self.managers)

        assert result.success
        assert self.manager.get_rule("Aacute", "left") == "=A"
        assert self.manager.get_rule("Aacute", "right") == "=A"

    def test_set_rule_invalid_syntax(self):
        cmd = SetMetricsRuleCommand("Aacute", "left", "invalid")
        result = cmd.execute(self.context, self.managers)

        assert not result.success
        assert "Invalid" in result.message

    def test_set_rule_overwrites(self):
        self.manager.set_rule("Aacute", "left", "=A")

        cmd = SetMetricsRuleCommand("Aacute", "left", "=A+10")
        result = cmd.execute(self.context, self.managers)

        assert result.success
        assert self.manager.get_rule("Aacute", "left") == "=A+10"

    def test_undo_restores_no_rule(self):
        cmd = SetMetricsRuleCommand("Aacute", "left", "=A")
        cmd.execute(self.context, self.managers)

        cmd.undo(self.context, self.managers)

        assert self.manager.get_rule("Aacute", "left") is None

    def test_undo_restores_previous_rule(self):
        self.manager.set_rule("Aacute", "left", "=A")
        self.manager.set_rule("Aacute", "right", "=A+5")

        cmd = SetMetricsRuleCommand("Aacute", "both", "=H")
        cmd.execute(self.context, self.managers)

        assert self.manager.get_rule("Aacute", "left") == "=H"
        assert self.manager.get_rule("Aacute", "right") == "=H"

        cmd.undo(self.context, self.managers)

        assert self.manager.get_rule("Aacute", "left") == "=A"
        assert self.manager.get_rule("Aacute", "right") == "=A+5"

    def test_description(self):
        cmd = SetMetricsRuleCommand("Aacute", "left", "=A")
        assert "Aacute" in cmd.description
        assert "left" in cmd.description
        assert "=A" in cmd.description

        cmd = SetMetricsRuleCommand("Aacute", "both", "=A")
        assert "both" not in cmd.description  # "both" is not in description

    def test_no_managers_error(self):
        cmd = SetMetricsRuleCommand("Aacute", "left", "=A")
        result = cmd.execute(self.context, None)
        assert not result.success


class TestRemoveMetricsRuleCommand:
    """Test RemoveMetricsRuleCommand."""

    def setup_method(self):
        self.font = MockFont(["A", "Aacute"])
        self.context = FontContext.from_single_font(self.font)
        self.manager = MetricsRulesManager(self.font)
        self.managers = {id(self.font): self.manager}
        # Set up initial rules
        self.manager.set_rule("Aacute", "left", "=A")
        self.manager.set_rule("Aacute", "right", "=A+5")

    def test_remove_rule_left(self):
        cmd = RemoveMetricsRuleCommand("Aacute", "left")
        result = cmd.execute(self.context, self.managers)

        assert result.success
        assert self.manager.get_rule("Aacute", "left") is None
        assert self.manager.get_rule("Aacute", "right") == "=A+5"

    def test_remove_rule_right(self):
        cmd = RemoveMetricsRuleCommand("Aacute", "right")
        result = cmd.execute(self.context, self.managers)

        assert result.success
        assert self.manager.get_rule("Aacute", "left") == "=A"
        assert self.manager.get_rule("Aacute", "right") is None

    def test_remove_rule_both(self):
        cmd = RemoveMetricsRuleCommand("Aacute", "both")
        result = cmd.execute(self.context, self.managers)

        assert result.success
        assert self.manager.get_rules_for_glyph("Aacute") is None

    def test_remove_nonexistent_rule(self):
        cmd = RemoveMetricsRuleCommand("Agrave", "left")
        result = cmd.execute(self.context, self.managers)

        # Should succeed even if no rule exists
        assert result.success

    def test_undo_restores_rule(self):
        cmd = RemoveMetricsRuleCommand("Aacute", "left")
        cmd.execute(self.context, self.managers)

        cmd.undo(self.context, self.managers)

        assert self.manager.get_rule("Aacute", "left") == "=A"

    def test_undo_restores_both_rules(self):
        cmd = RemoveMetricsRuleCommand("Aacute", "both")
        cmd.execute(self.context, self.managers)

        cmd.undo(self.context, self.managers)

        assert self.manager.get_rule("Aacute", "left") == "=A"
        assert self.manager.get_rule("Aacute", "right") == "=A+5"

    def test_description(self):
        cmd = RemoveMetricsRuleCommand("Aacute", "left")
        assert "Aacute" in cmd.description
        assert "left" in cmd.description

        cmd = RemoveMetricsRuleCommand("Aacute", "both")
        assert "Aacute" in cmd.description

    def test_no_managers_error(self):
        cmd = RemoveMetricsRuleCommand("Aacute", "left")
        result = cmd.execute(self.context, None)
        assert not result.success


class TestRuleCommandsMultiFont:
    """Test rule commands with multiple fonts."""

    def setup_method(self):
        self.font1 = MockFont(["A", "Aacute"])
        self.font2 = MockFont(["A", "Aacute"])
        self.context = FontContext.from_linked_fonts([self.font1, self.font2])
        self.manager1 = MetricsRulesManager(self.font1)
        self.manager2 = MetricsRulesManager(self.font2)
        self.managers = {
            id(self.font1): self.manager1,
            id(self.font2): self.manager2,
        }

    def test_set_rule_multi_font(self):
        cmd = SetMetricsRuleCommand("Aacute", "left", "=A")
        result = cmd.execute(self.context, self.managers)

        assert result.success
        assert self.manager1.get_rule("Aacute", "left") == "=A"
        assert self.manager2.get_rule("Aacute", "left") == "=A"

    def test_undo_multi_font(self):
        # Set different initial rules for each font
        self.manager1.set_rule("Aacute", "left", "=A")
        self.manager2.set_rule("Aacute", "left", "=A+10")

        cmd = SetMetricsRuleCommand("Aacute", "left", "=H")
        cmd.execute(self.context, self.managers)

        cmd.undo(self.context, self.managers)

        # Each font should have its original rule restored
        assert self.manager1.get_rule("Aacute", "left") == "=A"
        assert self.manager2.get_rule("Aacute", "left") == "=A+10"

    def test_remove_rule_multi_font(self):
        self.manager1.set_rule("Aacute", "left", "=A")
        self.manager2.set_rule("Aacute", "left", "=A+10")

        cmd = RemoveMetricsRuleCommand("Aacute", "left")
        cmd.execute(self.context, self.managers)

        assert self.manager1.get_rule("Aacute", "left") is None
        assert self.manager2.get_rule("Aacute", "left") is None

        cmd.undo(self.context, self.managers)

        assert self.manager1.get_rule("Aacute", "left") == "=A"
        assert self.manager2.get_rule("Aacute", "left") == "=A+10"
