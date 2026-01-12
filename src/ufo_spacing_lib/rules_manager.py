"""
Metrics Rules Manager.

This module provides the MetricsRulesManager class for managing metrics rules
with caching, validation, and evaluation support.

Example:
    >>> manager = MetricsRulesManager(font)
    >>> manager.set_rule("Aacute", "left", "=A")
    >>> manager.set_rule("Aacute", "right", "=A")
    >>>
    >>> # Validate rules
    >>> report = manager.validate()
    >>> if not report.is_valid:
    ...     print(report.errors)
    >>>
    >>> # Evaluate rule
    >>> value = manager.evaluate("Aacute", "left")
"""

from __future__ import annotations

from typing import Any

from .rules_constants import (
    METRICS_RULES_LIB_KEY,
    METRICS_RULES_VERSION,
    SOURCE_SIDE_OPPOSITE,
)
from .rules_core import (
    ParsedRule,
    RuleIssue,
    ValidationReport,
    create_cycle_error,
    create_missing_glyph_warning,
    create_parse_error,
    create_self_reference_warning,
)
from .rules_parser import RuleParseError, RuleParser


class MetricsRulesManager:
    """
    Manager for metrics rules with caching and validation.

    Handles loading, saving, caching, validation, and evaluation of
    metrics rules. Supports runtime modification with automatic cache
    rebuilding.

    Attributes:
        font: The font object this manager is associated with.

    Example:
        >>> manager = MetricsRulesManager(font)
        >>>
        >>> # Set rules
        >>> manager.set_rule("Aacute", "left", "=A")
        >>> manager.set_rule("Agrave", "both", "=A")  # both sides
        >>>
        >>> # Get dependents (glyphs that depend on A)
        >>> deps = manager.get_dependents("A")
        >>> # {'Aacute', 'Agrave'}
        >>>
        >>> # Validate
        >>> report = manager.validate()
        >>> if report.is_valid:
        ...     print("All rules are valid")
    """

    def __init__(self, font: Any):
        """
        Initialize the manager for a font.

        Args:
            font: Font object with `lib` attribute for storage and
                glyph access via `font[glyph_name]`.
        """
        self._font = font
        self._parser = RuleParser()

        # Raw rules: {glyph: {side: rule_string}}
        self._rules: dict[str, dict[str, str]] = {}

        # Parsed rules cache: {glyph: {side: ParsedRule}}
        self._parsed_cache: dict[str, dict[str, ParsedRule]] = {}

        # Reverse dependency cache: {source_glyph: {dependent_glyphs}}
        self._dependents_cache: dict[str, set[str]] = {}

        # Load existing rules from font
        self._load_from_font()
        self._rebuild_caches()

    @property
    def font(self) -> Any:
        """The font this manager is associated with."""
        return self._font

    # =========================================================================
    # Load / Save
    # =========================================================================

    def _load_from_font(self) -> None:
        """Load rules from font.lib."""
        if not hasattr(self._font, "lib"):
            return

        data = self._font.lib.get(METRICS_RULES_LIB_KEY)
        if not data:
            return

        # Check version
        version = data.get("version", 0)
        if version != METRICS_RULES_VERSION:
            # Future: handle version migration
            return

        rules = data.get("rules", {})
        if isinstance(rules, dict):
            self._rules = {
                glyph: dict(sides) for glyph, sides in rules.items()
            }

    def _save_to_font(self) -> None:
        """Save rules to font.lib."""
        if not hasattr(self._font, "lib"):
            return

        self._font.lib[METRICS_RULES_LIB_KEY] = {
            "version": METRICS_RULES_VERSION,
            "rules": {
                glyph: dict(sides) for glyph, sides in self._rules.items()
            },
        }

    # =========================================================================
    # Cache Management
    # =========================================================================

    def _rebuild_caches(self) -> None:
        """Rebuild parsed rules and dependency caches."""
        self._parsed_cache.clear()
        self._dependents_cache.clear()

        for glyph, sides in self._rules.items():
            self._parsed_cache[glyph] = {}

            for side, rule in sides.items():
                try:
                    parsed = self._parser.parse(rule, side)
                    self._parsed_cache[glyph][side] = parsed

                    # Build reverse dependency
                    if parsed.source_glyph:
                        self._dependents_cache.setdefault(
                            parsed.source_glyph, set()
                        ).add(glyph)
                    elif parsed.is_symmetry:
                        # Symmetry rules (=|) depend on self (opposite side)
                        # Glyph is a dependent of itself
                        self._dependents_cache.setdefault(glyph, set()).add(glyph)
                except RuleParseError:
                    # Invalid rules will be reported in validation
                    pass

    # =========================================================================
    # Read Methods
    # =========================================================================

    def get_rule(self, glyph: str, side: str) -> str | None:
        """
        Get raw rule string for glyph/side.

        Args:
            glyph: Glyph name.
            side: "left" or "right".

        Returns:
            Rule string or None if no rule defined.
        """
        return self._rules.get(glyph, {}).get(side)

    def get_rules_for_glyph(self, glyph: str) -> dict[str, str] | None:
        """
        Get all rules for a glyph.

        Args:
            glyph: Glyph name.

        Returns:
            Dict like {"left": "=A", "right": "=A"} or None if no rules.
        """
        rules = self._rules.get(glyph)
        return dict(rules) if rules else None

    def get_all_rules(self) -> dict[str, dict[str, str]]:
        """
        Get copy of all rules.

        Returns:
            Dict of all rules: {glyph: {side: rule}}.
        """
        return {
            glyph: dict(sides) for glyph, sides in self._rules.items()
        }

    def get_dependents(self, glyph: str) -> set[str]:
        """
        Get glyphs that depend on this glyph.

        Args:
            glyph: Source glyph name.

        Returns:
            Set of glyph names that have rules referencing this glyph.
        """
        return self._dependents_cache.get(glyph, set()).copy()

    def get_dependencies(self, glyph: str) -> set[str]:
        """
        Get glyphs this glyph depends on.

        Args:
            glyph: Glyph name.

        Returns:
            Set of glyph names that this glyph's rules reference.
        """
        result = set()
        parsed_sides = self._parsed_cache.get(glyph, {})
        for parsed in parsed_sides.values():
            if parsed.source_glyph:
                result.add(parsed.source_glyph)
        return result

    def has_rule(self, glyph: str, side: str | None = None) -> bool:
        """
        Check if glyph has a rule.

        Args:
            glyph: Glyph name.
            side: Optional side to check. If None, checks any side.

        Returns:
            True if rule exists.
        """
        if glyph not in self._rules:
            return False
        if side is None:
            return bool(self._rules[glyph])
        return side in self._rules[glyph]

    # =========================================================================
    # Modification Methods
    # =========================================================================

    def set_rule(self, glyph: str, side: str, rule: str) -> None:
        """
        Set a rule. Rebuilds caches and saves to font.

        Args:
            glyph: Glyph name.
            side: "left", "right", or "both".
            rule: Rule string (e.g., "=A", "=A+10").

        Raises:
            ValueError: If rule syntax is invalid.
        """
        # Validate syntax first
        is_valid, error = self._parser.validate_syntax(rule)
        if not is_valid:
            raise ValueError(f"Invalid rule syntax: {error}")

        if side == "both":
            self._rules.setdefault(glyph, {})["left"] = rule
            self._rules[glyph]["right"] = rule
        else:
            self._rules.setdefault(glyph, {})[side] = rule

        self._rebuild_caches()
        self._save_to_font()

    def remove_rule(self, glyph: str, side: str) -> str | None:
        """
        Remove a rule.

        Args:
            glyph: Glyph name.
            side: "left", "right", or "both".

        Returns:
            The removed rule string, or None if no rule existed.
            For "both", returns the left rule if it existed.
        """
        if glyph not in self._rules:
            return None

        if side == "both":
            old_left = self._rules[glyph].pop("left", None)
            self._rules[glyph].pop("right", None)
            old_rule = old_left
        else:
            old_rule = self._rules[glyph].pop(side, None)

        # Clean up empty glyph entry
        if not self._rules.get(glyph):
            del self._rules[glyph]

        if old_rule is not None:
            self._rebuild_caches()
            self._save_to_font()

        return old_rule

    def clear_rules_for_glyph(self, glyph: str) -> dict[str, str] | None:
        """
        Remove all rules for a glyph.

        Args:
            glyph: Glyph name.

        Returns:
            Dict of removed rules or None if no rules existed.
        """
        old_rules = self._rules.pop(glyph, None)
        if old_rules:
            self._rebuild_caches()
            self._save_to_font()
        return old_rules

    def clear_all_rules(self) -> dict[str, dict[str, str]]:
        """
        Remove all rules.

        Returns:
            Dict of all removed rules.
        """
        old_rules = self._rules.copy()
        self._rules.clear()
        self._rebuild_caches()
        self._save_to_font()
        return old_rules

    # =========================================================================
    # Validation
    # =========================================================================

    def validate(self) -> ValidationReport:
        """
        Validate all rules and return detailed report.

        Checks for:
        - Syntax errors
        - Circular dependencies
        - Missing referenced glyphs
        - Self-references

        Returns:
            ValidationReport with detailed results.
        """
        issues: list[RuleIssue] = []

        # Check for cycles
        for cycle in self._detect_cycles():
            issues.append(create_cycle_error(cycle))

        for glyph, sides in self._rules.items():
            for side, rule in sides.items():
                # Check parse errors
                is_valid, error = self._parser.validate_syntax(rule)
                if not is_valid:
                    issues.append(
                        create_parse_error(glyph, side, rule, error or "Unknown error")
                    )
                    continue

                parsed = self._parsed_cache.get(glyph, {}).get(side)
                if not parsed:
                    continue

                # Check self-reference (not symmetry)
                if (
                    parsed.source_glyph == glyph
                    and not parsed.is_symmetry
                    and parsed.source_side != SOURCE_SIDE_OPPOSITE
                ):
                    issues.append(create_self_reference_warning(glyph, side, rule))

                # Check missing glyph
                if parsed.source_glyph and not self._glyph_exists(
                    parsed.source_glyph
                ):
                    issues.append(
                        create_missing_glyph_warning(
                            glyph, side, rule, parsed.source_glyph
                        )
                    )

        has_errors = any(i.is_error for i in issues)

        return ValidationReport(
            is_valid=not has_errors,
            issues=issues,
        )

    def _detect_cycles(self) -> list[list[str]]:
        """Detect circular dependencies using DFS."""
        cycles: list[list[str]] = []
        visited: set[str] = set()
        rec_stack: set[str] = set()
        path: list[str] = []

        def dfs(glyph: str) -> bool:
            """DFS to find cycles. Returns True if cycle found."""
            visited.add(glyph)
            rec_stack.add(glyph)
            path.append(glyph)

            # Get glyphs this glyph depends on
            for dep in self.get_dependencies(glyph):
                if dep not in visited:
                    if dfs(dep):
                        return True
                elif dep in rec_stack:
                    # Found cycle
                    cycle_start = path.index(dep)
                    cycle = path[cycle_start:] + [dep]
                    cycles.append(cycle)
                    return True

            path.pop()
            rec_stack.remove(glyph)
            return False

        # Check from each glyph that has rules
        for glyph in self._rules:
            if glyph not in visited:
                dfs(glyph)

        return cycles

    def _glyph_exists(self, glyph: str) -> bool:
        """Check if glyph exists in font."""
        try:
            return glyph in self._font
        except (TypeError, AttributeError):
            return False

    # =========================================================================
    # Evaluation
    # =========================================================================

    def evaluate(self, glyph: str, side: str) -> int | None:
        """
        Evaluate rule and return computed margin value.

        Args:
            glyph: Glyph name.
            side: "left" or "right".

        Returns:
            Computed margin value, or None if no rule or evaluation fails.
        """
        parsed = self._parsed_cache.get(glyph, {}).get(side)
        if not parsed:
            return None

        # Get source value
        if parsed.is_symmetry:
            # =| means RSB = LSB of same glyph (or vice versa)
            opposite_side = "left" if side == "right" else "right"
            source_value = self._get_margin(glyph, opposite_side)
        elif parsed.source_glyph:
            # Determine source side
            if parsed.source_side == SOURCE_SIDE_OPPOSITE:
                # =H| means target.left = source.right (or vice versa)
                source_side = "right" if side == "left" else "left"
            else:
                # Same side as target
                source_side = side
            source_value = self._get_margin(parsed.source_glyph, source_side)
        else:
            return None

        if source_value is None:
            return None

        # Apply operator
        if parsed.operator is None:
            return source_value

        if parsed.operand is None:
            return source_value

        if parsed.operator == "+":
            return round(source_value + parsed.operand)
        elif parsed.operator == "-":
            return round(source_value - parsed.operand)
        elif parsed.operator == "*":
            return round(source_value * parsed.operand)
        elif parsed.operator == "/":
            if parsed.operand == 0:
                return None
            return round(source_value / parsed.operand)

        return source_value

    def _get_margin(self, glyph: str, side: str) -> int | None:
        """Get margin value from font."""
        if not self._glyph_exists(glyph):
            return None

        try:
            g = self._font[glyph]
            if side == "left":
                return g.leftMargin
            else:
                return g.rightMargin
        except (AttributeError, KeyError):
            return None

    # =========================================================================
    # Cascade Helpers
    # =========================================================================

    def get_cascade_order(self, glyph: str) -> list[str]:
        """
        Get ordered list of glyphs to update when glyph changes.

        Uses topological sort to ensure correct order - dependencies
        are processed before dependents.

        Args:
            glyph: Source glyph that changed.

        Returns:
            List of dependent glyph names in correct update order.
            Includes the source glyph itself if it has symmetry rules.
        """
        result: list[str] = []
        visited: set[str] = set()

        def visit(g: str) -> None:
            if g in visited:
                return
            visited.add(g)

            # First visit all dependents recursively
            for dep in self.get_dependents(g):
                visit(dep)

            # Add to result (will be reversed)
            result.append(g)

        # Start from direct dependents
        for dep in self.get_dependents(glyph):
            visit(dep)

        # Reverse to get correct order (dependencies first)
        result.reverse()

        # Check if source glyph has symmetry rules (=|)
        # If so, keep it in the cascade order
        has_symmetry = glyph in self.get_dependents(glyph)

        if has_symmetry:
            return result
        else:
            # Remove the source glyph if it got included but doesn't have symmetry
            return [g for g in result if g != glyph]

    def get_affected_glyphs(
        self, glyph: str, side: str | None = None
    ) -> set[str]:
        """
        Get all glyphs that would be affected by changing a glyph's margin.

        This includes direct dependents and all transitive dependents.

        Args:
            glyph: Glyph name.
            side: Optional side filter.

        Returns:
            Set of affected glyph names.
        """
        result: set[str] = set()
        to_visit = [glyph]

        while to_visit:
            current = to_visit.pop()
            for dep in self.get_dependents(current):
                if dep not in result:
                    result.add(dep)
                    to_visit.append(dep)

        return result

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def __repr__(self) -> str:
        """Return string representation."""
        rule_count = sum(len(sides) for sides in self._rules.values())
        return f"MetricsRulesManager(rules={rule_count})"

    def __len__(self) -> int:
        """Return total number of rules."""
        return sum(len(sides) for sides in self._rules.values())

    def __bool__(self) -> bool:
        """Return True if any rules exist."""
        return len(self._rules) > 0
