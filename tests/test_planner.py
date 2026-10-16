"""Tests for the margin planner: compensation, rules cascade, sync, status."""

from __future__ import annotations

import pytest

from tests.geometry import GContour, GSource, accent_font
from ufo_spacing_lib import (
    E_CYCLE,
    W_EMPTY_GLYPH,
    W_EVALUATION_FAILED,
    W_MISSING_GLYPH,
    W_RULE_OVERRIDDEN,
    MetricsRulesManager,
    Plan,
    angled_margins,
    apply_plan,
    build_reverse_component_map,
    check_rules,
    component_shift,
    plan_margin_edit,
    plan_sync,
)

D = 20

AACUTE_RULES = {"Aacute": {"left": "=A", "right": "=A"}}


def shifted(drawing, d):
    return sorted((round(x + d, 6), y) for x, y in drawing)


def edit(source, *args, **kwargs) -> Plan:
    plan = plan_margin_edit(source, *args, **kwargs)
    apply_plan(source, plan)
    return plan


# =============================================================================
# Structural compensation (§1.1)
# =============================================================================


class TestComponentShift:
    def test_identity(self):
        assert component_shift((1, 0, 0, 1, 5, 5), (10, 0)) == (10, 0)

    def test_mirrored(self):
        assert component_shift((-1, 0, 0, 1, 0, 0), (10, 0)) == (-10, 0)

    def test_rotated_gets_dy(self):
        # 90 degrees: x' = -y, y' = x
        assert component_shift((0, 1, -1, 0, 0, 0), (10, 0)) == (0, 10)

    def test_scaled(self):
        assert component_shift((0.5, 0, 0, 2, 0, 0), (10, 0)) == (5, 0)


class TestCompensation:
    def test_left_edit_keeps_composite_in_place(self):
        s = accent_font()
        before = s["Aacute"].drawing()
        plan = edit(s, "A", "left", delta=D)
        assert s["Aacute"].drawing() == before
        assert s["Aacute"].width == 600
        assert s["Aacute"].components[0].offset == (-D, 0)
        assert s["Aacute"].components[1].offset == (300, 0)
        assert plan.get("Aacute").reasons == ["compensate:A"]

    def test_right_edit_needs_no_compensation(self):
        s = accent_font()
        plan = plan_margin_edit(s, "A", "right", delta=D)
        assert plan.names == {"A"}

    def test_existing_offset_is_kept(self):
        """0.4.3 bug 1: a single-component composite lost its offset."""
        s = GSource()
        s.new("A", 600).rect(50, 0, 550, 700)
        s.new("Asmall", 600).component("A", (D, 0))
        before = s["Asmall"].drawing()
        edit(s, "A", "left", delta=D)
        assert s["Asmall"].components[0].offset == (0, 0)
        assert s["Asmall"].drawing() == before

    def test_editing_an_accent_moves_only_its_component(self):
        """0.4.3 bug 2: the accent moved by 2d."""
        s = accent_font()
        before = s["Aacute"].drawing()
        edit(s, "acute", "left", delta=D)
        assert s["Aacute"].components[0].offset == (0, 0)
        assert s["Aacute"].components[1].offset == (300 - D, 0)
        assert s["Aacute"].drawing() == before
        assert s["Aacute"].anchors[0].x == 300

    def test_mirrored_component_gets_plus_s(self):
        """0.4.3 bug 3: transforms were ignored."""
        s = accent_font()
        s.new("Aturn", 600).component("A", (600, 700), (-1, 0, 0, -1))
        before = s["Aturn"].drawing()
        edit(s, "A", "left", delta=D)
        assert s["Aturn"].components[0].offset == (600 + D, 700)
        assert s["Aturn"].drawing() == before

    def test_rotated_component_gets_dy(self):
        s = accent_font()
        s.new("Arot", 800).component("A", (700, 0), (0, 1, -1, 0))
        before = s["Arot"].drawing()
        edit(s, "A", "left", delta=D)
        assert s["Arot"].components[0].offset == (700, -D)
        assert s["Arot"].drawing() == before

    def test_scaled_component(self):
        s = accent_font()
        s.new("Asc", 400).component("A", (0, 0), (0.5, 0, 0, 0.5))
        before = s["Asc"].drawing()
        edit(s, "A", "left", delta=D)
        assert s["Asc"].components[0].offset == (-D / 2, 0)
        assert s["Asc"].drawing() == before

    def test_collapsed_component_is_left_alone(self):
        s = accent_font()
        s.new("Aflat", 600).component("A", (0, 0), (0, 0, 0, 1))
        plan = plan_margin_edit(s, "A", "left", delta=D)
        assert "Aflat" not in plan.names

    def test_base_used_twice(self):
        s = accent_font()
        s.new("AA", 1200).component("A").component("A", (600, 0))
        before = s["AA"].drawing()
        edit(s, "A", "left", delta=D)
        assert s["AA"].drawing() == before
        assert [c.offset for c in s["AA"].components] == [(-D, 0), (600 - D, 0)]

    def test_no_recursion(self):
        """A composite held in place needs nothing for its own composites."""
        s = accent_font()
        plan = plan_margin_edit(s, "A", "left", delta=D)
        assert "Aring" in plan.names
        assert "Aringacute" not in plan.names

    def test_stale_reverse_map(self):
        """The map can outlive a deletion or list the base itself."""
        s = accent_font()
        reverse_map = {"A": ["A", "Gone", "Aacute"]}
        plan = plan_margin_edit(s, "A", "left", delta=D, reverse_map=reverse_map)
        assert plan.names == {"A", "Aacute"}
        assert plan.get("A").component_offsets == {}


