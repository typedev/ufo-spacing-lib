"""Broken (dormant) rules: storage, planner, status, restore, commands."""

from __future__ import annotations

from tests.geometry import accent_font
from tests.mocks import MockFont
from ufo_spacing_lib import (
    W_RULE_OVERRIDDEN,
    FontContext,
    MetricsRulesManager,
    RemoveMetricsRuleCommand,
    SetMetricsRuleCommand,
    apply_plan,
    check_rules,
    generate_rules_from_composites,
    plan_margin_edit,
    plan_restore,
    plan_sync,
)
from ufo_spacing_lib.rules_constants import METRICS_RULES_LIB_KEY
from ufo_spacing_lib.rules_generator import SKIP_BROKEN_RULES, SKIP_EXISTING_RULES

D = 20
RULES = {"Aacute": {"left": "=A", "right": "=A"}}


def manager(source, rules=RULES, broken=None):
    value = {"version": 1, "rules": rules}
    if broken:
        value["broken"] = broken
    return MetricsRulesManager.from_rules(value, source)


class TestStorage:
    def test_round_trip_through_lib(self):
        font = MockFont(["A", "Aacute"])
        m = MetricsRulesManager(font)
        m.set_rule("Aacute", "both", "=A")
        assert m.mark_broken("Aacute", "left")
        stored = font.lib[METRICS_RULES_LIB_KEY]
        assert stored == {
            "version": 1,
            "rules": {"Aacute": {"left": "=A", "right": "=A"}},
            "broken": {"Aacute": ["left"]},
        }
        reloaded = MetricsRulesManager(font)
        assert reloaded.is_broken("Aacute", "left")
        assert not reloaded.is_broken("Aacute", "right")

    def test_no_broken_key_when_nothing_broken(self):
        font = MockFont(["A", "Aacute"])
        m = MetricsRulesManager(font)
        m.set_rule("Aacute", "left", "=A")
        assert "broken" not in font.lib[METRICS_RULES_LIB_KEY]

    def test_stale_entries_dropped(self):
        m = manager(None, broken={"Aacute": ["left", "top"], "Nope": ["left"]})
        assert m.get_broken() == {"Aacute": ["left"]}

    def test_plain_rules_dict_has_nothing_broken(self):
        m = MetricsRulesManager.from_rules(RULES)
        assert m.get_broken() == {}

    def test_mark_requires_rule(self):
        m = manager(None, rules={"Aacute": {"left": "=A"}})
        assert not m.mark_broken("Aacute", "right")
        assert m.mark_broken("Aacute", "both")
        assert m.get_broken() == {"Aacute": ["left"]}
        assert not m.mark_broken("Aacute", "left")  # already broken

    def test_restore(self):
        m = manager(None, broken={"Aacute": ["left", "right"]})
        assert m.restore_rule("Aacute", "left")
        assert m.get_broken() == {"Aacute": ["right"]}
        assert m.restore_rule("Aacute", "both")
        assert not m.is_broken("Aacute")
        assert not m.restore_rule("Aacute", "left")

    def test_set_and_remove_rule_clear_flag(self):
        m = manager(None, broken={"Aacute": ["left", "right"]})
        m.set_rule("Aacute", "left", "=A+5")
        assert m.get_broken() == {"Aacute": ["right"]}
        m.remove_rule("Aacute", "right")
        assert m.get_broken() == {}

    def test_clear_rules_clears_flags(self):
        m = manager(None, broken={"Aacute": ["left"]})
        m.clear_rules_for_glyph("Aacute")
        assert m.get_broken() == {}
        m = manager(None, broken={"Aacute": ["left"]})
        m.clear_all_rules()
        assert m.get_broken() == {}

    def test_validate_still_checks_broken_rules(self):
        m = manager(None, rules={"Aacute": {"left": "=Nope"}}, broken={"Aacute": ["left"]})
        assert m.validate().warnings


