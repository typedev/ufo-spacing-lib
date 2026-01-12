"""Tests for rules_generator module."""

import pytest

from tests.mocks import MockFont, MockGlyph
from ufo_spacing_lib.rules_core import (
    I_SINGLE_COMPONENT,
    RuleIssue,
    W_COMPONENT_WIDER,
    W_EXTENDS_LEFT,
    W_EXTENDS_RIGHT,
    W_MISSING_BASE,
    W_MIXED_CONTOURS,
    W_ZERO_WIDTH,
)
from ufo_spacing_lib.rules_generator import (
    RuleGenerationResult,
    generate_rules_from_composites,
)


class TestRuleIssue:
    """Test RuleIssue dataclass."""

    def test_create_issue(self):
        issue = RuleIssue(
            glyph="Aacute",
            code=W_COMPONENT_WIDER,
            message="Component 1 wider than base",
            details={"base": "A", "component": "acutecomb"},
        )
        assert issue.glyph == "Aacute"
        assert issue.code == W_COMPONENT_WIDER
        assert issue.message == "Component 1 wider than base"
        assert issue.details["base"] == "A"

    def test_issue_default_details(self):
        issue = RuleIssue(glyph="A", code="W03", message="test")
        assert issue.details == {}

    def test_issue_repr(self):
        issue = RuleIssue(glyph="A", code="W03", message="test")
        assert "A" in repr(issue)
        assert "W03" in repr(issue)


class TestRuleGenerationResult:
    """Test RuleGenerationResult dataclass."""

    def test_empty_result(self):
        result = RuleGenerationResult()
        assert len(result) == 0
        assert not result
        assert not result.has_warnings

    def test_result_with_rules(self):
        result = RuleGenerationResult(
            rules={"Aacute": {"left": "=A", "right": "=A"}}
        )
        assert len(result) == 1
        assert result
        assert "Aacute" in result.rules

    def test_get_issues_for_glyph(self):
        result = RuleGenerationResult(
            issues=[
                RuleIssue("A", "W01", "msg1"),
                RuleIssue("A", "W02", "msg2"),
                RuleIssue("B", "W01", "msg3"),
            ]
        )
        a_issues = result.get_issues_for_glyph("A")
        assert len(a_issues) == 2

    def test_get_issues_by_code(self):
        result = RuleGenerationResult(
            issues=[
                RuleIssue("A", "W01", "msg1"),
                RuleIssue("B", "W01", "msg2"),
                RuleIssue("C", "W02", "msg3"),
            ]
        )
        w01_issues = result.get_issues_by_code("W01")
        assert len(w01_issues) == 2


class TestGenerateRulesSimple:
    """Test generate_rules_from_composites with simple cases."""

    def setup_method(self):
        """Create a font with composite glyphs."""
        self.font = MockFont(["A", "acutecomb", "Aacute", "B"])

        # A - base glyph with bounds
        self.font["A"].leftMargin = 50
        self.font["A"].rightMargin = 50
        self.font["A"].width = 600

        # acutecomb - accent
        self.font["acutecomb"].leftMargin = 0
        self.font["acutecomb"].rightMargin = 0
        self.font["acutecomb"].width = 100

        # Aacute - composite of A + acutecomb
        self.font["Aacute"].addComponent("A", (1, 0, 0, 1, 0, 0))
        self.font["Aacute"].addComponent("acutecomb", (1, 0, 0, 1, 250, 200))

        # B - non-composite
        self.font["B"].leftMargin = 40
        self.font["B"].rightMargin = 40

    def test_basic_composite(self):
        """Test rule generation for simple composite."""
        result = generate_rules_from_composites(self.font, ["Aacute"])

        assert "Aacute" in result.rules
        assert result.rules["Aacute"]["left"] == "=A"
        assert result.rules["Aacute"]["right"] == "=A"

    def test_non_composite_skipped(self):
        """Test that non-composite glyphs are skipped."""
        result = generate_rules_from_composites(self.font, ["B"])

        assert "B" not in result.rules
        assert len(result.rules) == 0

    def test_all_glyphs(self):
        """Test processing all glyphs."""
        result = generate_rules_from_composites(self.font)

        # Only Aacute should have rules
        assert "Aacute" in result.rules
        assert "A" not in result.rules
        assert "B" not in result.rules


class TestGenerateRulesSingleComponent:
    """Test single component handling."""

    def setup_method(self):
        self.font = MockFont(["A", "A.sc"])

        self.font["A"].leftMargin = 50
        self.font["A"].rightMargin = 50
        self.font["A"].width = 600

        # A.sc - single component
        self.font["A.sc"].addComponent("A", (0.8, 0, 0, 0.8, 0, 0))

    def test_single_component_included_by_default(self):
        result = generate_rules_from_composites(self.font)

        assert "A.sc" in result.rules
        assert result.rules["A.sc"]["left"] == "=A"

        # Should have I01 info (single component)
        i01_infos = result.get_issues_by_code(I_SINGLE_COMPONENT)
        assert len(i01_infos) == 1
        assert i01_infos[0].glyph == "A.sc"

    def test_single_component_excluded(self):
        result = generate_rules_from_composites(
            self.font, include_single_component=False
        )

        assert "A.sc" not in result.rules
        assert "A.sc" in result.skipped


