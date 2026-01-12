"""
Metrics Rules Core Data Classes.

This module defines data classes for the metrics rules system including
parsed rules and validation results.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ParsedRule:
    """
    Parsed metrics rule.

    Represents a parsed rule with all components extracted from the rule string.

    Attributes:
        source_glyph: Glyph to get value from. None for symmetry (=|).
        source_side: Which side of source to use: "same", "opposite".
        operator: Arithmetic operator: None, "+", "-", "*", "/".
        operand: Value for arithmetic operation.
        is_symmetry: True for =| pattern (RSB = LSB of same glyph).

    Examples:
        "=A"     -> ParsedRule(source_glyph="A", source_side="same", ...)
        "=A+10"  -> ParsedRule(source_glyph="A", operator="+", operand=10, ...)
        "=|"     -> ParsedRule(source_glyph=None, is_symmetry=True, ...)
        "=H|"    -> ParsedRule(source_glyph="H", source_side="opposite", ...)
    """

    source_glyph: str | None
    source_side: str  # "same" or "opposite"
    operator: str | None = None
    operand: float | None = None
    is_symmetry: bool = False


@dataclass
class ParseError:
    """
    Rule parsing error.

    Attributes:
        glyph: Glyph the rule is defined for.
        side: Side the rule is defined for ("left" or "right").
        rule: The raw rule string that failed to parse.
        error: Description of the parsing error.
    """

    glyph: str
    side: str
    rule: str
    error: str

    def __str__(self) -> str:
        return f"{self.glyph}.{self.side}: {self.error} (rule: '{self.rule}')"


@dataclass
class MissingGlyphWarning:
    """
    Warning for rule referencing a non-existent glyph.

    Attributes:
        glyph: Glyph the rule is defined for.
        side: Side the rule is defined for.
        rule: The raw rule string.
        missing_glyph: The glyph referenced that doesn't exist.
    """

    glyph: str
    side: str
    rule: str
    missing_glyph: str

    def __str__(self) -> str:
        return (
            f"{self.glyph}.{self.side}: references missing glyph "
            f"'{self.missing_glyph}' (rule: '{self.rule}')"
        )


@dataclass
class CycleError:
    """
    Error for circular dependency in rules.

    Attributes:
        cycle: List of glyphs forming the cycle, e.g. ["A", "B", "C", "A"].
    """

    cycle: list[str]

    def __str__(self) -> str:
        return f"Circular dependency: {' -> '.join(self.cycle)}"


@dataclass
class SelfReferenceWarning:
    """
    Warning for rule that references the same glyph (non-symmetry).

    Attributes:
        glyph: Glyph the rule is defined for.
        side: Side the rule is defined for.
        rule: The raw rule string.
    """

    glyph: str
    side: str
    rule: str

    def __str__(self) -> str:
        return (
            f"{self.glyph}.{self.side}: self-reference detected "
            f"(rule: '{self.rule}')"
        )


@dataclass
class ValidationReport:
    """
    Result of validating all metrics rules.

    Attributes:
        is_valid: True if no critical errors (cycles, parse errors).
        cycles: List of detected circular dependencies.
        missing_glyphs: List of warnings for missing referenced glyphs.
        parse_errors: List of syntax errors in rules.
        self_references: List of self-reference warnings.

    Example:
        >>> report = manager.validate()
        >>> if not report.is_valid:
        ...     for error in report.errors:
        ...         print(f"Error: {error}")
        >>> for warning in report.warnings:
        ...     print(f"Warning: {warning}")
    """

    is_valid: bool
    cycles: list[CycleError] = field(default_factory=list)
    missing_glyphs: list[MissingGlyphWarning] = field(default_factory=list)
    parse_errors: list[ParseError] = field(default_factory=list)
    self_references: list[SelfReferenceWarning] = field(default_factory=list)

    @property
    def errors(self) -> list[str]:
        """Get all critical errors as strings."""
        result = []
        for cycle in self.cycles:
            result.append(str(cycle))
        for parse_error in self.parse_errors:
            result.append(str(parse_error))
        return result

    @property
    def warnings(self) -> list[str]:
        """Get all warnings as strings."""
        result = []
        for missing in self.missing_glyphs:
            result.append(str(missing))
        for self_ref in self.self_references:
            result.append(str(self_ref))
        return result

    @property
    def has_errors(self) -> bool:
        """Check if there are any critical errors."""
        return len(self.cycles) > 0 or len(self.parse_errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return len(self.missing_glyphs) > 0 or len(self.self_references) > 0

    def __bool__(self) -> bool:
        """Returns True if validation passed (is_valid)."""
        return self.is_valid
