"""Tests for MetricsRulesManager."""

import pytest

from tests.mocks import MockFont
from ufo_spacing_lib.rules_constants import METRICS_RULES_LIB_KEY, METRICS_RULES_VERSION
from ufo_spacing_lib.rules_manager import MetricsRulesManager


class TestManagerInitialization:
    """Test manager initialization."""

    def test_empty_font(self):
        font = MockFont(["A", "B", "C"])
        manager = MetricsRulesManager(font)
        assert len(manager) == 0
        assert not manager
        assert manager.font is font

    def test_load_existing_rules(self):
        font = MockFont(["A", "Aacute"])
        font.lib[METRICS_RULES_LIB_KEY] = {
            "version": METRICS_RULES_VERSION,
            "rules": {
                "Aacute": {"left": "=A", "right": "=A"},
            },
        }
        manager = MetricsRulesManager(font)
        assert len(manager) == 2
        assert manager.get_rule("Aacute", "left") == "=A"
        assert manager.get_rule("Aacute", "right") == "=A"

    def test_ignore_wrong_version(self):
        font = MockFont(["A"])
        font.lib[METRICS_RULES_LIB_KEY] = {
            "version": 999,  # Wrong version
            "rules": {"A": {"left": "=B"}},
        }
        manager = MetricsRulesManager(font)
        assert len(manager) == 0

    def test_repr(self):
        font = MockFont(["A", "Aacute"])
        manager = MetricsRulesManager(font)
        manager.set_rule("Aacute", "left", "=A")
        assert "rules=1" in repr(manager)


class TestReadMethods:
    """Test read methods."""

    def setup_method(self):
        self.font = MockFont(["A", "Aacute", "Agrave", "H"])
        self.manager = MetricsRulesManager(self.font)
        self.manager.set_rule("Aacute", "left", "=A")
        self.manager.set_rule("Aacute", "right", "=A+5")
        self.manager.set_rule("Agrave", "left", "=A")

    def test_get_rule(self):
        assert self.manager.get_rule("Aacute", "left") == "=A"
        assert self.manager.get_rule("Aacute", "right") == "=A+5"
        assert self.manager.get_rule("Agrave", "left") == "=A"
        assert self.manager.get_rule("Agrave", "right") is None
        assert self.manager.get_rule("H", "left") is None

    def test_get_rules_for_glyph(self):
        rules = self.manager.get_rules_for_glyph("Aacute")
        assert rules == {"left": "=A", "right": "=A+5"}

        rules = self.manager.get_rules_for_glyph("Agrave")
        assert rules == {"left": "=A"}

        rules = self.manager.get_rules_for_glyph("H")
        assert rules is None

    def test_get_all_rules(self):
        all_rules = self.manager.get_all_rules()
        assert "Aacute" in all_rules
        assert "Agrave" in all_rules
        assert all_rules["Aacute"]["left"] == "=A"

    def test_has_rule(self):
        assert self.manager.has_rule("Aacute")
        assert self.manager.has_rule("Aacute", "left")
        assert self.manager.has_rule("Aacute", "right")
        assert not self.manager.has_rule("Agrave", "right")
        assert not self.manager.has_rule("H")

    def test_get_dependents(self):
        deps = self.manager.get_dependents("A")
        assert deps == {"Aacute", "Agrave"}

    def test_get_dependencies(self):
        deps = self.manager.get_dependencies("Aacute")
        assert deps == {"A"}

        deps = self.manager.get_dependencies("A")
        assert deps == set()


