"""
Rules Generator from Composites.

This module provides functionality to analyze composite glyphs and generate
metrics rules based on their component structure.

Example:
    >>> from ufo_spacing_lib import generate_rules_from_composites
    >>>
    >>> result = generate_rules_from_composites(font)
    >>> for glyph, sides in result.rules.items():
    ...     print(f"{glyph}: left={sides['left']}, right={sides['right']}")
    >>>
    >>> for issue in result.issues:
    ...     print(f"[{issue.code}] {issue.glyph}: {issue.message}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .rules_core import (
    RuleIssue,
    create_component_wider_warning,
    create_extends_left_warning,
    create_extends_right_warning,
    create_missing_base_warning,
    create_mixed_contours_warning,
    create_multi_body_warning,
    create_single_component_info,
    create_zero_width_warning,
)

# Skip reasons (RuleGenerationResult.skip_reasons values)
SKIP_EXISTING_RULES = "existing_rules"
SKIP_MIXED_CONTOURS = "mixed_contours"
SKIP_MISSING_BASE = "missing_base"
SKIP_SINGLE_COMPONENT = "single_component_excluded"

# =============================================================================
# Result Class
# =============================================================================


@dataclass
class RuleGenerationResult:
    """
    Result of generating rules from composites.

    Attributes:
        rules: Dict mapping glyph names to their rules.
            Format: {"Aacute": {"left": "=A", "right": "=A"}}
        issues: List of issues (warnings/info) generated during analysis.
        skipped: List of glyph names that were skipped.
        skip_reasons: Why each skipped glyph was skipped:
            {"Abar": "mixed_contours"}. One of SKIP_EXISTING_RULES,
            SKIP_MIXED_CONTOURS, SKIP_MISSING_BASE, SKIP_SINGLE_COMPONENT.
        alternatives: Geometric proposals for multi-body candidates:
            left from the component with the smallest xMin, right from the
            one with the largest xMax. Only present when it differs from
            the default (component 0); each has a W09 issue. The library
            does not choose: `rules` always holds the default.
    """

    rules: dict[str, dict[str, str]] = field(default_factory=dict)
    issues: list[RuleIssue] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    skip_reasons: dict[str, str] = field(default_factory=dict)
    alternatives: dict[str, dict[str, str]] = field(default_factory=dict)

    def skip(self, glyph_name: str, reason: str) -> None:
        """Record a skipped glyph with its reason."""
        self.skipped.append(glyph_name)
        self.skip_reasons[glyph_name] = reason

    def __len__(self) -> int:
        """Return number of rules generated."""
        return len(self.rules)

    def __bool__(self) -> bool:
        """Return True if any rules were generated."""
        return len(self.rules) > 0

    @property
    def warnings(self) -> list[RuleIssue]:
        """Get all warnings."""
        return [i for i in self.issues if i.is_warning]

    @property
    def infos(self) -> list[RuleIssue]:
        """Get all info messages."""
        return [i for i in self.issues if i.is_info]

    @property
    def has_warnings(self) -> bool:
        """Return True if any warnings were generated."""
        return any(i.is_warning for i in self.issues)

    def get_issues_for_glyph(self, glyph: str) -> list[RuleIssue]:
        """Get all issues for a specific glyph."""
        return [i for i in self.issues if i.glyph == glyph]

    def get_issues_by_code(self, code: str) -> list[RuleIssue]:
        """Get all issues with a specific code."""
        return [i for i in self.issues if i.code == code]


# =============================================================================
# Helper Functions
# =============================================================================


def _get_component_bounds(
    font: Any, component: Any
) -> tuple[float, float, float] | None:
    """
    Get horizontal bounds of a component as drawn in the composite.

    The base glyph's bounding box is mapped through the full
    transformation (scale, mirror, rotation and offset).

    Args:
        font: Glyph source.
        component: Component object with baseGlyph and transformation.

    Returns:
        Tuple of (left, right, width) or None if bounds unavailable.
    """
    box = _get_component_box(font, component)
    if box is None:
        return None
    left, _, right, _ = box
    return (left, right, right - left)


def _get_component_box(
    font: Any, component: Any
) -> tuple[float, float, float, float] | None:
    """Bounding box of the base glyph's box mapped through the transformation."""
    base_name = component.baseGlyph
    if base_name not in font:
        return None

    bounds = font[base_name].bounds
    if bounds is None:
        return None

    xx, xy, yx, yy, dx, dy = component.transformation
    x0, y0, x1, y1 = bounds
    corners = [
        (xx * x + yx * y + dx, xy * x + yy * y + dy)
        for x in (x0, x1)
        for y in (y0, y1)
    ]
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    return (min(xs), min(ys), max(xs), max(ys))