# =============================================================================
# Worked examples (§1.3)
# =============================================================================


class TestWorkedExamples:
    def test_a_left_with_rules_aacute_follows(self):
        s = accent_font()
        before = s["Aacute"].drawing()
        plan = edit(s, "A", "left", delta=D, rules=AACUTE_RULES)
        aacute = s["Aacute"]
        assert aacute.components[0].offset == (0, 0)
        assert aacute.components[1].offset == (300 + D, 0)
        assert aacute.width == 600 + D
        assert aacute.drawing() == shifted(before, D)
        assert aacute.anchors[0].x == 300 + D
        assert aacute.leftMargin == s["A"].leftMargin
        assert aacute.rightMargin == s["A"].rightMargin
        assert plan.get("Aacute").reasons == ["compensate:A", "rule:left =A"]
        assert plan.get("Aacute").component_offsets == {0: (-D, 0)}
        assert plan.get("Aacute").shift == D

    def test_a_right_with_rules(self):
        s = accent_font()
        before = s["Aacute"].drawing()
        edit(s, "A", "right", delta=D, rules=AACUTE_RULES)
        assert s["Aacute"].width == 600 + D
        assert s["Aacute"].drawing() == before
        assert s["Aacute"].rightMargin == s["A"].rightMargin

    def test_acute_left_with_rules_leaves_aacute(self):
        s = accent_font()
        before = s["Aacute"].drawing()
        plan = edit(s, "acute", "left", delta=D, rules=AACUTE_RULES)
        assert s["Aacute"].drawing() == before
        assert s["Aacute"].width == 600
        assert plan.get("Aacute").reasons == ["compensate:acute"]

    def test_a_left_without_rule_no_drift_no_follow(self):
        s = accent_font()
        before = s["Aacute"].drawing()
        edit(s, "A", "left", delta=D)
        assert s["Aacute"].drawing() == before
        assert s["Aacute"].width == 600

    def test_dz_follows_d_left(self):
        s = accent_font()
        rules = {"DZ": {"left": "=D", "right": "=Z"}}
        before = s["DZ"].drawing()
        edit(s, "D", "left", delta=D, rules=rules)
        assert s["DZ"].drawing() == shifted(before, D)
        assert s["DZ"].width == 1250 + D
        assert s["DZ"].leftMargin == s["D"].leftMargin

    def test_dz_z_right(self):
        s = accent_font()
        rules = {"DZ": {"left": "=D", "right": "=Z"}}
        edit(s, "Z", "right", delta=D, rules=rules)
        assert s["DZ"].width == 1250 + D
        assert s["DZ"].rightMargin == s["Z"].rightMargin

    def test_dz_d_right_leaves_dz(self):
        s = accent_font()
        rules = {"DZ": {"left": "=D", "right": "=Z"}}
        before = s.state()["DZ"]
        plan = edit(s, "D", "right", delta=D, rules=rules)
        assert s.state()["DZ"] == before
        assert plan.names == {"D"}

    def test_nested_both_follow_and_stay_intact(self):
        s = accent_font()
        rules = {
            "Aring": {"left": "=A", "right": "=A"},
            "Aringacute": {"left": "=Aring", "right": "=Aring"},
        }
        ring_before = s["Aring"].drawing()
        nest_before = s["Aringacute"].drawing()
        plan = edit(s, "A", "left", delta=D, rules=rules)
        assert s["Aring"].drawing() == shifted(ring_before, D)
        assert s["Aringacute"].drawing() == shifted(nest_before, D)
        assert s["Aringacute"].leftMargin == s["A"].leftMargin
        assert s["Aringacute"].rightMargin == s["A"].rightMargin
        assert plan.ordered_names[0] == "A"
        assert plan.ordered_names.index("Aring") < plan.ordered_names.index(
            "Aringacute"
        )

    def test_mixed_composite_own_contours_move(self):
        s = accent_font()
        mixed = s.new("Abar", 600).component("A").rect(0, 300, 600, 350)
        rules = {"Abar": {"left": "=A+10"}}
        # Bar at 0 sets the left margin; =A+10 asks for 60 + 20 = 80.
        edit(s, "A", "left", delta=D, rules=rules)
        assert mixed.contours[0].points[0][0] == 80
        assert mixed.leftMargin == s["A"].leftMargin + 10


