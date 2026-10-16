"""Margin commands over the planner: the eight 0.4.3 bugs (spec §5)."""

from __future__ import annotations

import pytest

from tests.geometry import GSource, accent_font
from ufo_spacing_lib import (
    W_EMPTY_GLYPH,
    AdjustMarginCommand,
    FontContext,
    MetricsRulesManager,
    SetMarginCommand,
    SyncRulesCommand,
)

D = 20


class Info:
    def __init__(self, italic_angle):
        self.italicAngle = italic_angle


def run(source, command, rules=None):
    context = FontContext.from_single_font(source)
    managers = None
    if rules is not None:
        managers = {id(source): MetricsRulesManager.from_rules(rules, source)}
    result = command.execute(context, managers)
    return context, result


class TestBugs:
    def test_1_single_component_offset_kept(self):
        s = GSource()
        s.new("A", 600).rect(50, 0, 550, 700)
        s.new("Asmall", 600).component("A", (D, 0))
        before = s["Asmall"].drawing()
        run(s, AdjustMarginCommand("A", "left", D))
        assert s["Asmall"].drawing() == before

    def test_2_accent_edit_moves_accent_once_and_keeps_anchors(self):
        s = accent_font()
        before = s["Aacute"].drawing()
        run(s, AdjustMarginCommand("acute", "left", D))
        assert s["Aacute"].drawing() == before
        assert s["Aacute"].anchors[0].x == 300

    def test_3_mirrored_component(self):
        s = accent_font()
        s.new("Aturn", 600).component("A", (600, 700), (-1, 0, 0, -1))
        before = s["Aturn"].drawing()
        run(s, AdjustMarginCommand("A", "left", D))
        assert s["Aturn"].drawing() == before

    def test_4_undo_restores_everything(self):
        s = accent_font()
        rules = {
            "Aacute": {"left": "=A", "right": "=A"},
            "Aring": {"left": "=A", "right": "=A"},
            "Aringacute": {"left": "=Aring", "right": "=Aring"},
        }
        before = s.state()
        command = AdjustMarginCommand("A", "left", D)
        context, _ = run(s, command, rules)
        assert s.state() != before
        command.undo(context)
        assert s.state() == before

    def test_4_undo_redo_cycle(self):
        s = accent_font()
        rules = {"Aacute": {"left": "=A", "right": "=A"}}
        before = s.state()
        command = SetMarginCommand("A", "left", 70)
        context, _ = run(s, command, rules)
        after = s.state()
        command.undo(context)
        assert s.state() == before
        managers = {id(s): MetricsRulesManager.from_rules(rules, s)}
        command.execute(context, managers)
        assert s.state() == after

    def test_5_angled_left_set_changes_width(self):
        pytest.importorskip("fontTools")
        s = accent_font()
        s.info = Info(-5.710593137499643)  # tan = 0.1
        width = s["H"].width
        run(s, SetMarginCommand("H", "left", 50, value_is_angled=True))
        # Unskewed xMin of the H rectangle is 80 - 0.1 * 700 = 10.
        assert s["H"].width == pytest.approx(width + 40)

    def test_6_set_on_empty_glyph(self):
        s = accent_font()
        s.new("space", 250)
        _, result = run(s, SetMarginCommand("space", "left", 30))
        assert s["space"].width == 250
        assert any(W_EMPTY_GLYPH in w for w in result.warnings)

    def test_7_works_on_a_layer(self):
        """A source without lib and without a font API."""
        s = accent_font()
        assert not hasattr(s, "lib")
        _, result = run(s, AdjustMarginCommand("A", "left", D), AACUTE_RULES)
        assert result.success
        assert s["Aacute"].leftMargin == s["A"].leftMargin

    def test_8_rule_pointing_elsewhere_wins(self):
        s = accent_font()
        rules = {"Aacute": {"left": "=H"}}
        before = s["Aacute"].drawing()
        run(s, AdjustMarginCommand("A", "left", D), rules)
        assert s["Aacute"].drawing() == before
        assert s["Aacute"].width == 600


AACUTE_RULES = {"Aacute": {"left": "=A", "right": "=A"}}


class TestCommands:
    def test_affected_glyphs_in_plan_order(self):
        s = accent_font()
        _, result = run(s, AdjustMarginCommand("A", "left", D), AACUTE_RULES)
        assert result.affected_glyphs[0] == "A"
        assert set(result.affected_glyphs) == {"A", "Aacute", "Aring"}

    def test_scaled_context(self):
        light, bold = accent_font(), accent_font()
        context = FontContext.from_linked_fonts([light, bold], scales={bold: 2.0})
        AdjustMarginCommand("A", "left", 10).execute(context)
        assert light["A"].leftMargin == 60
        assert bold["A"].leftMargin == 70

    def test_plan_for_does_not_mutate(self):
        s = accent_font()
        before = s.state()
        plan = AdjustMarginCommand("A", "left", D).plan_for(s)
        assert plan.names == {"A", "Aacute", "Aring"}
        assert s.state() == before

    def test_sync_command_keeps_composites_and_undoes(self):
        s = accent_font()
        s.new("Aringdot", 600).component("Aring").component("acute", (300, -900))
        rules = {"Aring": {"left": "=A+10"}}
        before = s.state()
        dot_before = s["Aringdot"].drawing()
        context = FontContext.from_single_font(s)
        managers = {id(s): MetricsRulesManager.from_rules(rules, s)}
        command = SyncRulesCommand()
        result = command.execute(context, managers)
        assert s["Aring"].leftMargin == 60
        assert s["Aringdot"].drawing() == dot_before
        assert set(result.affected_glyphs) == {"Aring", "Aringacute", "Aringdot"}
        command.undo(context, managers)
        assert s.state() == before
