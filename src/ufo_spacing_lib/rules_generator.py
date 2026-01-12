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
    create_single_component_info,
    create_zero_width_warning,
)


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
    """

    rules: dict[str, dict[str, str]] = field(default_factory=dict)
    issues: list[RuleIssue] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

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
    Get bounds of a component with transformation applied.

    Args:
        font: Font object.
        component: Component object with baseGlyph and transformation.

    Returns:
        Tuple of (left, right, width) or None if bounds unavailable.
    """
    base_name = component.baseGlyph
    if base_name not in font:
        return None

    base = font[base_name]
    bounds = base.bounds
    if bounds is None:
        return None

    # Apply transformation offset
    t = component.transformation
    left = bounds[0] + t[4]
    right = bounds[2] + t[4]
    width = right - left

    return (left, right, width)


def _has_own_contours(font: Any, glyph: Any) -> bool:
    """
    Check if glyph has its own contours (not just components).

    Compares glyph bounds with calculated component bounds.
    If glyph bounds is None (pure composite), returns False.
    """
    if not glyph.components:
        return glyph.bounds is not None

    glyph_bounds = glyph.bounds

    # If glyph bounds is None, it's a pure composite (no own contours)
    if glyph_bounds is None:
        return False

    # Calculate bounds from components only
    comp_bounds = None
    for comp in glyph.components:
        base_name = comp.baseGlyph
        if base_name not in font:
            continue

        base = font[base_name]
        base_bounds = base.bounds
        if base_bounds is None:
            continue

        t = comp.transformation
        full_cb = (
            base_bounds[0] + t[4],
            base_bounds[1] + t[5],
            base_bounds[2] + t[4],
            base_bounds[3] + t[5],
        )

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
    return (
        abs(glyph_bounds[0] - comp_bounds[0]) > tolerance
        or abs(glyph_bounds[1] - comp_bounds[1]) > tolerance
        or abs(glyph_bounds[2] - comp_bounds[2]) > tolerance
        or abs(glyph_bounds[3] - comp_bounds[3]) > tolerance
    )


def _analyze_glyph(
    font: Any, glyph: Any
) -> tuple[dict[str, str] | None, list[RuleIssue]]:
    """
    Analyze a single glyph and generate rule + issues.

    Args:
        font: Font object.
        glyph: Glyph object to analyze.

    Returns:
        Tuple of (rule_dict, issues_list).
        rule_dict is None if glyph should be skipped.
    """
    issues: list[RuleIssue] = []
    glyph_name = glyph.name

    # Skip glyphs without components
    if not glyph.components:
        return None, issues

    # Check for mixed contours + components
    if _has_own_contours(font, glyph):
        issues.append(
            create_mixed_contours_warning(
                glyph_name, [c.baseGlyph for c in glyph.components]
            )
        )
        return None, issues

    # Get component 0 (base)
    comp0 = glyph.components[0]
    base_name = comp0.baseGlyph

    # Check if base exists
    if base_name not in font:
        issues.append(create_missing_base_warning(glyph_name, base_name))
        return None, issues

    # Get base bounds
    base_bounds = _get_component_bounds(font, comp0)
    if base_bounds is None:
        issues.append(create_missing_base_warning(glyph_name, base_name))
        return None, issues

    base_left, base_right, base_width = base_bounds

    # Check for zero width base
    if base_width == 0:
        issues.append(create_zero_width_warning(glyph_name, base_name))

    # Single component case
    if len(glyph.components) == 1:
        issues.append(create_single_component_info(glyph_name, base_name))
        return {"left": f"={base_name}", "right": f"={base_name}"}, issues

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

    # Generate rule based on component 0
    rule = {"left": f"={base_name}", "right": f"={base_name}"}

    return rule, issues


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
    (index 0) determines both left and right margins.

    Args:
        font: Font object with glyphs to analyze.
        glyph_names: Optional list of glyph names to process.
            If None, processes all glyphs.
        include_single_component: Include glyphs with single component.
            Default True.
        skip_existing_rules: Skip glyphs that already have rules.
            Requires rules_manager. Default False.
        rules_manager: Optional MetricsRulesManager for checking
            existing rules.

    Returns:
        RuleGenerationResult with rules, issues, and skipped glyphs.

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
        glyphs_to_process = list(font)

    for glyph in glyphs_to_process:
        glyph_name = glyph.name

        # Skip if no components
        if not glyph.components:
            continue

        # Skip if already has rules
        if skip_existing_rules and rules_manager is not None:
            if rules_manager.has_rule(glyph_name):
                result.skipped.append(glyph_name)
                continue

        # Analyze glyph
        rule, issues = _analyze_glyph(font, glyph)

        # Add issues
        result.issues.extend(issues)

        # Skip if no rule generated (mixed contours, missing base, etc.)
        if rule is None:
            result.skipped.append(glyph_name)
            continue

        # Skip single component if not included
        if not include_single_component and len(glyph.components) == 1:
            result.skipped.append(glyph_name)
            continue

        # Add rule
        result.rules[glyph_name] = rule

    return result


# =============================================================================
# Backwards Compatibility
# =============================================================================

# RuleWarning is now RuleIssue from rules_core
# Keeping alias for backwards compatibility
RuleWarning = RuleIssue
