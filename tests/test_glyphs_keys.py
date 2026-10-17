"""Glyphs.app metrics-key compatibility: syntax, width rules, conversion."""

from __future__ import annotations

import pytest

from tests.geometry import accent_font
from ufo_spacing_lib import (
    E_PARSE_ERROR,
    GLYPHS_GLYPH_KEY,
    GLYPHS_LAYER_KEY,
    W_AMBIGUOUS_NAME,
    W_MISSING_GLYPH,
    W_RULE_OVERRIDDEN,
    W_WIDTH_RIGHT_CONFLICT,
    MetricsRulesManager,
    apply_plan,
    check_rules,
    glyphs_key_from_rule,
    plan_margin_edit,
    plan_sync,
    rules_from_glyphs_keys,
)
from ufo_spacing_lib.rules_parser import RuleParseError, RuleParser

D = 20


# =============================================================================
# Syntax
# =============================================================================


class TestSyntax:
    parser = RuleParser()

    @pytest.mark.parametrize(
        "rule, canonical",
        [
            ("=A", "=A"),
            ("=a-cy", "=a-cy"),
            ("=el-cy.loclBGR", "=el-cy.loclBGR"),
            ("=A-cy.ss01+10", "=A-cy.ss01+10"),
            ("=a-5", "=a-5"),  # a minus 5
            ("=H + 10", "=H+10"),
            ("=c*1.1", "=c*1.1"),
            ("=d/2", "=d/2"),
            ("=|", "=|"),
            ("|", "=|"),
            ("=|H", "=|H"),
            ("=|H+20", "=|H+20"),
            ("=H|", "=|H"),  # legacy alias
            ("=40", "=40"),
            ("=-20", "=-20"),
            ("==n+15", "=n+15"),
            ("A", "=A"),
            ("a-cy", "=a-cy"),
            ("a-5", "a-5"),  # bare: the glyph "a-5"
        ],
    )
    def test_canonical(self, rule, canonical):
        assert self.parser.format(rule) == canonical
        assert glyphs_key_from_rule(rule) == canonical

    def test_trailing_operation_wins(self):
        parsed = self.parser.parse("=a-5", "left")
        assert (parsed.source_glyph, parsed.operator, parsed.operand) == ("a", "-", 5)
        parsed = self.parser.parse("=a-cy-10", "left")
        assert (parsed.source_glyph, parsed.operator, parsed.operand) == ("a-cy", "-", 10)

    def test_bare_name_is_the_whole_name(self):
        parsed = self.parser.parse("a-5", "left")
        assert parsed.source_glyph == "a-5" and parsed.operator is None
        # ...and its canonical spelling reads back as the same glyph
        again = self.parser.parse(self.parser.format("a-5"), "left")
        assert again.source_glyph == "a-5" and again.operator is None
        opposite = self.parser.format("=a-5|")
        assert self.parser.parse(opposite, "left").source_glyph == "a-5"

    def test_opposite_semantics(self):
        parsed = self.parser.parse("=|H+20", "left")
        assert parsed.source_side_for("left") == "right"
        assert parsed.operand == 20

    @pytest.mark.parametrize(
        "rule, reason",
        [
            ("=|@200", "Symmetry \\(=\\|\\) cannot be measured at a height"),
            ("=40@200", "a constant has no height"),
            ("=+10", "Auto-alignment offsets"),
            ("=(H+O)/2", "parentheses"),
            ("=|+10", "Arithmetic on symmetry"),
            ("=H+O", "Invalid rule syntax"),
            ("=H*-1", "Invalid rule syntax"),
            ("A+10", "must be a glyph name"),
            ("=", "Empty rule"),
            ("=H|+5", "Invalid rule syntax"),
        ],
    )
    def test_unsupported_gives_clean_error(self, rule, reason):
        with pytest.raises(RuleParseError, match=reason):
            self.parser.parse(rule, "left")

    @pytest.mark.parametrize("rule", ["=|", "=|H", "=H|"])
    def test_width_rejects_opposite(self, rule):
        with pytest.raises(RuleParseError, match="not allowed for width"):
            self.parser.parse(rule, "width")

    def test_width_accepts_reference_and_constant(self):
        assert self.parser.format("=H+20", "width") == "=H+20"
        assert self.parser.format("=600", "width") == "=600"


