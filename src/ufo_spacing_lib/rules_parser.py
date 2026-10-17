"""
Metrics Rules Parser.

This module provides the RuleParser class for parsing metrics rule syntax
for linked sidebearings (metrics keys). The syntax is compatible with
Glyphs.app metrics keys.

Supported syntax:
    =A          Reference (same side)
    =A+10       Reference with arithmetic: + - * / and one number
    =A + 10     Spaces around the operator are allowed
    =|          Symmetry (this side = the opposite side of the same glyph)
    =|H         Opposite side of another glyph (target LSB = H's RSB)
    =|H+20      Opposite side with arithmetic
    =40         Constant (=-20 too)
    =H@200      Measured at a height: both the source and the target are
                measured along the line y = 200 (=H@200+5, =|H@200, =H@-50;
                "=H+5@200" is read as "=H@200+5")
    ==A         Glyphs "this master only" form, read as =A
    A           Bare name (Glyphs form), read as =A; no arithmetic
    =H|         Legacy opposite-side form, read as =|H

Glyph names may contain any character except whitespace and | ( ) @ = + * /
and must not start with "-". So "=a-cy" is the glyph "a-cy". A trailing
"op NUMBER" is always the operation: "=a-5" is "a" minus 5.

On the "width" side only references, arithmetic and constants are allowed,
without a height.

Glyphs.app forms that are not supported give a parse error with a reason:
auto-alignment offsets (=+10), expressions with parentheses or several
glyphs (=H+O), symmetry at a height (=|@200).
"""

from __future__ import annotations

import re

from .rules_constants import SIDE_WIDTH, SOURCE_SIDE_OPPOSITE, SOURCE_SIDE_SAME
from .rules_core import ParsedRule

_NAME = r"[^\s|()@=+*/\-][^\s|()@=+*/]*"
_NUMBER = r"\d+(?:\.\d+)?|\.\d+"
_OPERATION = rf"\s*(?P<operator>[-+*/])\s*(?P<operand>{_NUMBER})"
_NUMBER_ONLY = re.compile(rf"^(?:{_NUMBER})$")
_HEIGHT = rf"\s*@\s*(?P<height>-?\s*(?:{_NUMBER}))"