class TestModificationMethods:
    """Test modification methods."""

    def setup_method(self):
        self.font = MockFont(["A", "Aacute", "Agrave", "H"])
        self.manager = MetricsRulesManager(self.font)

    def test_set_rule(self):
        self.manager.set_rule("Aacute", "left", "=A")
        assert self.manager.get_rule("Aacute", "left") == "=A"
        # Check saved to font.lib
        assert METRICS_RULES_LIB_KEY in self.font.lib

    def test_set_rule_both_sides(self):
        self.manager.set_rule("Aacute", "both", "=A")
        assert self.manager.get_rule("Aacute", "left") == "=A"
        assert self.manager.get_rule("Aacute", "right") == "=A"

    def test_set_rule_invalid_syntax(self):
        with pytest.raises(ValueError, match="Invalid rule syntax"):
            self.manager.set_rule("Aacute", "left", "invalid")

    def test_remove_rule(self):
        self.manager.set_rule("Aacute", "left", "=A")
        self.manager.set_rule("Aacute", "right", "=A")

        old = self.manager.remove_rule("Aacute", "left")
        assert old == "=A"
        assert self.manager.get_rule("Aacute", "left") is None
        assert self.manager.get_rule("Aacute", "right") == "=A"

    def test_remove_rule_both_sides(self):
        self.manager.set_rule("Aacute", "both", "=A")

        old = self.manager.remove_rule("Aacute", "both")
        assert old == "=A"
        assert self.manager.get_rules_for_glyph("Aacute") is None

    def test_remove_nonexistent_rule(self):
        old = self.manager.remove_rule("Aacute", "left")
        assert old is None

    def test_clear_rules_for_glyph(self):
        self.manager.set_rule("Aacute", "both", "=A")

        old = self.manager.clear_rules_for_glyph("Aacute")
        assert old == {"left": "=A", "right": "=A"}
        assert self.manager.get_rules_for_glyph("Aacute") is None

    def test_clear_all_rules(self):
        self.manager.set_rule("Aacute", "left", "=A")
        self.manager.set_rule("Agrave", "left", "=A")

        old = self.manager.clear_all_rules()
        assert len(old) == 2
        assert len(self.manager) == 0

    def test_cache_rebuilds_on_modification(self):
        self.manager.set_rule("Aacute", "left", "=A")
        assert self.manager.get_dependents("A") == {"Aacute"}

        self.manager.set_rule("Agrave", "left", "=A")
        assert self.manager.get_dependents("A") == {"Aacute", "Agrave"}

        self.manager.remove_rule("Aacute", "left")
        assert self.manager.get_dependents("A") == {"Agrave"}


class TestValidation:
    """Test validation."""

    def setup_method(self):
        self.font = MockFont(["A", "B", "C", "Aacute"])
        self.manager = MetricsRulesManager(self.font)

    def test_valid_rules(self):
        self.manager.set_rule("Aacute", "left", "=A")
        report = self.manager.validate()
        assert report.is_valid
        assert not report.has_errors
        assert not report.has_warnings

    def test_detect_cycle_simple(self):
        self.manager.set_rule("A", "left", "=B")
        self.manager.set_rule("B", "left", "=A")

        report = self.manager.validate()
        assert not report.is_valid
        cycle_errors = report.get_issues_by_code("E02")
        assert len(cycle_errors) >= 1

    def test_detect_cycle_chain(self):
        self.manager.set_rule("A", "left", "=B")
        self.manager.set_rule("B", "left", "=C")
        self.manager.set_rule("C", "left", "=A")

        report = self.manager.validate()
        assert not report.is_valid
        cycle_errors = report.get_issues_by_code("E02")
        assert len(cycle_errors) >= 1

    def test_detect_missing_glyph(self):
        self.manager.set_rule("A", "left", "=NonExistent")

        report = self.manager.validate()
        assert report.is_valid  # Missing glyph is warning, not error
        assert report.has_warnings
        missing_warnings = report.get_issues_by_code("W01")
        assert len(missing_warnings) == 1
        assert missing_warnings[0].details["missing"] == "NonExistent"

    def test_detect_self_reference(self):
        self.manager.set_rule("A", "left", "=A")

        report = self.manager.validate()
        # Self-reference creates a cycle, so it's an error
        assert not report.is_valid
        cycle_errors = report.get_issues_by_code("E02")
        assert len(cycle_errors) >= 1
        # Also detected as self-reference warning
        self_ref_warnings = report.get_issues_by_code("W02")
        assert len(self_ref_warnings) == 1

    def test_symmetry_not_self_reference(self):
        """=| is symmetry, not self-reference."""
        self.manager.set_rule("A", "right", "=|")

        report = self.manager.validate()
        assert report.is_valid
        assert not report.has_warnings


