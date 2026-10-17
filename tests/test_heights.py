"""Margins measured at a height (=d@200+5): beam, reader protocol, planner."""

from __future__ import annotations

import math

import pytest

pytest.importorskip("fontTools")

from tests.geometry import GContour, GSource  # noqa: E402
from ufo_spacing_lib import (  # noqa: E402
    GLYPHS_GLYPH_KEY,
    GLYPHS_LAYER_KEY,
    W_NO_OUTLINE_AT_HEIGHT,
    W_READER_NO_HEIGHT,
    W_RULE_OVERRIDDEN,
    MetricsRulesManager,
    angled_margins,
    apply_plan,
    beam_margins,
    check_rules,
    glyphs_key_from_rule,
    margin_reader,
    plan_margin_edit,
    plan_restore,
    plan_sync,
    rules_from_glyphs_keys,
    upright_margins,
)

TAN = 0.1
ANGLE = -math.degrees(math.atan(TAN))  # italicAngle with slant 0.1


def d_font() -> GSource:
    """d and dcroat; dcroat's bar overhangs, so its full right margin is unrelated."""
    s = GSource()
    d = s.new("d", 560)
    d.rect(60, 0, 400, 400)  # bowl
    d.rect(400, 0, 480, 700)  # stem
    dcroat = s.new("dcroat", 560)
    dcroat.rect(60, 0, 400, 400)
    dcroat.rect(400, 0, 480, 700)
    dcroat.rect(300, 550, 600, 600)  # bar, past the advance
    s.new("space", 250)
    return s


# =============================================================================
# Beam
# =============================================================================


class TestBeam:
    def test_rectangles(self):
        s = d_font()
        assert beam_margins(s["d"], 200, s) == (60, 80)
        assert beam_margins(s["d"], 500, s) == (400, 80)
        assert beam_margins(s["dcroat"], 575, s) == (300, -40)

    def test_miss(self):
        s = d_font()
        assert beam_margins(s["d"], 900, s) == (None, None)
        assert beam_margins(s["space"], 100, s) == (None, None)

    def test_curve(self):
        """A cubic quarter-circle approximation, checked against its formula."""
        s = GSource()
        g = s.new("o", 300)
        k = 0.5522847498 * 100
        pen_points = [
            ("moveTo", (150, 0)),
            ("curveTo", (150 + k, 0), (250, 100 - k), (250, 100)),
            ("curveTo", (250, 100 + k), (150 + k, 200), (150, 200)),
            ("curveTo", (150 - k, 200), (50, 100 + k), (50, 100)),
            ("curveTo", (50, 100 - k), (150 - k, 0), (150, 0)),
        ]

        def draw(pen):
            for op, *pts in pen_points:
                getattr(pen, op)(*pts)
            pen.closePath()

        g.draw = draw  # type: ignore[method-assign]
        left, right = beam_margins(g, 100, s)
        assert left == pytest.approx(50) and right == pytest.approx(50)
        left, _ = beam_margins(g, 150, s)
        assert left == pytest.approx(150 - math.sqrt(100**2 - 50**2), abs=0.1)

    def test_components_and_transform(self):
        s = d_font()
        s.new("dd", 1120).component("d").component("d", (560, 0))
        s.new("dmir", 560).component("d", (560, 0), (-1, 0, 0, 1))
        assert beam_margins(s["dd"], 200, s) == (60, 80)
        assert beam_margins(s["dmir"], 200, s) == (80, 60)

    def test_slant(self):
        s = GSource()
        g = s.new("I", 300)
        g.contours.append(GContour([(50, 0), (100, 0), (170, 700), (120, 700)]))
        left, right = beam_margins(g, 200, s, slant=TAN)
        assert left == pytest.approx(50)
        assert right == pytest.approx(300 - 100)


# =============================================================================
# Readers
# =============================================================================


class TestReaders:
    def test_margin_reader_heights(self):
        s = d_font()
        read = margin_reader(s)
        assert read(s["dcroat"], "right") == -40
        assert read(s["dcroat"], "right", 200) == 80

    def test_angled_reader_heights(self):
        s = GSource()
        g = s.new("I", 300)
        g.contours.append(GContour([(50, 0), (100, 0), (170, 700), (120, 700)]))
        read = angled_margins(s, ANGLE)
        assert read(g, "left", 200) == pytest.approx(50)
        assert read(g, "left") == pytest.approx(50)


# =============================================================================
# Planner
# =============================================================================


RULES = {"dcroat": {"right": "=d@200+5"}}


