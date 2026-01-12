"""Tests for rules parser."""

import pytest

from ufo_spacing_lib.rules_constants import SOURCE_SIDE_OPPOSITE, SOURCE_SIDE_SAME
from ufo_spacing_lib.rules_parser import RuleParseError, RuleParser


class TestRuleParserSimpleReference:
    """Test simple reference rules like =A."""

    def setup_method(self):
        self.parser = RuleParser()

    def test_simple_reference(self):
        rule = self.parser.parse("=A", "left")
        assert rule.source_glyph == "A"
        assert rule.source_side == SOURCE_SIDE_SAME
        assert rule.operator is None
        assert rule.operand is None
        assert rule.is_symmetry is False

    def test_simple_reference_lowercase(self):
        rule = self.parser.parse("=a", "left")
        assert rule.source_glyph == "a"

    def test_simple_reference_long_name(self):
        rule = self.parser.parse("=Aacute", "left")
        assert rule.source_glyph == "Aacute"

    def test_simple_reference_with_dot(self):
        """Test glyph names like zero.lf."""
        rule = self.parser.parse("=zero.lf", "left")
        assert rule.source_glyph == "zero.lf"

    def test_simple_reference_with_underscore(self):
        rule = self.parser.parse("=A_acute", "left")
        assert rule.source_glyph == "A_acute"

    def test_simple_reference_with_numbers(self):
        rule = self.parser.parse("=uni0041", "left")
        assert rule.source_glyph == "uni0041"

    def test_simple_reference_underscore_start(self):
        rule = self.parser.parse("=_notdef", "left")
        assert rule.source_glyph == "_notdef"

    def test_simple_reference_complex_name(self):
        rule = self.parser.parse("=A.ss01.alt", "right")
        assert rule.source_glyph == "A.ss01.alt"


class TestRuleParserArithmetic:
    """Test arithmetic rules like =A+10."""

    def setup_method(self):
        self.parser = RuleParser()

    def test_addition_integer(self):
        rule = self.parser.parse("=A+10", "left")
        assert rule.source_glyph == "A"
        assert rule.operator == "+"
        assert rule.operand == 10.0
        assert rule.source_side == SOURCE_SIDE_SAME

    def test_addition_float(self):
        rule = self.parser.parse("=A+10.5", "left")
        assert rule.operand == 10.5

    def test_subtraction(self):
        rule = self.parser.parse("=H-5", "right")
        assert rule.source_glyph == "H"
        assert rule.operator == "-"
        assert rule.operand == 5.0

    def test_multiplication(self):
        rule = self.parser.parse("=O*1.5", "left")
        assert rule.source_glyph == "O"
        assert rule.operator == "*"
        assert rule.operand == 1.5

    def test_multiplication_integer(self):
        rule = self.parser.parse("=O*2", "left")
        assert rule.operand == 2.0

    def test_division(self):
        rule = self.parser.parse("=H/2", "left")
        assert rule.source_glyph == "H"
        assert rule.operator == "/"
        assert rule.operand == 2.0

    def test_arithmetic_with_complex_glyph(self):
        rule = self.parser.parse("=zero.lf+5", "left")
        assert rule.source_glyph == "zero.lf"
        assert rule.operator == "+"
        assert rule.operand == 5.0

    def test_arithmetic_zero(self):
        rule = self.parser.parse("=A+0", "left")
        assert rule.operand == 0.0


class TestRuleParserSymmetry:
    """Test symmetry rules."""

    def setup_method(self):
        self.parser = RuleParser()

    def test_symmetry_self(self):
        """Test =| pattern (RSB = LSB of same glyph)."""
        rule = self.parser.parse("=|", "right")
        assert rule.source_glyph is None
        assert rule.is_symmetry is True
        assert rule.operator is None

    def test_opposite_side(self):
        """Test =H| pattern (LSB of target = RSB of H)."""
        rule = self.parser.parse("=H|", "left")
        assert rule.source_glyph == "H"
        assert rule.source_side == SOURCE_SIDE_OPPOSITE
        assert rule.is_symmetry is False

    def test_opposite_side_complex_glyph(self):
        rule = self.parser.parse("=zero.lf|", "left")
        assert rule.source_glyph == "zero.lf"
        assert rule.source_side == SOURCE_SIDE_OPPOSITE


