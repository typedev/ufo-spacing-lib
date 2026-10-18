"""Manual sides: storage, exclusivity with rules, planner, status, commands."""

from __future__ import annotations

from tests.geometry import accent_font
from tests.mocks import MockFont
from ufo_spacing_lib import (
    W_MANUAL_MISSING_GLYPH,
    FontContext,
    MetricsRulesManager,
    RemoveMetricsRuleCommand,
    SetMetricsRuleCommand,
    apply_plan,
    check_rules,
    plan_margin_edit,
    plan_sync,
)
from ufo_spacing_lib.rules_constants import METRICS_RULES_LIB_KEY

RULES = {"Aacute": {"left": "=A", "right": "=A"}}


def manager(source, rules=RULES, manual=None, broken=None):
    value = {"version": 1, "rules": rules}
    if manual:
        value["manual"] = manual
    if broken:
        value["broken"] = broken
    return MetricsRulesManager.from_rules(value, source)


class TestStorage:
    def test_round_trip_through_lib(self):
        font = MockFont(["A", "Aacute", "ae"])
        m = MetricsRulesManager(font)
        m.set_rule("Aacute", "left", "=A")
        assert m.mark_manual("Aacute", "right")
        assert m.mark_manual("ae", "both")
        assert font.lib[METRICS_RULES_LIB_KEY] == {
            "version": 1,
            "rules": {"Aacute": {"left": "=A"}},
            "manual": {"Aacute": ["right"], "ae": ["left", "right"]},
        }
        reloaded = MetricsRulesManager(font)
        assert reloaded.get_manual() == {"Aacute": ["right"], "ae": ["left", "right"]}
        assert reloaded.is_manual("ae")
        assert not reloaded.is_manual("Aacute", "left")

    def test_value_with_only_manual(self):
        font = MockFont(["ae"])
        font.lib[METRICS_RULES_LIB_KEY] = {"version": 1, "manual": {"ae": ["width"]}}
        m = MetricsRulesManager(font)
        assert m.get_all_rules() == {}
        assert m.get_manual() == {"ae": ["width"]}
        assert m.to_lib_value() == {
            "version": 1,
            "rules": {},
            "manual": {"ae": ["width"]},
        }

    def test_from_rules_reads_manual(self):
        m = manager(None, manual={"ae": "left"})
        assert m.get_manual() == {"ae": ["left"]}

    def test_no_manual_key_when_nothing_manual(self):
        font = MockFont(["A", "Aacute"])
        m = MetricsRulesManager(font)
        m.set_rule("Aacute", "left", "=A")
        assert "manual" not in font.lib[METRICS_RULES_LIB_KEY]

    def test_stale_entries_dropped(self):
        m = manager(None, manual={"Aacute": ["left"], "ae": ["left", "top"]})
        assert m.get_manual() == {"ae": ["left"]}  # Aacute.left has a rule

    def test_side_order(self):
        m = manager(None, {}, manual={"ae": ["width", "right", "left"]})
        assert m.get_manual() == {"ae": ["left", "right", "width"]}

    def test_clear(self):
        m = manager(None, {}, manual={"ae": ["left", "right"]})
        assert m.clear_manual("ae", "left")
        assert not m.clear_manual("ae", "left")
        assert m.clear_manual("ae", "both")
        assert m.get_manual() == {}


class TestExclusivity:
    def test_mark_refused_on_ruled_side(self):
        m = manager(None)
        assert not m.mark_manual("Aacute", "left")
        assert not m.is_manual("Aacute")

    def test_mark_refused_on_broken_side(self):
        m = manager(None, broken={"Aacute": ["left"]})
        assert not m.mark_manual("Aacute", "left")

    def test_mark_twice(self):
        m = manager(None, {})
        assert m.mark_manual("ae", "left")
        assert not m.mark_manual("ae", "left")

    def test_unknown_side_ignored(self):
        m = manager(None, {})
        assert not m.mark_manual("ae", "top")

    def test_set_rule_clears_marker(self):
        m = manager(None, {}, manual={"ae": ["left", "right"]})
        m.set_rule("ae", "left", "=a")
        assert m.get_manual() == {"ae": ["right"]}

    def test_remove_rule_then_mark(self):
        m = manager(None)
        m.remove_rule("Aacute", "left")
        assert m.mark_manual("Aacute", "left")

    def test_clearing_rules_keeps_markers(self):
        m = manager(None, manual={"ae": ["left"]})
        m.clear_rules_for_glyph("ae")
        m.clear_all_rules()
        assert m.get_manual() == {"ae": ["left"]}

    def test_bool_counts_rules_only(self):
        assert not manager(None, {}, manual={"ae": ["left"]})


class TestValidate:
    def test_missing_glyph_warns(self):
        s = accent_font()
        m = manager(s, manual={"Nope": ["left"], "Aring": ["right"]})
        report = m.validate()
        assert report.is_valid
        [issue] = [i for i in report.issues if i.code == W_MANUAL_MISSING_GLYPH]
        assert issue.glyph == "Nope"
        assert issue.details == {"sides": ["left"]}

    def test_no_source_no_warning(self):
        m = manager(None, {}, manual={"Nope": ["left"]})
        assert m.validate().issues == []


class TestPlannerAndStatus:
    def test_manual_side_only_compensated(self):
        s = accent_font()
        m = manager(s, {}, manual={"Aacute": ["left"]})
        before = s["Aacute"].drawing()
        apply_plan(s, plan_margin_edit(s, "A", "left", delta=20, rules=m))
        assert s["Aacute"].drawing() == before
        assert s["Aacute"].width == 600

    def test_manual_edit_breaks_nothing(self):
        s = accent_font()
        m = manager(s, {}, manual={"Aacute": ["left"]})
        plan = plan_margin_edit(s, "Aacute", "left", delta=5, rules=m)
        assert plan.breaks == [] and plan.issues == []

    def test_check_rules_and_sync_ignore_manual(self):
        s = accent_font()
        apply_plan(s, plan_margin_edit(s, "Aacute", "right", delta=5))
        m = manager(s, {"Aacute": {"left": "=A"}}, manual={"Aacute": ["right"]})
        status = check_rules(s, m)
        assert status.is_in_sync and status.broken == [] and status.issues == []
        assert plan_sync(s, m).changes == []


class TestCommands:
    def setup_method(self):
        self.font = MockFont(["A", "Aacute"])
        self.m = MetricsRulesManager(self.font)
        self.context = FontContext.from_single_font(self.font)
        self.managers = {id(self.font): self.m}

    def test_set_rule_command_undo_restores_marker(self):
        self.m.mark_manual("Aacute", "both")
        command = SetMetricsRuleCommand("Aacute", "left", "=A")
        command.execute(self.context, self.managers)
        assert self.m.get_manual() == {"Aacute": ["right"]}
        command.undo(self.context, self.managers)
        assert self.m.get_all_rules() == {}
        assert self.m.get_manual() == {"Aacute": ["left", "right"]}
        command.execute(self.context, self.managers)  # redo
        assert self.m.get_manual() == {"Aacute": ["right"]}

    def test_remove_rule_command_keeps_other_marker(self):
        self.m.set_rule("Aacute", "left", "=A")
        self.m.mark_manual("Aacute", "right")
        command = RemoveMetricsRuleCommand("Aacute", "left")
        command.execute(self.context, self.managers)
        command.undo(self.context, self.managers)
        assert self.m.get_rule("Aacute", "left") == "=A"
        assert self.m.get_manual() == {"Aacute": ["right"]}