class TestPlanner:
    def test_edit_on_active_rule_reports_break(self):
        s = accent_font()
        plan = plan_margin_edit(s, "Aacute", "left", delta=5, rules=manager(s))
        assert plan.breaks == [("Aacute", "left")]
        assert [i.code for i in plan.issues] == [W_RULE_OVERRIDDEN]

    def test_edit_on_broken_side_reports_nothing(self):
        s = accent_font()
        m = manager(s, broken={"Aacute": ["left"]})
        plan = plan_margin_edit(s, "Aacute", "left", delta=5, rules=m)
        assert plan.breaks == [] and plan.issues == []

    def test_unruled_edit_breaks_nothing(self):
        s = accent_font()
        plan = plan_margin_edit(s, "A", "left", delta=5, rules=manager(s))
        assert plan.breaks == []
        assert plan.inverted().breaks == []

    def test_broken_rule_does_not_refire(self):
        """The break survives the next edit of the rule's source."""
        s = accent_font()
        m = manager(s, broken={"Aacute": ["left"]})
        before = s["Aacute"].drawing()
        apply_plan(s, plan_margin_edit(s, "A", "left", delta=D, rules=m))
        assert s["Aacute"].drawing() == before  # compensated, not re-ruled
        assert s["Aacute"].width == 600

    def test_other_side_still_active(self):
        s = accent_font()
        m = manager(s, broken={"Aacute": ["left"]})
        apply_plan(s, plan_margin_edit(s, "A", "right", delta=D, rules=m))
        assert s["Aacute"].rightMargin == s["A"].rightMargin

    def test_readers_of_broken_glyph_read_actual_margin(self):
        s = accent_font()
        rules = {**RULES, "Aringacute": {"left": "=Aacute"}}
        m = manager(s, rules, broken={"Aacute": ["left"]})
        apply_plan(s, plan_margin_edit(s, "Aacute", "left", delta=5, rules=m))
        assert s["Aringacute"].leftMargin == s["Aacute"].leftMargin == 55

    def test_lib_value_dict_carries_broken(self):
        s = accent_font()
        value = {"version": 1, "rules": RULES, "broken": {"Aacute": ["left"]}}
        plan = plan_margin_edit(s, "A", "left", delta=D, rules=value)
        assert plan.get("Aacute").shift == 0

    def test_sync_leaves_broken_sides(self):
        s = accent_font()
        s["Aacute"].width = 650  # right out of sync
        apply_plan(s, plan_margin_edit(s, "Aacute", "left", delta=5))  # left out of sync
        m = manager(s, broken={"Aacute": ["left"]})
        plan = plan_sync(s, m)
        assert plan.get("Aacute").shift == 0
        assert plan.get("Aacute").width_delta == -50


class TestStatusAndRestore:
    def setup_method(self):
        self.s = accent_font()
        apply_plan(self.s, plan_margin_edit(self.s, "Aacute", "left", delta=5))
        self.m = manager(self.s, broken={"Aacute": ["left"]})

    def test_check_rules_lists_broken_separately(self):
        status = check_rules(self.s, self.m)
        assert status.out_of_sync == []
        assert status.is_in_sync
        [entry] = status.broken
        assert (entry.glyph, entry.side, entry.rule, entry.expected, entry.actual) == (
            "Aacute",
            "left",
            "=A",
            50,
            55,
        )

    def test_holding_broken_rule_still_listed(self):
        m = manager(self.s, broken={"Aacute": ["right"]})
        status = check_rules(self.s, m)
        assert [(b.side, b.expected, b.actual) for b in status.broken] == [
            ("right", 50, 50)
        ]

    def test_restore_then_plan_restore(self):
        self.m.restore_rule("Aacute", "left")
        apply_plan(self.s, plan_restore(self.s, self.m, "Aacute", "left"))
        assert self.s["Aacute"].leftMargin == 50
        assert check_rules(self.s, self.m).is_in_sync

    def test_plan_restore_before_unmarking(self):
        plan = plan_restore(self.s, self.m, "Aacute", "left")
        assert plan.get("Aacute").shift == -5

    def test_plan_restore_touches_only_that_side(self):
        self.s["Aacute"].width += 30  # right out of sync too
        plan = plan_restore(self.s, self.m, "Aacute", "left")
        assert plan.get("Aacute").width_delta == -5  # only the shift

    def test_plan_restore_cascades(self):
        s = self.s
        rules = {**RULES, "Aringacute": {"left": "=Aacute"}}
        m = manager(s, rules, broken={"Aacute": ["left"]})
        apply_plan(s, plan_sync(s, m))  # Aringacute follows the broken 55
        apply_plan(s, plan_restore(s, m, "Aacute", "left"))
        assert s["Aringacute"].leftMargin == 50