# =============================================================================
# Manager
# =============================================================================


class TestManager:
    def test_set_rule_stores_canonical(self):
        m = MetricsRulesManager.from_rules({})
        m.set_rule("Aacute", "left", "=A|")
        m.set_rule("Aacute", "right", "A")
        m.set_rule("Aacute", "width", "==H + 10")
        assert m.get_rules_for_glyph("Aacute") == {
            "left": "=|A",
            "right": "=A",
            "width": "=H+10",
        }

    def test_loading_canonicalizes_and_keeps_unparseable(self):
        m = MetricsRulesManager.from_rules(
            {"X": {"left": "=H|", "right": "=(A+B)/2"}}
        )
        assert m.get_all_rules() == {"X": {"left": "=|H", "right": "=(A+B)/2"}}
        lib = m.to_lib_value()
        assert lib["rules"]["X"] == {"left": "=|H", "right": "=(A+B)/2"}

    def test_set_rule_width_rejects_symmetry(self):
        m = MetricsRulesManager.from_rules({})
        with pytest.raises(ValueError, match="not allowed for width"):
            m.set_rule("X", "width", "=|")

    def test_both_means_left_and_right(self):
        m = MetricsRulesManager.from_rules({})
        m.set_rule("X", "both", "=H")
        assert m.get_rules_for_glyph("X") == {"left": "=H", "right": "=H"}

    def test_validate_conflict_and_ambiguity(self):
        s = accent_font()
        s.new("a", 500).rect(40, 0, 460, 500)
        s.new("a-5", 500).rect(40, 0, 460, 500)
        m = MetricsRulesManager.from_rules(
            {"X": {"right": "=H", "width": "=H"}, "Y": {"left": "=a-5"}}, s
        )
        codes = {(i.glyph, i.code) for i in m.validate().issues}
        assert ("X", W_WIDTH_RIGHT_CONFLICT) in codes
        assert ("Y", W_AMBIGUOUS_NAME) in codes

    def test_validate_reports_reason(self):
        m = MetricsRulesManager.from_rules({"X": {"left": "=+10"}})
        [issue] = m.validate().errors
        assert "Auto-alignment offsets" in issue.message

    def test_evaluate_constant_and_width(self):
        s = accent_font()
        m = MetricsRulesManager.from_rules(
            {"Aacute": {"left": "=40", "width": "=H+20"}}, s
        )
        assert m.evaluate("Aacute", "left") == 40
        assert m.evaluate("Aacute", "width") == 720


# =============================================================================
# Width rules in the planner
# =============================================================================


class TestWidthRules:
    def test_width_rule_follows_source_width(self):
        s = accent_font()
        rules = {"Aacute": {"width": "=A"}}
        before = s["Aacute"].drawing()
        apply_plan(s, plan_margin_edit(s, "A", "right", delta=D, rules=rules))
        assert s["Aacute"].width == 600 + D
        assert s["Aacute"].drawing() == before  # shift 0

    def test_width_edit_cascades(self):
        s = accent_font()
        rules = {"Aacute": {"width": "=A+10"}}
        plan = plan_margin_edit(s, "A", "width", value=650, rules=rules)
        assert plan.get("A").width_delta == 50
        assert plan.get("Aacute").width_delta == 60
        assert plan.get("Aacute").shift == 0

    def test_left_edit_keeps_width(self):
        """Glyphs: LSB and width fixed, the RSB is computed."""
        s = accent_font()
        rules = {"H": {"width": "=700"}}
        apply_plan(s, plan_margin_edit(s, "H", "left", delta=D, rules=rules))
        assert s["H"].width == 700
        assert s["H"].leftMargin == 80 + D
        assert s["H"].rightMargin == 80 - D

    def test_left_rule_keeps_width(self):
        s = accent_font()
        rules = {"Aacute": {"left": "=A", "width": "=600"}}
        apply_plan(s, plan_margin_edit(s, "A", "left", delta=D, rules=rules))
        assert s["Aacute"].leftMargin == s["A"].leftMargin
        assert s["Aacute"].width == 600

    def test_right_edit_breaks_width_rule(self):
        s = accent_font()
        rules = {"H": {"width": "=700"}}
        plan = plan_margin_edit(s, "H", "right", delta=D, rules=rules)
        assert plan.breaks == [("H", "width")]
        [issue] = [i for i in plan.issues if i.code == W_RULE_OVERRIDDEN]
        assert issue.details["side"] == "width"
        assert issue.details["actual"] == 700 + D
        assert plan.get("H").width_delta == D

    def test_right_rule_yields_to_width_rule(self):
        s = accent_font()
        rules = {"Aacute": {"right": "=H", "width": "=A"}}
        plan = plan_sync(s, rules)
        assert not plan  # width already =A; right rule ignored
        status = check_rules(s, rules)
        assert status.is_in_sync
        assert any(i.code == W_WIDTH_RIGHT_CONFLICT for i in status.issues)

    def test_broken_width_rule_lets_right_rule_run(self):
        s = accent_font()
        value = {
            "version": 1,
            "rules": {"Aacute": {"right": "=H", "width": "=A"}},
            "broken": {"Aacute": ["width"]},
        }
        plan = plan_sync(s, value)
        assert plan.get("Aacute").width_delta == 80 - 50

    def test_constant_rule_in_sync(self):
        s = accent_font()
        plan = plan_sync(s, {"H": {"left": "=100"}})
        assert plan.get("H").shift == 20

    def test_check_rules_width_out_of_sync(self):
        s = accent_font()
        status = check_rules(s, {"Aacute": {"width": "=H"}})
        [entry] = status.out_of_sync
        assert (entry.side, entry.expected, entry.actual) == ("width", 700, 600)

    def test_old_sides_unchanged_by_width_side(self):
        s = accent_font()
        rules = {"Aacute": {"left": "=A", "right": "=A"}}
        plan = plan_margin_edit(s, "A", "left", delta=D, rules=rules)
        assert plan.get("Aacute").width_delta == D