class TestEvaluation:
    """Test rule evaluation."""

    def setup_method(self):
        self.font = MockFont(["A", "Aacute", "H"])
        # Set up margins
        self.font["A"].leftMargin = 50
        self.font["A"].rightMargin = 60
        self.font["H"].leftMargin = 70
        self.font["H"].rightMargin = 80
        self.manager = MetricsRulesManager(self.font)

    def test_evaluate_simple(self):
        self.manager.set_rule("Aacute", "left", "=A")
        value = self.manager.evaluate("Aacute", "left")
        assert value == 50

    def test_evaluate_addition(self):
        self.manager.set_rule("Aacute", "left", "=A+10")
        value = self.manager.evaluate("Aacute", "left")
        assert value == 60

    def test_evaluate_subtraction(self):
        self.manager.set_rule("Aacute", "left", "=A-10")
        value = self.manager.evaluate("Aacute", "left")
        assert value == 40

    def test_evaluate_multiplication(self):
        self.manager.set_rule("Aacute", "left", "=A*2")
        value = self.manager.evaluate("Aacute", "left")
        assert value == 100

    def test_evaluate_division(self):
        self.manager.set_rule("Aacute", "left", "=A/2")
        value = self.manager.evaluate("Aacute", "left")
        assert value == 25

    def test_evaluate_symmetry(self):
        """=| means RSB = LSB of same glyph."""
        self.manager.set_rule("A", "right", "=|")
        value = self.manager.evaluate("A", "right")
        assert value == 50  # A's leftMargin

    def test_evaluate_opposite_side(self):
        """=H| means target.left = H.right."""
        self.manager.set_rule("Aacute", "left", "=H|")
        value = self.manager.evaluate("Aacute", "left")
        assert value == 80  # H's rightMargin

    def test_evaluate_no_rule(self):
        value = self.manager.evaluate("Aacute", "left")
        assert value is None

    def test_evaluate_missing_source(self):
        self.manager.set_rule("Aacute", "left", "=NonExistent")
        value = self.manager.evaluate("Aacute", "left")
        assert value is None

    def test_evaluate_division_by_zero(self):
        self.manager.set_rule("Aacute", "left", "=A/0")
        value = self.manager.evaluate("Aacute", "left")
        assert value is None


class TestCascadeOrder:
    """Test cascade order for dependent glyphs."""

    def setup_method(self):
        self.font = MockFont(["A", "B", "C", "D"])
        self.manager = MetricsRulesManager(self.font)

    def test_simple_cascade(self):
        self.manager.set_rule("B", "left", "=A")
        self.manager.set_rule("C", "left", "=A")

        order = self.manager.get_cascade_order("A")
        assert set(order) == {"B", "C"}

    def test_chain_cascade(self):
        # A -> B -> C
        self.manager.set_rule("B", "left", "=A")
        self.manager.set_rule("C", "left", "=B")

        order = self.manager.get_cascade_order("A")
        # B must come before C
        assert order.index("B") < order.index("C")

    def test_complex_cascade(self):
        # A -> B, A -> C, B -> D
        self.manager.set_rule("B", "left", "=A")
        self.manager.set_rule("C", "left", "=A")
        self.manager.set_rule("D", "left", "=B")

        order = self.manager.get_cascade_order("A")
        assert set(order) == {"B", "C", "D"}
        # B must come before D
        assert order.index("B") < order.index("D")

    def test_cascade_excludes_source(self):
        self.manager.set_rule("B", "left", "=A")

        order = self.manager.get_cascade_order("A")
        assert "A" not in order

    def test_get_affected_glyphs(self):
        self.manager.set_rule("B", "left", "=A")
        self.manager.set_rule("C", "left", "=B")

        affected = self.manager.get_affected_glyphs("A")
        assert affected == {"B", "C"}


class TestPersistence:
    """Test rules persistence to font.lib."""

    def test_save_and_reload(self):
        font = MockFont(["A", "Aacute"])
        manager = MetricsRulesManager(font)
        manager.set_rule("Aacute", "left", "=A")
        manager.set_rule("Aacute", "right", "=A+10")

        # Create new manager from same font
        manager2 = MetricsRulesManager(font)
        assert manager2.get_rule("Aacute", "left") == "=A"
        assert manager2.get_rule("Aacute", "right") == "=A+10"

    def test_lib_format(self):
        font = MockFont(["A", "Aacute"])
        manager = MetricsRulesManager(font)
        manager.set_rule("Aacute", "left", "=A")

        data = font.lib[METRICS_RULES_LIB_KEY]
        assert data["version"] == METRICS_RULES_VERSION
        assert "rules" in data
        assert data["rules"]["Aacute"]["left"] == "=A"