class TestRuleParserInvalid:
    """Test invalid rule syntax."""

    def setup_method(self):
        self.parser = RuleParser()

    def test_empty_rule(self):
        with pytest.raises(RuleParseError, match="Empty rule"):
            self.parser.parse("", "left")

    def test_no_equals(self):
        with pytest.raises(RuleParseError, match="must start with '='"):
            self.parser.parse("A", "left")

    def test_only_equals(self):
        with pytest.raises(RuleParseError, match="Invalid rule syntax"):
            self.parser.parse("=", "left")

    def test_double_equals(self):
        with pytest.raises(RuleParseError, match="Invalid rule syntax"):
            self.parser.parse("==A", "left")

    def test_equals_with_number_only(self):
        with pytest.raises(RuleParseError, match="Invalid rule syntax"):
            self.parser.parse("=10", "left")

    def test_invalid_operator_position(self):
        with pytest.raises(RuleParseError, match="Invalid rule syntax"):
            self.parser.parse("=+A", "left")

    def test_glyph_starting_with_number(self):
        with pytest.raises(RuleParseError, match="Invalid rule syntax"):
            self.parser.parse("=1A", "left")

    def test_missing_operand(self):
        with pytest.raises(RuleParseError, match="Invalid rule syntax"):
            self.parser.parse("=A+", "left")

    def test_double_operator(self):
        with pytest.raises(RuleParseError, match="Invalid rule syntax"):
            self.parser.parse("=A++10", "left")

    def test_invalid_symmetry_syntax(self):
        with pytest.raises(RuleParseError, match="Invalid rule syntax"):
            self.parser.parse("=||", "left")

    def test_pipe_in_middle(self):
        with pytest.raises(RuleParseError, match="Invalid rule syntax"):
            self.parser.parse("=A|B", "left")


class TestRuleParserValidateSyntax:
    """Test validate_syntax method."""

    def setup_method(self):
        self.parser = RuleParser()

    def test_valid_simple(self):
        is_valid, error = self.parser.validate_syntax("=A")
        assert is_valid is True
        assert error is None

    def test_valid_arithmetic(self):
        is_valid, error = self.parser.validate_syntax("=A+10")
        assert is_valid is True
        assert error is None

    def test_valid_symmetry(self):
        is_valid, error = self.parser.validate_syntax("=|")
        assert is_valid is True
        assert error is None

    def test_valid_opposite(self):
        is_valid, error = self.parser.validate_syntax("=H|")
        assert is_valid is True
        assert error is None

    def test_invalid_empty(self):
        is_valid, error = self.parser.validate_syntax("")
        assert is_valid is False
        assert "Empty rule" in error

    def test_invalid_no_equals(self):
        is_valid, error = self.parser.validate_syntax("A")
        assert is_valid is False
        assert "must start with '='" in error

    def test_invalid_syntax(self):
        is_valid, error = self.parser.validate_syntax("=")
        assert is_valid is False
        assert error is not None


class TestRuleParserExtractReferencedGlyph:
    """Test extract_referenced_glyph method."""

    def setup_method(self):
        self.parser = RuleParser()

    def test_simple_reference(self):
        glyph = self.parser.extract_referenced_glyph("=A")
        assert glyph == "A"

    def test_arithmetic_reference(self):
        glyph = self.parser.extract_referenced_glyph("=A+10")
        assert glyph == "A"

    def test_opposite_reference(self):
        glyph = self.parser.extract_referenced_glyph("=H|")
        assert glyph == "H"

    def test_symmetry(self):
        glyph = self.parser.extract_referenced_glyph("=|")
        assert glyph is None

    def test_invalid_rule(self):
        glyph = self.parser.extract_referenced_glyph("invalid")
        assert glyph is None

    def test_complex_glyph_name(self):
        glyph = self.parser.extract_referenced_glyph("=A.ss01+5")
        assert glyph == "A.ss01"