class TestPlanner:
    def test_rule_measures_both_glyphs_at_height(self):
        s = d_font()
        plan = plan_sync(s, RULES)
        # d at 200: 80, so 85 is asked; dcroat at 200: 80 -> width +5
        assert plan.get("dcroat").width_delta == 5
        apply_plan(s, plan)
        assert beam_margins(s["dcroat"], 200, s)[1] == 85
        assert s["dcroat"].rightMargin == -35  # full margin: -40 + 5, unrelated

    def test_refires_on_source_edit(self):
        s = d_font()
        apply_plan(s, plan_sync(s, RULES))
        apply_plan(s, plan_margin_edit(s, "d", "right", delta=10, rules=RULES))
        assert beam_margins(s["dcroat"], 200, s)[1] == 95

    def test_left_rule_at_height_shifts(self):
        s = d_font()
        rules = {"dcroat": {"left": "=d@200+10"}}  # both 60 at y=200
        plan = plan_sync(s, rules)
        assert plan.get("dcroat").shift == 10
        assert plan.get("dcroat").width_delta == 10

    def test_opposite_side_at_height(self):
        s = d_font()
        rules = {"dcroat": {"left": "=|d@200"}}  # d right at 200 = 80
        assert plan_sync(s, rules).get("dcroat").shift == 20

    def test_italic(self):
        s = GSource()
        for name in ("I", "J"):
            g = s.new(name, 300)
            g.contours.append(GContour([(50, 0), (100, 0), (170, 700), (120, 700)]))
        rules = {"J": {"right": "=I@200+5"}}
        plan = plan_sync(s, rules, margins=angled_margins(s, ANGLE))
        assert plan.get("J").width_delta == pytest.approx(5)

    def test_target_misses_line(self):
        s = d_font()
        rules = {"space": {"right": "=d@200"}}
        plan = plan_sync(s, rules)
        assert not plan
        [issue] = plan.issues
        assert issue.code == W_NO_OUTLINE_AT_HEIGHT
        assert (issue.details["role"], issue.details["height"]) == ("target", 200)
        status = check_rules(s, rules)
        assert status.out_of_sync == []
        assert [i.code for i in status.issues] == [W_NO_OUTLINE_AT_HEIGHT]

    def test_source_misses_line(self):
        s = d_font()
        rules = {"dcroat": {"right": "=d@900"}}
        plan = plan_sync(s, rules)
        assert not plan
        assert plan.issues[0].details["role"] == "source"

    def test_two_argument_reader_never_ignores_height(self):
        s = d_font()
        calls = []

        def reader(glyph, side):
            calls.append(side)
            return upright_margins(glyph, side)

        plan = plan_sync(s, RULES, margins=reader)
        assert not plan
        assert [i.code for i in plan.issues] == [W_READER_NO_HEIGHT]
        assert check_rules(s, RULES, margins=reader).out_of_sync == []
        # Rules without a height still work with it
        plan = plan_sync(s, {"dcroat": {"left": "=d+10"}}, margins=reader)
        assert plan.get("dcroat").shift == 10

    def test_three_argument_reader_gets_height(self):
        s = d_font()
        seen = []

        def reader(glyph, side, at_height):
            seen.append(at_height)
            return 100.0 if at_height else upright_margins(glyph, side)

        plan_sync(s, RULES, margins=reader)
        assert seen == [200, 200]

    def test_check_rules_reports_height_values(self):
        s = d_font()
        [entry] = check_rules(s, RULES).out_of_sync
        assert (entry.expected, entry.actual) == (85, 80)

    def test_edit_override_actual_at_height(self):
        s = d_font()
        plan = plan_margin_edit(s, "dcroat", "right", delta=3, rules=RULES)
        [issue] = [i for i in plan.issues if i.code == W_RULE_OVERRIDDEN]
        assert (issue.details["expected"], issue.details["actual"]) == (85, 83)

    def test_plan_restore(self):
        s = d_font()
        value = {"version": 1, "rules": RULES, "broken": {"dcroat": ["right"]}}
        m = MetricsRulesManager.from_rules(value, s)
        assert not plan_sync(s, m)
        [broken] = check_rules(s, m).broken
        assert (broken.expected, broken.actual) == (85, 80)
        assert plan_restore(s, m, "dcroat", "right").get("dcroat").width_delta == 5

    def test_manager_evaluate_uses_beam(self):
        s = d_font()
        m = MetricsRulesManager.from_rules(RULES, s)
        assert m.evaluate("dcroat", "right") == 85


# =============================================================================
# Glyphs keys
# =============================================================================


class TestGlyphsKeys:
    def test_converted(self):
        s = d_font()
        s["dcroat"].lib.update(
            {
                GLYPHS_GLYPH_KEY.format(side="right"): "=d@200+5",
                GLYPHS_LAYER_KEY.format(side="right"): "==d@200+30",
                GLYPHS_GLYPH_KEY.format(side="left"): "d@200",
            }
        )
        rules, issues = rules_from_glyphs_keys(s)
        assert rules == {"dcroat": {"left": "=d@200", "right": "=d@200+30"}}
        assert issues == []

    def test_export_spelling(self):
        assert glyphs_key_from_rule("=d+5@200") == "=d@200+5"
        assert glyphs_key_from_rule("=|H @ -50") == "=|H@-50"