class TestGenerateRulesWarnings:
    """Test warning generation."""

    def setup_method(self):
        self.font = MockFont(["i", "j", "ij", "A", "missing_ref"])

        # i - narrow
        self.font["i"].leftMargin = 50
        self.font["i"].rightMargin = 50
        self.font["i"].width = 200

        # j - wider
        self.font["j"].leftMargin = -20
        self.font["j"].rightMargin = 50
        self.font["j"].width = 250

        # ij - composite where j is wider than i
        self.font["ij"].addComponent("i", (1, 0, 0, 1, 0, 0))
        self.font["ij"].addComponent("j", (1, 0, 0, 1, 200, 0))

        # A - base
        self.font["A"].leftMargin = 50
        self.font["A"].rightMargin = 50
        self.font["A"].width = 600

        # missing_ref - references non-existent glyph
        self.font["missing_ref"].addComponent("nonexistent", (1, 0, 0, 1, 0, 0))

    def test_component_wider_warning(self):
        """Test W03 warning when component is wider than base."""
        result = generate_rules_from_composites(self.font, ["ij"])

        w03_warnings = result.get_issues_by_code(W_COMPONENT_WIDER)
        assert len(w03_warnings) == 1
        assert w03_warnings[0].glyph == "ij"
        assert w03_warnings[0].details["component"] == "j"

    def test_missing_base_warning(self):
        """Test W08 warning when base doesn't exist."""
        result = generate_rules_from_composites(self.font, ["missing_ref"])

        w08_warnings = result.get_issues_by_code(W_MISSING_BASE)
        assert len(w08_warnings) == 1
        assert "missing_ref" in result.skipped


class TestGenerateRulesExtendsBounds:
    """Test warnings for components extending beyond base."""

    def setup_method(self):
        self.font = MockFont(["I", "gravecomb", "acutecomb", "Igrave", "Iacute"])

        # I - narrow
        self.font["I"].leftMargin = 80
        self.font["I"].rightMargin = 80
        self.font["I"].width = 280

        # gravecomb - extends left
        self.font["gravecomb"].leftMargin = -100
        self.font["gravecomb"].rightMargin = 0
        self.font["gravecomb"].width = 0

        # acutecomb - extends right
        self.font["acutecomb"].leftMargin = 0
        self.font["acutecomb"].rightMargin = -100
        self.font["acutecomb"].width = 0

        # Igrave - grave extends left
        self.font["Igrave"].addComponent("I", (1, 0, 0, 1, 0, 0))
        self.font["Igrave"].addComponent("gravecomb", (1, 0, 0, 1, 100, 400))

        # Iacute - acute extends right
        self.font["Iacute"].addComponent("I", (1, 0, 0, 1, 0, 0))
        self.font["Iacute"].addComponent("acutecomb", (1, 0, 0, 1, 200, 400))

    def test_extends_left_warning(self):
        """Test W04 warning when component extends left."""
        result = generate_rules_from_composites(self.font, ["Igrave"])

        w04_warnings = result.get_issues_by_code(W_EXTENDS_LEFT)
        assert len(w04_warnings) == 1
        assert w04_warnings[0].details["component"] == "gravecomb"
        assert w04_warnings[0].details["extends_by"] > 0

    def test_extends_right_warning(self):
        """Test W05 warning when component extends right."""
        result = generate_rules_from_composites(self.font, ["Iacute"])

        w05_warnings = result.get_issues_by_code(W_EXTENDS_RIGHT)
        assert len(w05_warnings) == 1
        assert w05_warnings[0].details["component"] == "acutecomb"


class TestGenerateRulesZeroWidth:
    """Test zero width base warning."""

    def setup_method(self):
        self.font = MockFont(["zerocomb", "A", "test"])

        # Zero width combining mark
        self.font["zerocomb"].leftMargin = 0
        self.font["zerocomb"].rightMargin = 0
        self.font["zerocomb"].width = 0

        self.font["A"].leftMargin = 50
        self.font["A"].width = 600

        # test - uses zero-width as base (wrong order)
        self.font["test"].addComponent("zerocomb", (1, 0, 0, 1, 0, 0))
        self.font["test"].addComponent("A", (1, 0, 0, 1, 0, 0))

    def test_zero_width_warning(self):
        """Test W06 warning for zero width base."""
        result = generate_rules_from_composites(self.font, ["test"])

        w06_warnings = result.get_issues_by_code(W_ZERO_WIDTH)
        assert len(w06_warnings) == 1
        assert w06_warnings[0].details["base"] == "zerocomb"


class TestGenerateRulesSpecificGlyphs:
    """Test processing specific glyph list."""

    def setup_method(self):
        self.font = MockFont(["A", "B", "Aacute", "Agrave"])

        self.font["A"].leftMargin = 50
        self.font["A"].width = 600

        self.font["B"].leftMargin = 40
        self.font["B"].width = 550

        self.font["Aacute"].addComponent("A", (1, 0, 0, 1, 0, 0))
        self.font["Agrave"].addComponent("A", (1, 0, 0, 1, 0, 0))

    def test_specific_glyphs_only(self):
        """Test that only specified glyphs are processed."""
        result = generate_rules_from_composites(self.font, ["Aacute"])

        assert "Aacute" in result.rules
        assert "Agrave" not in result.rules

    def test_nonexistent_glyph_ignored(self):
        """Test that nonexistent glyphs are silently ignored."""
        result = generate_rules_from_composites(
            self.font, ["Aacute", "nonexistent"]
        )

        assert "Aacute" in result.rules
        assert len(result.rules) == 1
