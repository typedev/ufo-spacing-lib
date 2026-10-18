"""Generator on real geometry: multi-body alternatives, skip reasons, transforms."""

from __future__ import annotations

import pytest

from tests.geometry import GSource, accent_font
from ufo_spacing_lib import (
    W_EXTENDS_RIGHT,
    W_MIXED_CONTOURS,
    W_MULTI_BODY,
    generate_rules_from_composites,
)
from ufo_spacing_lib.rules_generator import SKIP_MIXED_CONTOURS

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


def font():
    s = accent_font()
    s.new("f", 350).rect(40, 0, 380, 750)  # overhangs its advance
    s.new("i", 260).rect(70, 0, 190, 500)
    s.new("f_i", 610).component("f").component("i", (350, 0))
    s.new("O", 700).rect(50, 0, 650, 700)
    s.new("horn", 0).rect(-20, 600, 120, 700)
    s.new("Ohorn", 700).component("O").component("horn", (620, 0))
    s.new("Abar", 600).component("A").rect(0, 300, 600, 350)
    return s


class TestMultiBody:
    def test_dz_alternative(self):
        result = generate_rules_from_composites(font(), ["DZ"])
        assert result.rules["DZ"] == {"left": "=D", "right": "=D"}
        assert result.alternatives["DZ"] == {"left": "=D", "right": "=Z"}
        [issue] = result.get_issues_by_code(W_MULTI_BODY)
        assert issue.details["default"] == {"left": "=D", "right": "=D"}
        assert issue.details["geometric"] == {"left": "=D", "right": "=Z"}
        assert (issue.details["left_component"], issue.details["right_component"]) == (
            0,
            1,
        )

    def test_ligature_alternative(self):
        result = generate_rules_from_composites(font(), ["f_i"])
        assert result.alternatives["f_i"] == {"left": "=f", "right": "=i"}

    def test_plain_accent_has_no_alternative(self):
        result = generate_rules_from_composites(font(), ["Aacute", "Aring"])
        assert result.alternatives == {}
        assert not result.get_issues_by_code(W_MULTI_BODY)

    def test_overhanging_accent_reported_not_chosen(self):
        result = generate_rules_from_composites(font(), ["Ohorn"])
        assert result.rules["Ohorn"] == {"left": "=O", "right": "=O"}
        assert result.alternatives["Ohorn"] == {"left": "=O", "right": "=horn"}
        assert result.get_issues_by_code(W_EXTENDS_RIGHT)
        assert result.get_issues_by_code(W_MULTI_BODY)

    def test_nested_composite_bounds(self):
        """Aringacute's base Aring is itself a composite."""
        result = generate_rules_from_composites(font(), ["Aringacute"])
        assert result.rules["Aringacute"] == {"left": "=Aring", "right": "=Aring"}
        assert "Aringacute" not in result.alternatives


class TestSkipReasons:
    def test_mixed_composite_listed_with_reason(self):
        result = generate_rules_from_composites(font(), ["Abar"])
        assert result.skipped == ["Abar"]
        assert result.skip_reasons == {"Abar": SKIP_MIXED_CONTOURS}
        assert result.get_issues_by_code(W_MIXED_CONTOURS)


class TestTransforms:
    def test_mirrored_component_bounds(self):
        s = GSource()
        s.new("A", 600).rect(50, 0, 550, 700)
        s.new("dot", 0).rect(-50, 750, 50, 850)
        # Mirrored A drawn at x 50..550 again, dot to its right.
        s.new("Amir", 600).component("A", (600, 0), (-1, 0, 0, 1)).component(
            "dot", (580, 0)
        )
        result = generate_rules_from_composites(s, ["Amir"])
        [issue] = result.get_issues_by_code(W_EXTENDS_RIGHT)
        assert issue.details["extends_by"] == 80

    def test_whole_source_without_names(self):
        result = generate_rules_from_composites(font())
        assert {"Aacute", "DZ", "f_i", "Ohorn"} <= set(result.rules)
        assert "Abar" in result.skipped
