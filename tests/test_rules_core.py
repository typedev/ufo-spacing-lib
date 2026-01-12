"""Tests for rules core data classes."""


from ufo_spacing_lib.rules_constants import (
    METRICS_RULES_LIB_KEY,
    METRICS_RULES_VERSION,
    SIDE_BOTH,
    SIDE_LEFT,
    SIDE_RIGHT,
    SOURCE_SIDE_OPPOSITE,
    SOURCE_SIDE_SAME,
)
from ufo_spacing_lib.rules_core import (
    CycleError,
    MissingGlyphWarning,
    ParsedRule,
    ParseError,
    SelfReferenceWarning,
    ValidationReport,
)


class TestConstants:
    """Test constants are defined correctly."""

    def test_lib_key(self):
        assert METRICS_RULES_LIB_KEY == "com.typedev.spacing.metricsRules"

    def test_version(self):
        assert METRICS_RULES_VERSION == 1

    def test_sides(self):
        assert SIDE_LEFT == "left"
        assert SIDE_RIGHT == "right"
        assert SIDE_BOTH == "both"

    def test_source_sides(self):
        assert SOURCE_SIDE_SAME == "same"
        assert SOURCE_SIDE_OPPOSITE == "opposite"


class TestParsedRule:
    """Test ParsedRule dataclass."""

    def test_simple_rule(self):
        rule = ParsedRule(
            source_glyph="A",
            source_side="same",
        )
        assert rule.source_glyph == "A"
        assert rule.source_side == "same"
        assert rule.operator is None
        assert rule.operand is None
        assert rule.is_symmetry is False

    def test_arithmetic_rule(self):
        rule = ParsedRule(
            source_glyph="A",
            source_side="same",
            operator="+",
            operand=10.0,
        )
        assert rule.operator == "+"
        assert rule.operand == 10.0

    def test_symmetry_rule(self):
        rule = ParsedRule(
            source_glyph=None,
            source_side="same",
            is_symmetry=True,
        )
        assert rule.source_glyph is None
        assert rule.is_symmetry is True

    def test_opposite_side_rule(self):
        rule = ParsedRule(
            source_glyph="H",
            source_side="opposite",
        )
        assert rule.source_glyph == "H"
        assert rule.source_side == "opposite"


class TestParseError:
    """Test ParseError dataclass."""

    def test_creation(self):
        error = ParseError(
            glyph="Aacute",
            side="left",
            rule="=",
            error="Empty rule",
        )
        assert error.glyph == "Aacute"
        assert error.side == "left"
        assert error.rule == "="
        assert error.error == "Empty rule"

    def test_str(self):
        error = ParseError(
            glyph="Aacute",
            side="left",
            rule="=",
            error="Empty rule",
        )
        s = str(error)
        assert "Aacute.left" in s
        assert "Empty rule" in s
        assert "=" in s


class TestMissingGlyphWarning:
    """Test MissingGlyphWarning dataclass."""

    def test_creation(self):
        warning = MissingGlyphWarning(
            glyph="Aacute",
            side="left",
            rule="=A",
            missing_glyph="A",
        )
        assert warning.glyph == "Aacute"
        assert warning.missing_glyph == "A"

    def test_str(self):
        warning = MissingGlyphWarning(
            glyph="Aacute",
            side="left",
            rule="=A",
            missing_glyph="A",
        )
        s = str(warning)
        assert "Aacute.left" in s
        assert "missing glyph" in s
        assert "'A'" in s


class TestCycleError:
    """Test CycleError dataclass."""

    def test_creation(self):
        error = CycleError(cycle=["A", "B", "A"])
        assert error.cycle == ["A", "B", "A"]

    def test_str(self):
        error = CycleError(cycle=["A", "B", "C", "A"])
        s = str(error)
        assert "Circular dependency" in s
        assert "A -> B -> C -> A" in s


class TestSelfReferenceWarning:
    """Test SelfReferenceWarning dataclass."""

    def test_creation(self):
        warning = SelfReferenceWarning(
            glyph="A",
            side="left",
            rule="=A",
        )
        assert warning.glyph == "A"

    def test_str(self):
        warning = SelfReferenceWarning(
            glyph="A",
            side="left",
            rule="=A",
        )
        s = str(warning)
        assert "A.left" in s
        assert "self-reference" in s


class TestValidationReport:
    """Test ValidationReport dataclass."""

    def test_valid_report(self):
        report = ValidationReport(is_valid=True)
        assert report.is_valid is True
        assert report.has_errors is False
        assert report.has_warnings is False
        assert len(report.errors) == 0
        assert len(report.warnings) == 0
        assert bool(report) is True

    def test_report_with_cycles(self):
        from ufo_spacing_lib.rules_core import create_cycle_error

        report = ValidationReport(
            is_valid=False,
            issues=[create_cycle_error(["A", "B", "A"])],
        )
        assert report.is_valid is False
        assert report.has_errors is True
        assert len(report.errors) == 1
        assert "A -> B -> A" in str(report.errors[0])
        assert bool(report) is False

    def test_report_with_parse_errors(self):
        from ufo_spacing_lib.rules_core import create_parse_error

        report = ValidationReport(
            is_valid=False,
            issues=[create_parse_error("X", "left", "=", "Empty")],
        )
        assert report.has_errors is True
        assert len(report.errors) == 1

    def test_report_with_warnings(self):
        from ufo_spacing_lib.rules_core import (
            create_missing_glyph_warning,
            create_self_reference_warning,
        )

        report = ValidationReport(
            is_valid=True,
            issues=[
                create_missing_glyph_warning("Aacute", "left", "=A", "A"),
                create_self_reference_warning("B", "right", "=B"),
            ],
        )
        assert report.is_valid is True
        assert report.has_warnings is True
        assert len(report.warnings) == 2

    def test_report_with_all_issues(self):
        from ufo_spacing_lib.rules_core import (
            create_cycle_error,
            create_missing_glyph_warning,
            create_parse_error,
            create_self_reference_warning,
        )

        report = ValidationReport(
            is_valid=False,
            issues=[
                create_cycle_error(["A", "B", "A"]),
                create_missing_glyph_warning("X", "left", "=Y", "Y"),
                create_parse_error("Z", "right", "==", "Invalid"),
                create_self_reference_warning("W", "left", "=W"),
            ],
        )
        assert report.has_errors is True
        assert report.has_warnings is True
        assert len(report.errors) == 2
        assert len(report.warnings) == 2