# =============================================================================
# Plan behaviour
# =============================================================================


class TestPlan:
    def test_planning_does_not_mutate(self):
        s = accent_font()
        before = s.state()
        plan_margin_edit(s, "A", "left", delta=D, rules=AACUTE_RULES)
        plan_sync(s, AACUTE_RULES)
        check_rules(s, AACUTE_RULES)
        assert s.state() == before

    def test_edited_glyph_first(self):
        s = accent_font()
        plan = plan_margin_edit(s, "A", "left", delta=D, rules=AACUTE_RULES)
        assert plan.changes[0].name == "A"
        assert plan.changes[0].reasons == ["edit"]
        assert plan.names == {"A", "Aacute", "Aring"}

    def test_width_delta_includes_shift(self):
        s = accent_font()
        change = plan_margin_edit(s, "A", "left", delta=D).get("A")
        assert (change.shift, change.width_delta) == (D, D)
        change = plan_margin_edit(s, "A", "right", delta=D).get("A")
        assert (change.shift, change.width_delta) == (0, D)

    def test_inverted_plan_restores_exactly(self):
        s = accent_font()
        rules = {
            "Aacute": {"left": "=A", "right": "=A"},
            "Aring": {"left": "=A", "right": "=A"},
            "Aringacute": {"left": "=Aring", "right": "=Aring"},
        }
        before = s.state()
        plan = edit(s, "A", "left", delta=D, rules=rules)
        apply_plan(s, plan.inverted())
        assert s.state() == before

    def test_value_edit(self):
        s = accent_font()
        edit(s, "A", "left", value=75, rules=AACUTE_RULES)
        assert s["A"].leftMargin == 75
        assert s["Aacute"].leftMargin == 75

    def test_zero_change_is_empty(self):
        s = accent_font()
        assert not plan_margin_edit(s, "A", "left", value=50)

    def test_apply_calls_changed(self):
        s = accent_font()
        edit(s, "A", "left", delta=D)
        assert s["A"].changed_count == 1

    def test_bad_arguments(self):
        s = accent_font()
        with pytest.raises(ValueError):
            plan_margin_edit(s, "A", "top", delta=1)
        with pytest.raises(ValueError):
            plan_margin_edit(s, "A", "left")
        with pytest.raises(ValueError):
            plan_margin_edit(s, "A", "left", delta=1, value=2)
        with pytest.raises(KeyError):
            plan_margin_edit(s, "nope", "left", delta=1)

    def test_rules_as_lib_value_or_manager(self):
        s = accent_font()
        lib_value = {"version": 1, "rules": AACUTE_RULES}
        manager = MetricsRulesManager.from_rules(AACUTE_RULES, s)
        for rules in (lib_value, manager):
            plan = plan_margin_edit(s, "A", "left", delta=D, rules=rules)
            assert plan.get("Aacute").shift == D

    def test_reverse_map_from_source_or_scan(self):
        scanned = build_reverse_component_map(accent_font())
        mapped = GSource(with_reverse_mapping=True)
        mapped.new("A", 600).rect(0, 0, 10, 10)
        mapped.new("Aacute", 600).component("A")
        assert build_reverse_component_map(mapped) == {"A": ["Aacute"]}
        assert scanned["A"] == ["Aacute", "Aring"]
        assert scanned["Aring"] == ["Aringacute"]

    def test_explicit_reverse_map_is_used(self):
        s = accent_font()
        plan = plan_margin_edit(s, "A", "left", delta=D, reverse_map={})
        assert plan.names == {"A"}