def _has_own_contours(font: Any, glyph: Any) -> bool:
    """
    Check if glyph has its own contours (not just components).

    Uses the contour count when the glyph exposes one (`glyph.contours`
    in fontParts, `len(glyph)` in defcon). Otherwise compares glyph
    bounds with the union of component bounds.
    """
    contours = getattr(glyph, "contours", None)
    if contours is not None:
        try:
            return len(contours) > 0
        except TypeError:
            pass
    elif hasattr(glyph, "__len__"):
        try:
            return len(glyph) > 0
        except TypeError:
            pass

    if not glyph.components:
        return glyph.bounds is not None

    glyph_bounds = glyph.bounds

    # If glyph bounds is None, it's a pure composite (no own contours)
    if glyph_bounds is None:
        return False

    # Calculate bounds from components only
    comp_bounds = None
    for comp in glyph.components:
        full_cb = _get_component_box(font, comp)
        if full_cb is None:
            continue
        if comp_bounds is None:
            comp_bounds = full_cb
        else:
            comp_bounds = (
                min(comp_bounds[0], full_cb[0]),
                min(comp_bounds[1], full_cb[1]),
                max(comp_bounds[2], full_cb[2]),
                max(comp_bounds[3], full_cb[3]),
            )

    # If no component bounds calculated, but glyph has bounds = has contours
    if comp_bounds is None:
        return True

    # Check if glyph bounds differ significantly from component bounds
    tolerance = 2
    return any(
        abs(glyph_bounds[i] - comp_bounds[i]) > tolerance for i in range(4)
    )


def _outermost_components(
    font: Any, glyph: Any
) -> tuple[int, int] | None:
    """
    Indices of the components with the smallest xMin and the largest xMax.

    Ties go to the lower index, so component 0 wins a tie. Components
    whose base has no outline are ignored.
    """
    leftmost: tuple[float, int] | None = None
    rightmost: tuple[float, int] | None = None
    for i, comp in enumerate(glyph.components):
        bounds = _get_component_bounds(font, comp)
        if bounds is None:
            continue
        left, right, _ = bounds
        if leftmost is None or left < leftmost[0]:
            leftmost = (left, i)
        if rightmost is None or right > rightmost[0]:
            rightmost = (right, i)
    if leftmost is None or rightmost is None:
        return None
    return leftmost[1], rightmost[1]


@dataclass
class _Analysis:
    rule: dict[str, str] | None
    issues: list[RuleIssue]
    skip_reason: str | None = None
    alternative: dict[str, str] | None = None


def _analyze_glyph(font: Any, glyph: Any) -> _Analysis:
    """
    Analyze a single glyph and generate rule + issues.

    Args:
        font: Glyph source.
        glyph: Glyph object to analyze.

    Returns:
        _Analysis; `rule` is None if the glyph should be skipped.
    """
    issues: list[RuleIssue] = []
    glyph_name = glyph.name

    # Check for mixed contours + components
    if _has_own_contours(font, glyph):
        issues.append(
            create_mixed_contours_warning(
                glyph_name, [c.baseGlyph for c in glyph.components]
            )
        )
        return _Analysis(None, issues, SKIP_MIXED_CONTOURS)

    # Get component 0 (base)
    comp0 = glyph.components[0]
    base_name = comp0.baseGlyph

    # Check if base exists
    if base_name not in font:
        issues.append(create_missing_base_warning(glyph_name, base_name))
        return _Analysis(None, issues, SKIP_MISSING_BASE)

    # Get base bounds
    base_bounds = _get_component_bounds(font, comp0)
    if base_bounds is None:
        issues.append(create_missing_base_warning(glyph_name, base_name))
        return _Analysis(None, issues, SKIP_MISSING_BASE)

    base_left, base_right, base_width = base_bounds

    # Check for zero width base
    if base_width == 0:
        issues.append(create_zero_width_warning(glyph_name, base_name))

    rule = {"left": f"={base_name}", "right": f"={base_name}"}

    # Single component case
    if len(glyph.components) == 1:
        issues.append(create_single_component_info(glyph_name, base_name))
        return _Analysis(rule, issues)

    # Check other components
    for i, comp in enumerate(glyph.components[1:], 1):
        comp_bounds = _get_component_bounds(font, comp)
        if comp_bounds is None:
            continue

        comp_left, comp_right, comp_width = comp_bounds
        comp_name = comp.baseGlyph

        # Component wider than base
        if comp_width > base_width:
            issues.append(
                create_component_wider_warning(
                    glyph_name, i, comp_name, comp_width, base_name, base_width
                )
            )

        # Component extends left
        if comp_left < base_left:
            issues.append(
                create_extends_left_warning(
                    glyph_name, i, comp_name, base_left - comp_left, base_name
                )
            )

        # Component extends right
        if comp_right > base_right:
            issues.append(
                create_extends_right_warning(
                    glyph_name, i, comp_name, comp_right - base_right, base_name
                )
            )

    # Geometric alternative: outermost components govern each side
    alternative = None
    outermost = _outermost_components(font, glyph)
    if outermost is not None and outermost != (0, 0):
        left_index, right_index = outermost
        alternative = {
            "left": f"={glyph.components[left_index].baseGlyph}",
            "right": f"={glyph.components[right_index].baseGlyph}",
        }
        issues.append(
            create_multi_body_warning(
                glyph_name, rule, alternative, left_index, right_index
            )
        )

    return _Analysis(rule, issues, alternative=alternative)


