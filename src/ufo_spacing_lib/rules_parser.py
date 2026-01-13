"""
Metrics Rules Parser.

This module provides the RuleParser class for parsing metrics rule syntax
for linked sidebearings (metrics keys).

Supported syntax:
    =A          Simple reference (same side)
    =A+10       Reference with addition
    =A-5        Reference with subtraction
    =A*1.5      Reference with multiplication
    =A/2        Reference with division
    =|          Symmetry (RSB = LSB of same glyph)
    =H|         Opposite side reference (target LSB = H's RSB)
"""

from __future__ import annotations

import re

from .rules_constants import SOURCE_SIDE_OPPOSITE, SOURCE_SIDE_SAME
from .rules_core import ParsedRule


class RuleParseError(ValueError):
    """Exception raised when rule parsing fails."""

    pass


class RuleParser:
    """
    Parser for metrics rule syntax.

    Parses rule strings into ParsedRule objects. Supports
    syntax with simple references, arithmetic operations, and symmetry.

    Example:
        >>> parser = RuleParser()
        >>> rule = parser.parse("=A+10", "left")
        >>> rule.source_glyph
        'A'
        >>> rule.operator
        '+'
        >>> rule.operand
        10.0
    """

    # Glyph name pattern: starts with letter or underscore, can contain
    # letters, numbers, underscores, and dots
    _GLYPH_NAME = r"[A-Za-z_][A-Za-z0-9_\.]*"

    # Regex patterns for different rule types
    # Order matters - more specific patterns first

    # =| (symmetry - RSB = LSB of same glyph)
    PATTERN_SYMMETRY = re.compile(r"^=\|$")

    # =H| (opposite side of another glyph)
    PATTERN_OPPOSITE = re.compile(rf"^=({_GLYPH_NAME})\|$")

    # =A+10, =A-5, =A*1.5, =A/2 (reference with arithmetic)
    PATTERN_ARITHMETIC = re.compile(
        rf"^=({_GLYPH_NAME})([\+\-\*/])(\d+(?:\.\d+)?)$"
    )

    # =A (simple reference)
    PATTERN_SIMPLE = re.compile(rf"^=({_GLYPH_NAME})$")

    def parse(self, rule: str, target_side: str) -> ParsedRule:
        """
        Parse a rule string into a ParsedRule object.

        Args:
            rule: The rule string to parse (e.g., "=A+10").
            target_side: The side this rule is for ("left" or "right").
                Used to determine source side for symmetry rules.

        Returns:
            ParsedRule object representing the parsed rule.

        Raises:
            RuleParseError: If the rule syntax is invalid.

        Examples:
            >>> parser = RuleParser()
            >>> parser.parse("=A", "left")
            ParsedRule(source_glyph='A', source_side='same', ...)

            >>> parser.parse("=|", "right")
            ParsedRule(source_glyph=None, is_symmetry=True, ...)
        """
        if not rule:
            raise RuleParseError("Empty rule")

        if not rule.startswith("="):
            raise RuleParseError("Rule must start with '='")

        # Try symmetry pattern: =|
        if self.PATTERN_SYMMETRY.match(rule):
            return ParsedRule(
                source_glyph=None,
                source_side=SOURCE_SIDE_SAME,
                is_symmetry=True,
            )

        # Try opposite side pattern: =H|
        match = self.PATTERN_OPPOSITE.match(rule)
        if match:
            return ParsedRule(
                source_glyph=match.group(1),
                source_side=SOURCE_SIDE_OPPOSITE,
            )

        # Try arithmetic pattern: =A+10
        match = self.PATTERN_ARITHMETIC.match(rule)
        if match:
            glyph_name = match.group(1)
            operator = match.group(2)
            operand = float(match.group(3))
            return ParsedRule(
                source_glyph=glyph_name,
                source_side=SOURCE_SIDE_SAME,
                operator=operator,
                operand=operand,
            )

        # Try simple pattern: =A
        match = self.PATTERN_SIMPLE.match(rule)
        if match:
            return ParsedRule(
                source_glyph=match.group(1),
                source_side=SOURCE_SIDE_SAME,
            )

        # No pattern matched
        raise RuleParseError(f"Invalid rule syntax: '{rule}'")

    def validate_syntax(self, rule: str) -> tuple[bool, str | None]:
        """
        Check if a rule has valid syntax without raising exceptions.

        Args:
            rule: The rule string to validate.

        Returns:
            Tuple of (is_valid, error_message).
            If valid, error_message is None.

        Example:
            >>> parser = RuleParser()
            >>> parser.validate_syntax("=A+10")
            (True, None)
            >>> parser.validate_syntax("invalid")
            (False, "Rule must start with '='")
        """
        try:
            self.parse(rule, "left")  # target_side doesn't matter for validation
            return (True, None)
        except RuleParseError as e:
            return (False, str(e))

    def extract_referenced_glyph(self, rule: str) -> str | None:
        """
        Extract the glyph name referenced by a rule.

        Args:
            rule: The rule string.

        Returns:
            The referenced glyph name, or None for symmetry rules
            or invalid rules.

        Example:
            >>> parser = RuleParser()
            >>> parser.extract_referenced_glyph("=A+10")
            'A'
            >>> parser.extract_referenced_glyph("=|")
            None
        """
        try:
            parsed = self.parse(rule, "left")
            return parsed.source_glyph
        except RuleParseError:
            return None