# =============================================================================
# Rules details
# =============================================================================


class TestRules:
    def test_float_rule_not_rounded(self):
        s = accent_font()
        rules = {"Aacute": {"left": "=A*1.5"}}
        edit(s, "A", "left", delta=5, rules=rules)  # A.left = 55
        assert s["Aacute"].leftMargin == 82.5

    def test_round_values_option(self):
        s = accent_font()
        rules = {"Aacute": {"left": "=A*1.5"}}
        edit(s, "A", "left", delta=5, rules=rules, round_values=True)
        assert s["Aacute"].leftMargin == 82

    def test_no_rounding_accumulates_along_cascade(self):
        s = accent_font()
        s.new("X", 600).rect(10, 0, 500, 700)
        s.new("Y", 600).rect(10, 0, 500, 700)
        rules = {"X": {"left": "=A/3"}, "Y": {"left": "=X*3"}}
        edit(s, "A", "left", delta=1, rules=rules)  # A.left = 51
        assert s["Y"].leftMargin == pytest.approx(51, abs=1e-9)

    def test_edit_overrides_own_rule(self):
        s = accent_font()
        plan = edit(s, "Aacute", "left", delta=5, rules=AACUTE_RULES)
        assert s["Aacute"].leftMargin == 55
        [issue] = [i for i in plan.issues if i.code == W_RULE_OVERRIDDEN]
        assert issue.glyph == "Aacute"
        assert issue.details["side"] == "left"
        assert issue.details["rule"] == "=A"
        assert issue.details["expected"] == 50
        assert issue.details["actual"] == 55

    def test_overridden_glyph_still_cascades(self):
        s = accent_font()
        rules = {"Aacute": {"left": "=A"}, "Aringacute": {"left": "=Aacute"}}
        edit(s, "Aacute", "left", delta=5, rules=rules)
        assert s["Aringacute"].leftMargin == 55

    def test_symmetry_follows_edited_side(self):
        s = accent_font()
        rules = {"H": {"right": "=|"}}
        edit(s, "H", "left", delta=D, rules=rules)
        assert s["H"].rightMargin == s["H"].leftMargin == 80 + D

    def test_opposite_side_rule(self):
        s = accent_font()
        rules = {"D": {"left": "=H|"}}
        edit(s, "H", "right", delta=D, rules=rules)
        assert s["D"].leftMargin == s["H"].rightMargin

    def test_unrelated_side_not_resynced(self):
        """A rule runs only when what it reads changed."""
        s = accent_font()
        s["Aacute"].width = 650  # right side out of sync with A
        plan = plan_margin_edit(s, "A", "left", delta=D, rules=AACUTE_RULES)
        assert plan.get("Aacute").width_delta == D

    def test_cycle_reported_not_raised(self):
        s = accent_font()
        rules = {"Z": {"left": "=D"}, "D": {"right": "=Z"}, "H": {"left": "=Z"}}
        plan = plan_margin_edit(s, "D", "left", delta=D, rules=rules)
        [cycle] = [i for i in plan.issues if i.code == E_CYCLE]
        assert set(cycle.details["cycle"]) == {"D", "Z"}
        assert "Z" not in plan.names
        # Downstream of a cycle stays put too: H reads the unchanged Z.
        assert "H" not in plan.names

    def test_missing_source_glyph(self):
        s = accent_font()
        rules = {"Aacute": {"left": "=A"}, "H": {"left": "=Nope"}}
        plan = plan_sync(s, rules)
        assert any(i.code == W_MISSING_GLYPH and i.glyph == "H" for i in plan.issues)

    def test_division_by_zero(self):
        s = accent_font()
        plan = plan_margin_edit(s, "A", "left", delta=D, rules={"H": {"left": "=A/0"}})
        assert any(i.code == W_EVALUATION_FAILED for i in plan.issues)
        assert "H" not in plan.names