class TestGeneratorAndCommands:
    def test_generator_skips_broken_like_existing(self):
        s = accent_font()
        m = manager(s, {**RULES, "Aring": {"left": "=A"}}, broken={"Aacute": ["left"]})
        result = generate_rules_from_composites(
            s, ["Aacute", "Aring"], skip_existing_rules=True, rules_manager=m
        )
        assert result.skip_reasons == {
            "Aacute": SKIP_BROKEN_RULES,
            "Aring": SKIP_EXISTING_RULES,
        }

    def test_set_rule_command_undo_restores_flag(self):
        font = MockFont(["A", "Aacute"])
        m = MetricsRulesManager(font)
        m.set_rule("Aacute", "both", "=A")
        m.mark_broken("Aacute", "left")
        context = FontContext.from_single_font(font)
        managers = {id(font): m}

        command = SetMetricsRuleCommand("Aacute", "left", "=A+5")
        command.execute(context, managers)
        assert not m.is_broken("Aacute")
        command.undo(context, managers)
        assert m.get_rule("Aacute", "left") == "=A"
        assert m.get_broken() == {"Aacute": ["left"]}

    def test_remove_rule_command_undo_restores_flag(self):
        font = MockFont(["A", "Aacute"])
        m = MetricsRulesManager(font)
        m.set_rule("Aacute", "both", "=A")
        m.mark_broken("Aacute", "right")
        context = FontContext.from_single_font(font)
        managers = {id(font): m}

        command = RemoveMetricsRuleCommand("Aacute", "both")
        command.execute(context, managers)
        assert m.get_broken() == {}
        command.undo(context, managers)
        assert m.get_broken() == {"Aacute": ["right"]}


class TestBrokenWidth:
    """0.7.0 lost a broken "width" side on serialization."""

    def test_to_lib_value_keeps_width(self):
        m = MetricsRulesManager.from_rules({"version": 1, "rules": {"B": {"width": "=A"}}})
        assert m.mark_broken("B", "width")
        assert m.to_lib_value()["broken"] == {"B": ["width"]}

    def test_side_order_and_no_empty_lists(self):
        m = MetricsRulesManager.from_rules(
            {"B": {"left": "=A", "right": "=A", "width": "=A"}, "C": {"width": "=A"}}
        )
        m.mark_broken("B", "width")
        m.mark_broken("B", "left")
        m.mark_broken("C", "width")
        m.restore_rule("C", "width")
        assert m.get_broken() == {"B": ["left", "width"]}
        assert all(m.to_lib_value()["broken"].values())

    def test_round_trip_through_font_lib(self):
        font = MockFont(["A", "B"])
        m = MetricsRulesManager(font)
        m.set_rule("B", "width", "=A")
        m.mark_broken("B", "width")
        assert font.lib[METRICS_RULES_LIB_KEY]["broken"] == {"B": ["width"]}
        assert MetricsRulesManager(font).is_broken("B", "width")

    def test_width_edit_break_survives_save(self):
        s = accent_font()
        m = manager(s, {"Aacute": {"width": "=A"}})
        plan = plan_margin_edit(s, "Aacute", "width", delta=D, rules=m)
        assert plan.breaks == [("Aacute", "width")]
        apply_plan(s, plan)
        for glyph, side in plan.breaks:
            m.mark_broken(glyph, side)
        reloaded = MetricsRulesManager.from_rules(m.to_lib_value(), s)
        assert reloaded.is_broken("Aacute", "width")
        # The break holds: editing A does not re-fire the width rule
        later = plan_margin_edit(s, "A", "right", delta=D, rules=reloaded)
        assert "Aacute" not in later.names

    def test_check_rules_lists_broken_width(self):
        s = accent_font()
        m = manager(s, {"Aacute": {"width": "=H"}}, broken={"Aacute": ["width"]})
        status = check_rules(s, m)
        assert status.out_of_sync == []
        [entry] = status.broken
        assert (entry.side, entry.expected, entry.actual) == ("width", 700, 600)