def _height(text: str | None) -> float | None:
    return None if text is None else float(text.replace(" ", ""))


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

    # Body patterns, after the "=" / "==" prefix. The name is lazy, so a
    # trailing operation wins over a "-" inside the name.
    # Glyphs order: NAME @HEIGHT op NUM. Also accepted: NAME op NUM @HEIGHT.
    PATTERN_REFERENCE = re.compile(
        rf"^(?P<name>{_NAME}?)(?:{_HEIGHT})?(?:{_OPERATION})?$"
    )
    PATTERN_REFERENCE_OP_FIRST = re.compile(
        rf"^(?P<name>{_NAME}?)(?:{_OPERATION}){_HEIGHT}$"
    )
    PATTERN_OPPOSITE = re.compile(
        rf"^\|\s*(?P<name>{_NAME}?)(?:{_HEIGHT})?(?:{_OPERATION})?$"
    )
    PATTERN_OPPOSITE_OP_FIRST = re.compile(
        rf"^\|\s*(?P<name>{_NAME}?)(?:{_OPERATION}){_HEIGHT}$"
    )
    PATTERN_LEGACY_OPPOSITE = re.compile(rf"^(?P<name>{_NAME})\|$")
    PATTERN_CONSTANT = re.compile(rf"^(?P<sign>-?)\s*(?P<value>{_NUMBER})$")
    PATTERN_BARE_NAME = re.compile(rf"^(?P<name>{_NAME})(?:{_HEIGHT})?$")

    def parse(self, rule: str, target_side: str) -> ParsedRule:
        """
        Parse a rule string into a ParsedRule object.

        Args:
            rule: The rule string to parse (e.g., "=A+10").
            target_side: The side this rule is for ("left", "right" or
                "width"). Symmetry and opposite-side rules are errors on
                the width side.

        Returns:
            ParsedRule object representing the parsed rule.

        Raises:
            RuleParseError: If the rule syntax is invalid or unsupported.

        Examples:
            >>> parser = RuleParser()
            >>> parser.parse("=a-cy+10", "left").source_glyph
            'a-cy'
            >>> parser.parse("=|H", "left").source_side
            'opposite'
        """
        parsed = self._parse(rule)
        if target_side == SIDE_WIDTH and (
            parsed.is_symmetry or parsed.source_side == SOURCE_SIDE_OPPOSITE
        ):
            raise RuleParseError("Opposite-side rules are not allowed for width")
        if target_side == SIDE_WIDTH and parsed.at_height is not None:
            raise RuleParseError("Measuring at a height (@) is not allowed for width")
        return parsed

    def _parse(self, rule: str) -> ParsedRule:
        text = (rule or "").strip()
        if not text:
            raise RuleParseError("Empty rule")

        if text.startswith("="):
            body = text[2:] if text.startswith("==") else text[1:]
            body = body.strip()
            if not body:
                raise RuleParseError("Empty rule")
            return self._parse_body(body)

        # Bare key: a glyph name (or "|"), optionally @height, no arithmetic.
        if text == "|":
            return ParsedRule(source_glyph=None, source_side=SOURCE_SIDE_SAME, is_symmetry=True)
        self._reject_unsupported(text)
        match = self.PATTERN_BARE_NAME.match(text)
        if match and not _NUMBER_ONLY.match(match.group("name")):
            return ParsedRule(
                source_glyph=match.group("name"),
                source_side=SOURCE_SIDE_SAME,
                at_height=_height(match.group("height")),
            )
        raise RuleParseError(
            f"Invalid rule syntax: '{rule}' (a key without '=' must be a glyph name)"
        )

    def _parse_body(self, body: str) -> ParsedRule:
        if body == "|":
            return ParsedRule(source_glyph=None, source_side=SOURCE_SIDE_SAME, is_symmetry=True)

        self._reject_unsupported(body)

        match = self.PATTERN_CONSTANT.match(body)
        if match:
            value = float(match.group("value"))
            return ParsedRule(
                source_glyph=None,
                source_side=SOURCE_SIDE_SAME,
                constant=-value if match.group("sign") else value,
            )

        match = self.PATTERN_LEGACY_OPPOSITE.match(body)
        if match:
            return ParsedRule(
                source_glyph=match.group("name"), source_side=SOURCE_SIDE_OPPOSITE
            )

        opposite = body.startswith("|")
        if opposite:
            patterns = (self.PATTERN_OPPOSITE, self.PATTERN_OPPOSITE_OP_FIRST)
        else:
            patterns = (self.PATTERN_REFERENCE, self.PATTERN_REFERENCE_OP_FIRST)
        match = patterns[0].match(body) or patterns[1].match(body)
        if not match or not match.group("name"):
            raise RuleParseError(f"Invalid rule syntax: '={body}'")
        if _NUMBER_ONLY.match(match.group("name")):
            raise RuleParseError(f"Invalid rule syntax: '={body}' (a constant has no height)")
        operand = match.group("operand")
        return ParsedRule(
            source_glyph=match.group("name"),
            source_side=SOURCE_SIDE_OPPOSITE if opposite else SOURCE_SIDE_SAME,
            operator=match.group("operator"),
            operand=float(operand) if operand is not None else None,
            at_height=_height(match.group("height")),
        )

    @staticmethod
    def _reject_unsupported(body: str) -> None:
        """Raise a specific error for Glyphs forms the library does not support."""
        if body.startswith("|") and body[1:].lstrip().startswith("@"):
            raise RuleParseError("Symmetry (=|) cannot be measured at a height")
        if re.match(rf"^\+\s*(?:{_NUMBER})$", body):
            raise RuleParseError(
                "Auto-alignment offsets (=+10) are not supported"
            )
        if "(" in body or ")" in body:
            raise RuleParseError("Expressions with parentheses are not supported")
        if body.startswith("|") and len(body) > 1 and body[1:].lstrip()[:1] in "+-*/":
            raise RuleParseError("Arithmetic on symmetry (=|+10) is not supported")

    def format(self, rule: str, target_side: str = "left") -> str:
        """
        Canonical text for a rule (also valid Glyphs.app syntax).

        Raises:
            RuleParseError: If the rule does not parse.
        """
        return self.parse(rule, target_side).format()

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
