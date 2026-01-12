"""
Metrics Rules Core Data Classes.

This module defines data classes for the metrics rules system including
parsed rules, validation results, and unified issue reporting.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# =============================================================================
# Issue Codes
# =============================================================================

# Severity levels
SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"

# Error codes (critical - block validation)
E_PARSE_ERROR = "E01"
E_CYCLE = "E02"

# Warning codes (non-critical)
W_MISSING_GLYPH = "W01"
W_SELF_REFERENCE = "W02"
W_COMPONENT_WIDER = "W03"
W_EXTENDS_LEFT = "W04"
W_EXTENDS_RIGHT = "W05"
W_ZERO_WIDTH = "W06"
W_MIXED_CONTOURS = "W07"
W_MISSING_BASE = "W08"

# Info codes
I_SINGLE_COMPONENT = "I01"

# Human-readable messages
ISSUE_MESSAGES = {
    E_PARSE_ERROR: "Parse error: {error}",
    E_CYCLE: "Circular dependency: {cycle}",
    W_MISSING_GLYPH: "References missing glyph: {missing}",
    W_SELF_REFERENCE: "Self-reference detected",
    W_COMPONENT_WIDER: "Component {index} wider than base",
    W_EXTENDS_LEFT: "Component {index} extends left of base",
    W_EXTENDS_RIGHT: "Component {index} extends right of base",
    W_ZERO_WIDTH: "Base component has zero width",
    W_MIXED_CONTOURS: "Glyph has both contours and components",
    W_MISSING_BASE: "Base component does not exist",
    I_SINGLE_COMPONENT: "Single component",
}


# =============================================================================
# Unified Issue Class
# =============================================================================


@dataclass
class RuleIssue:
    """
    Unified issue (error/warning/info) for rules system.

    Attributes:
        glyph: Glyph name the issue relates to.
        code: Issue code (E01, W01, I01, etc.).
        message: Human-readable message.
        severity: One of "error", "warning", "info".
        details: Additional context (side, rule, component, etc.).

    Example:
        >>> issue = RuleIssue(
        ...     glyph="Aacute",
        ...     code=W_MISSING_GLYPH,
        ...     message="References missing glyph: X",
        ...     severity=SEVERITY_WARNING,
        ...     details={"side": "left", "rule": "=X", "missing": "X"}
        ... )
    """

    glyph: str
    code: str
    message: str
    severity: str = SEVERITY_WARNING
    details: dict = field(default_factory=dict)

    def __str__(self) -> str:
        if "side" in self.details:
            return f"[{self.code}] {self.glyph}.{self.details['side']}: {self.message}"
        return f"[{self.code}] {self.glyph}: {self.message}"

    def __repr__(self) -> str:
        return f"RuleIssue({self.glyph!r}, {self.code!r}, {self.message!r})"

    @property
    def is_error(self) -> bool:
        """Check if this is a critical error."""
        return self.severity == SEVERITY_ERROR

    @property
    def is_warning(self) -> bool:
        """Check if this is a warning."""
        return self.severity == SEVERITY_WARNING

    @property
    def is_info(self) -> bool:
        """Check if this is informational."""
        return self.severity == SEVERITY_INFO


# =============================================================================
# Factory functions for creating issues
# =============================================================================


def create_parse_error(glyph: str, side: str, rule: str, error: str) -> RuleIssue:
    """Create a parse error issue."""
    return RuleIssue(
        glyph=glyph,
        code=E_PARSE_ERROR,
        message=ISSUE_MESSAGES[E_PARSE_ERROR].format(error=error),
        severity=SEVERITY_ERROR,
        details={"side": side, "rule": rule, "error": error},
    )


def create_cycle_error(cycle: list[str]) -> RuleIssue:
    """Create a cycle error issue."""
    cycle_str = " -> ".join(cycle)
    return RuleIssue(
        glyph=cycle[0] if cycle else "",
        code=E_CYCLE,
        message=ISSUE_MESSAGES[E_CYCLE].format(cycle=cycle_str),
        severity=SEVERITY_ERROR,
        details={"cycle": cycle},
    )


def create_missing_glyph_warning(
    glyph: str, side: str, rule: str, missing: str
) -> RuleIssue:
    """Create a missing glyph warning."""
    return RuleIssue(
        glyph=glyph,
        code=W_MISSING_GLYPH,
        message=ISSUE_MESSAGES[W_MISSING_GLYPH].format(missing=missing),
        severity=SEVERITY_WARNING,
        details={"side": side, "rule": rule, "missing": missing},
    )


def create_self_reference_warning(glyph: str, side: str, rule: str) -> RuleIssue:
    """Create a self-reference warning."""
    return RuleIssue(
        glyph=glyph,
        code=W_SELF_REFERENCE,
        message=ISSUE_MESSAGES[W_SELF_REFERENCE],
        severity=SEVERITY_WARNING,
        details={"side": side, "rule": rule},
    )


def create_component_wider_warning(
    glyph: str,
    index: int,
    component: str,
    component_width: float,
    base: str,
    base_width: float,
) -> RuleIssue:
    """Create a component wider than base warning."""
    return RuleIssue(
        glyph=glyph,
        code=W_COMPONENT_WIDER,
        message=ISSUE_MESSAGES[W_COMPONENT_WIDER].format(index=index),
        severity=SEVERITY_WARNING,
        details={
            "index": index,
            "component": component,
            "component_width": round(component_width),
            "base": base,
            "base_width": round(base_width),
        },
    )


def create_extends_left_warning(
    glyph: str, index: int, component: str, extends_by: float, base: str
) -> RuleIssue:
    """Create a component extends left warning."""
    return RuleIssue(
        glyph=glyph,
        code=W_EXTENDS_LEFT,
        message=ISSUE_MESSAGES[W_EXTENDS_LEFT].format(index=index),
        severity=SEVERITY_WARNING,
        details={
            "index": index,
            "component": component,
            "extends_by": round(extends_by),
            "base": base,
        },
    )


def create_extends_right_warning(
    glyph: str, index: int, component: str, extends_by: float, base: str
) -> RuleIssue:
    """Create a component extends right warning."""
    return RuleIssue(
        glyph=glyph,
        code=W_EXTENDS_RIGHT,
        message=ISSUE_MESSAGES[W_EXTENDS_RIGHT].format(index=index),
        severity=SEVERITY_WARNING,
        details={
            "index": index,
            "component": component,
            "extends_by": round(extends_by),
            "base": base,
        },
    )


def create_zero_width_warning(glyph: str, base: str) -> RuleIssue:
    """Create a zero width base warning."""
    return RuleIssue(
        glyph=glyph,
        code=W_ZERO_WIDTH,
        message=ISSUE_MESSAGES[W_ZERO_WIDTH],
        severity=SEVERITY_WARNING,
        details={"base": base, "width": 0},
    )


def create_mixed_contours_warning(glyph: str, components: list[str]) -> RuleIssue:
    """Create a mixed contours + components warning."""
    return RuleIssue(
        glyph=glyph,
        code=W_MIXED_CONTOURS,
        message=ISSUE_MESSAGES[W_MIXED_CONTOURS],
        severity=SEVERITY_WARNING,
        details={"components": components},
    )


def create_missing_base_warning(glyph: str, base: str) -> RuleIssue:
    """Create a missing base component warning."""
    return RuleIssue(
        glyph=glyph,
        code=W_MISSING_BASE,
        message=ISSUE_MESSAGES[W_MISSING_BASE],
        severity=SEVERITY_WARNING,
        details={"base": base},
    )


def create_single_component_info(glyph: str, base: str) -> RuleIssue:
    """Create a single component info."""
    return RuleIssue(
        glyph=glyph,
        code=I_SINGLE_COMPONENT,
        message=ISSUE_MESSAGES[I_SINGLE_COMPONENT],
        severity=SEVERITY_INFO,
        details={"base": base},
    )


# =============================================================================
# Parsed Rule
# =============================================================================


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


# =============================================================================
# Validation Report
# =============================================================================


@dataclass
class ValidationReport:
    """
    Result of validating all metrics rules.

    Attributes:
        is_valid: True if no critical errors (cycles, parse errors).
        issues: List of all issues (errors, warnings, info).

    Example:
        >>> report = manager.validate()
        >>> if not report.is_valid:
        ...     for error in report.errors:
        ...         print(f"Error: {error}")
        >>> for warning in report.warnings:
        ...     print(f"Warning: {warning}")
    """

    is_valid: bool = True
    issues: list[RuleIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[RuleIssue]:
        """Get all critical errors."""
        return [i for i in self.issues if i.is_error]

    @property
    def warnings(self) -> list[RuleIssue]:
        """Get all warnings."""
        return [i for i in self.issues if i.is_warning]

    @property
    def infos(self) -> list[RuleIssue]:
        """Get all info messages."""
        return [i for i in self.issues if i.is_info]

    @property
    def has_errors(self) -> bool:
        """Check if there are any critical errors."""
        return any(i.is_error for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return any(i.is_warning for i in self.issues)

    def get_issues_for_glyph(self, glyph: str) -> list[RuleIssue]:
        """Get all issues for a specific glyph."""
        return [i for i in self.issues if i.glyph == glyph]

    def get_issues_by_code(self, code: str) -> list[RuleIssue]:
        """Get all issues with a specific code."""
        return [i for i in self.issues if i.code == code]

    def __bool__(self) -> bool:
        """Returns True if validation passed (is_valid)."""
        return self.is_valid

    def __len__(self) -> int:
        """Return total number of issues."""
        return len(self.issues)


# =============================================================================
# Backwards Compatibility (deprecated)
# =============================================================================

# These classes are kept for backwards compatibility but are deprecated.
# Use RuleIssue instead.


@dataclass
class ParseError:
    """Deprecated: Use RuleIssue with code E_PARSE_ERROR instead."""

    glyph: str
    side: str
    rule: str
    error: str

    def __str__(self) -> str:
        return f"{self.glyph}.{self.side}: {self.error} (rule: '{self.rule}')"


@dataclass
class MissingGlyphWarning:
    """Deprecated: Use RuleIssue with code W_MISSING_GLYPH instead."""

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
    """Deprecated: Use RuleIssue with code E_CYCLE instead."""

    cycle: list[str]

    def __str__(self) -> str:
        return f"Circular dependency: {' -> '.join(self.cycle)}"


@dataclass
class SelfReferenceWarning:
    """Deprecated: Use RuleIssue with code W_SELF_REFERENCE instead."""

    glyph: str
    side: str
    rule: str

    def __str__(self) -> str:
        return (
            f"{self.glyph}.{self.side}: self-reference detected "
            f"(rule: '{self.rule}')"
        )