# =============================================================================
# Conversion helpers
# =============================================================================


def glyphs_font():
    s = accent_font()
    s.new("a-cy", 500).rect(40, 0, 460, 500)
    s["Aacute"].lib.update(
        {
            GLYPHS_GLYPH_KEY.format(side="left"): "=A",
            GLYPHS_GLYPH_KEY.format(side="right"): "=A",
            GLYPHS_LAYER_KEY.format(side="right"): "==|H+5",
        }
    )
    s["Aring"].lib.update(
        {
            GLYPHS_GLYPH_KEY.format(side="left"): "a-cy",
            GLYPHS_GLYPH_KEY.format(side="right"): "=+10",
            GLYPHS_GLYPH_KEY.format(side="width"): "=Missing+10",
        }
    )
    s["DZ"].lib.update(
        {
            GLYPHS_GLYPH_KEY.format(side="right"): "=Z",
            GLYPHS_GLYPH_KEY.format(side="width"): "=1250",
        }
    )
    return s


class TestConversion:
    def test_rules_from_glyphs_keys(self):
        s = glyphs_font()
        before = {g.name: dict(g.lib) for g in s}
        rules, issues = rules_from_glyphs_keys(s)
        assert rules == {
            "Aacute": {"left": "=A", "right": "=|H+5"},  # layer key wins
            "Aring": {"left": "=a-cy", "width": "=Missing+10"},
            "DZ": {"right": "=Z", "width": "=1250"},
        }
        by_code = {(i.glyph, i.code): i for i in issues}
        parse = by_code[("Aring", E_PARSE_ERROR)]
        assert parse.details["rule"] == "=+10"
        assert "Auto-alignment offsets" in parse.message
        assert parse.details["level"] == "glyph"
        assert by_code[("Aring", W_MISSING_GLYPH)].details["side"] == "width"
        conflict = by_code[("DZ", W_WIDTH_RIGHT_CONFLICT)]
        assert conflict.details["key"] == GLYPHS_GLYPH_KEY.format(side="right")
        # Never writes the lib
        assert {g.name: dict(g.lib) for g in s} == before

    def test_glyph_names_filter(self):
        rules, _ = rules_from_glyphs_keys(glyphs_font(), ["DZ", "Nope"])
        assert list(rules) == ["DZ"]

    def test_round_trip_through_manager(self):
        s = glyphs_font()
        rules, _ = rules_from_glyphs_keys(s)
        m = MetricsRulesManager.from_rules(rules, s)
        for glyph, sides in rules.items():
            for side, rule in sides.items():
                assert glyphs_key_from_rule(m.get_rule(glyph, side), side) == rule