# =============================================================================
# Main Function
# =============================================================================


def generate_rules_from_composites(
    font: Any,
    glyph_names: list[str] | None = None,
    include_single_component: bool = True,
    skip_existing_rules: bool = False,
    rules_manager: Any | None = None,
) -> RuleGenerationResult:
    """
    Generate metrics rules from composite glyph structure.

    Analyzes composite glyphs and generates rules where component 0
    (index 0) determines both left and right margins. Never writes rules.

    For multi-body composites (DZ, f_i, IJ) and overhanging accents, the
    component with the smallest xMin / largest xMax may not be
    component 0. Then a geometric alternative is recorded in
    `result.alternatives` with a W09 issue holding both proposals.

    Args:
        font: Glyph source to analyze: a font or a layer (anything with
            `name in source`, `source[name]` and iteration or `keys()`).
        glyph_names: Optional list of glyph names to process.
            If None, processes all glyphs.
        include_single_component: Include glyphs with single component.
            Default True.
        skip_existing_rules: Skip glyphs that already have rules.
            Requires rules_manager. Default False.
        rules_manager: Optional MetricsRulesManager for checking
            existing rules.

    Returns:
        RuleGenerationResult with rules, issues, alternatives, and skipped
        glyphs with reasons.

    Example:
        >>> result = generate_rules_from_composites(font)
        >>> print(f"Generated {len(result)} rules")
        >>> print(f"Warnings: {len(result.warnings)}")
    """
    result = RuleGenerationResult()

    # Determine which glyphs to process
    if glyph_names is not None:
        glyphs_to_process = [font[name] for name in glyph_names if name in font]
    else:
        glyphs_to_process = [
            font[item] if isinstance(item, str) else item for item in font
        ]

    for glyph in glyphs_to_process:
        glyph_name = glyph.name

        # Skip if no components
        if not glyph.components:
            continue

        # Skip if already has rules
        if skip_existing_rules and rules_manager is not None:
            if rules_manager.has_rule(glyph_name):
                result.skip(glyph_name, SKIP_EXISTING_RULES)
                continue

        # Analyze glyph
        analysis = _analyze_glyph(font, glyph)

        # Add issues
        result.issues.extend(analysis.issues)

        # Skip if no rule generated (mixed contours, missing base, etc.)
        if analysis.rule is None:
            result.skip(glyph_name, analysis.skip_reason or SKIP_MISSING_BASE)
            continue

        # Skip single component if not included
        if not include_single_component and len(glyph.components) == 1:
            result.skip(glyph_name, SKIP_SINGLE_COMPONENT)
            continue

        # Add rule
        result.rules[glyph_name] = analysis.rule
        if analysis.alternative is not None:
            result.alternatives[glyph_name] = analysis.alternative

    return result


# =============================================================================
# Backwards Compatibility
# =============================================================================

# RuleWarning is now RuleIssue from rules_core
# Keeping alias for backwards compatibility
RuleWarning = RuleIssue