class TestEmptyGlyphs:
    def setup_method(self):
        self.s = accent_font()
        self.s.new("space", 250)

    def test_delta_changes_width_only(self):
        plan = edit(self.s, "space", "left", delta=10)
        assert self.s["space"].width == 260
        assert plan.get("space").shift == 0

    def test_value_edit_is_an_issue(self):
        plan = plan_margin_edit(self.s, "space", "left", value=10)
        assert not plan
        assert [i.code for i in plan.issues] == [W_EMPTY_GLYPH]

    def test_rule_on_empty_target(self):
        plan = plan_margin_edit(self.s, "A", "left", delta=1, rules={"space": {"left": "=A"}})
        assert "space" not in plan.names
        assert plan.issues[0].details["role"] == "target"

    def test_rule_with_empty_source(self):
        plan = plan_sync(self.s, {"A": {"left": "=space"}})
        assert not plan
        assert plan.issues[0].details["role"] == "source"


# =============================================================================
# Sync and status
# =============================================================================


class TestSyncAndStatus:
    def setup_method(self):
        self.s = accent_font()
        self.rules = {
            "Aacute": {"left": "=A", "right": "=A"},
            "Aring": {"left": "=A+10", "right": "=A"},
            "Aringacute": {"left": "=Aring", "right": "=Aring"},
        }

    def test_check_rules_reports_out_of_sync(self):
        status = check_rules(self.s, self.rules)
        assert [(e.glyph, e.side, e.expected, e.actual) for e in status.out_of_sync] == [
            ("Aring", "left", 60, 50)
        ]
        assert not status.is_in_sync

    def test_sync_fixes_and_cascades(self):
        plan = plan_sync(self.s, self.rules)
        assert plan.ordered_names[:2] == ["Aring", "Aringacute"]
        apply_plan(self.s, plan)
        assert check_rules(self.s, self.rules).is_in_sync
        assert self.s["Aringacute"].leftMargin == 60

    def test_sync_names_are_targets_downstream_runs(self):
        plan = plan_sync(self.s, self.rules, names=["Aring"])
        assert {"Aring", "Aringacute"} <= plan.names
        plan = plan_sync(self.s, self.rules, names=["Aacute"])
        assert not plan  # Aacute is in sync

    def test_sync_keeps_composites_intact(self):
        s = self.s
        s.new("Aringdot", 600).component("Aring").component("acute", (300, -900))
        before = s["Aringdot"].drawing()
        apply_plan(s, plan_sync(s, {"Aring": {"left": "=A+10"}}))
        assert s["Aringdot"].drawing() == before

    def test_check_rules_names_and_issues(self):
        rules = {**self.rules, "D": {"left": "=Z"}, "Z": {"left": "=D"}, "H": {"left": "=X"}}
        status = check_rules(self.s, rules, names=["Aacute"])
        assert status.is_in_sync and not status.issues
        status = check_rules(self.s, rules)
        codes = {i.code for i in status.issues}
        assert {E_CYCLE, W_MISSING_GLYPH} <= codes
        assert len([i for i in status.issues if i.code == W_MISSING_GLYPH]) == 1


# =============================================================================
# Angled margins (§2.4)
# =============================================================================


class TestAngledMargins:
    def test_value_edit_in_angled_space(self):
        pytest.importorskip("fontTools")
        s = GSource()
        # A slanted parallelogram, as an italic stem would be.
        g = s.new("I", 300)
        g.contours.append(GContour([(50, 0), (100, 0), (170, 700), (120, 700)]))
        reader = angled_margins(s, -5.710593137499643)  # tan = 0.1
        assert reader(g, "left") == pytest.approx(50)
        width_before = g.width
        edit(s, "I", "left", value=60, margins=reader)
        assert reader(g, "left") == pytest.approx(60)
        assert g.width == pytest.approx(width_before + 10)  # 0.4.3 bug 5

    def test_upright_angle_is_default_reader(self):
        from ufo_spacing_lib import upright_margins

        assert angled_margins(GSource(), 0) is upright_margins
