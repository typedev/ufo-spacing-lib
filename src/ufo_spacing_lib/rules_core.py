"""
Metrics Rules Core Data Classes.

This module defines data classes for the metrics rules system including
parsed rules, validation results, and unified issue reporting.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# A glyph name ending like an operation: "a-5", "uni0410-1"
_TRAILING_NUMBER = re.compile(r"-\s*(?:\d+(?:\.\d+)?|\.\d+)$")

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
W_MULTI_BODY = "W09"
W_RULE_OVERRIDDEN = "W10"
W_EMPTY_GLYPH = "W11"
W_EVALUATION_FAILED = "W12"
W_AMBIGUOUS_NAME = "W13"
W_WIDTH_RIGHT_CONFLICT = "W14"
W_NO_OUTLINE_AT_HEIGHT = "W15"
W_READER_NO_HEIGHT = "W16"
W_MANUAL_MISSING_GLYPH = "W17"

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
    W_MULTI_BODY: "Outermost components differ from component 0",
    W_RULE_OVERRIDDEN: "Edit overrides rule {rule}",
    W_EMPTY_GLYPH: "{role} glyph {name} has no outline",
    W_EVALUATION_FAILED: "Rule cannot be evaluated: {error}",
    W_AMBIGUOUS_NAME: "Read as {name} {operator} {operand}, but glyph {glyph_name} exists",
    W_WIDTH_RIGHT_CONFLICT: "Right rule is ignored: the width rule takes precedence",
    W_NO_OUTLINE_AT_HEIGHT: "{role} glyph {name} has no outline at height {height}",
    W_READER_NO_HEIGHT: "The margin reader cannot measure at a height",
    W_MANUAL_MISSING_GLYPH: "Manual marker on a missing glyph",
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


def create_multi_body_warning(
    glyph: str,
    default: dict[str, str],
    geometric: dict[str, str],
    left_component: int,
    right_component: int,
) -> RuleIssue:
    """Create a multi-body candidate warning.

    Raised when the component with the smallest xMin or the largest xMax
    is not component 0. Both proposals are included so a UI can offer a
    choice per side.
    """
    return RuleIssue(
        glyph=glyph,
        code=W_MULTI_BODY,
        message=ISSUE_MESSAGES[W_MULTI_BODY],
        severity=SEVERITY_WARNING,
        details={
            "default": dict(default),
            "geometric": dict(geometric),
            "left_component": left_component,
            "right_component": right_component,
        },
    )


def create_rule_overridden_warning(
    glyph: str, side: str, rule: str, expected: float | None, actual: float | None
) -> RuleIssue:
    """Create a warning for a direct edit that overrides the glyph's rule."""
    return RuleIssue(
        glyph=glyph,
        code=W_RULE_OVERRIDDEN,
        message=ISSUE_MESSAGES[W_RULE_OVERRIDDEN].format(rule=rule),
        severity=SEVERITY_WARNING,
        details={"side": side, "rule": rule, "expected": expected, "actual": actual},
    )


def create_empty_glyph_warning(
    glyph: str, side: str, rule: str | None, name: str, role: str
) -> RuleIssue:
    """Create a warning for a glyph without outline in a margin operation.

    Args:
        glyph: Glyph the operation was for.
        side: Side of the operation.
        rule: Rule text, or None for a direct edit.
        name: The glyph that has no outline.
        role: "target" or "source".
    """
    return RuleIssue(
        glyph=glyph,
        code=W_EMPTY_GLYPH,
        message=ISSUE_MESSAGES[W_EMPTY_GLYPH].format(
            role=role.capitalize(), name=name
        ),
        severity=SEVERITY_WARNING,
        details={"side": side, "rule": rule, "name": name, "role": role},
    )


def create_evaluation_failed_warning(
    glyph: str, side: str, rule: str, error: str
) -> RuleIssue:
    """Create a warning for a rule that parses but cannot be evaluated."""
    return RuleIssue(
        glyph=glyph,
        code=W_EVALUATION_FAILED,
        message=ISSUE_MESSAGES[W_EVALUATION_FAILED].format(error=error),
        severity=SEVERITY_WARNING,
        details={"side": side, "rule": rule, "error": error},
    )


def create_ambiguous_name_warning(
    glyph: str, side: str, rule: str, parsed: ParsedRule, glyph_name: str
) -> RuleIssue:
    """Create a warning for "=a-5" when a glyph named "a-5" exists."""
    return RuleIssue(
        glyph=glyph,
        code=W_AMBIGUOUS_NAME,
        message=ISSUE_MESSAGES[W_AMBIGUOUS_NAME].format(
            name=parsed.source_glyph,
            operator=parsed.operator,
            operand=format_number(parsed.operand or 0),
            glyph_name=glyph_name,
        ),
        severity=SEVERITY_WARNING,
        details={"side": side, "rule": rule, "glyph_name": glyph_name},
    )


def create_width_right_conflict_warning(
    glyph: str, width_rule: str, right_rule: str
) -> RuleIssue:
    """Create a warning for a glyph with both a width and a right rule."""
    return RuleIssue(
        glyph=glyph,
        code=W_WIDTH_RIGHT_CONFLICT,
        message=ISSUE_MESSAGES[W_WIDTH_RIGHT_CONFLICT],
        severity=SEVERITY_WARNING,
        details={"side": "right", "rule": right_rule, "width_rule": width_rule},
    )


def create_no_outline_at_height_warning(
    glyph: str, side: str, rule: str, name: str, role: str, height: float
) -> RuleIssue:
    """Create a warning for a beam (=H@200) that misses a glyph's outline."""
    return RuleIssue(
        glyph=glyph,
        code=W_NO_OUTLINE_AT_HEIGHT,
        message=ISSUE_MESSAGES[W_NO_OUTLINE_AT_HEIGHT].format(
            role=role.capitalize(), name=name, height=format_number(height)
        ),
        severity=SEVERITY_WARNING,
        details={
            "side": side,
            "rule": rule,
            "name": name,
            "role": role,
            "height": height,
        },
    )


def create_reader_no_height_warning(
    glyph: str, side: str, rule: str, height: float
) -> RuleIssue:
    """Create a warning for a rule with a height and a 2-argument reader."""
    return RuleIssue(
        glyph=glyph,
        code=W_READER_NO_HEIGHT,
        message=ISSUE_MESSAGES[W_READER_NO_HEIGHT],
        severity=SEVERITY_WARNING,
        details={"side": side, "rule": rule, "height": height},
    )


def create_manual_missing_glyph_warning(glyph: str, sides: list[str]) -> RuleIssue:
    """Create a warning for a manual marker on a glyph not in the source."""
    return RuleIssue(
        glyph=glyph,
        code=W_MANUAL_MISSING_GLYPH,
        message=ISSUE_MESSAGES[W_MANUAL_MISSING_GLYPH],
        severity=SEVERITY_WARNING,
        details={"sides": list(sides)},
    )


def format_number(value: float) -> str:
    """Shortest text for a rule number: 10, 1.5, -20."""
    value = float(value)
    if value.is_integer():
        return str(int(value))
    return repr(value)


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
        constant: Fixed value for =40 (no source glyph).
        at_height: For =H@200: both glyphs are measured at y = 200.

    Examples:
        "=A"     -> ParsedRule(source_glyph="A", source_side="same", ...)
        "=A+10"  -> ParsedRule(source_glyph="A", operator="+", operand=10, ...)
        "=|"     -> ParsedRule(source_glyph=None, is_symmetry=True, ...)
        "=|H"    -> ParsedRule(source_glyph="H", source_side="opposite", ...)
        "=40"    -> ParsedRule(source_glyph=None, constant=40, ...)
    """

    source_glyph: str | None
    source_side: str  # "same" or "opposite"
    operator: str | None = None
    operand: float | None = None
    is_symmetry: bool = False
    constant: float | None = None
    at_height: float | None = None

    @property
    def is_constant(self) -> bool:
        """True for a fixed value (=40)."""
        return self.constant is not None

    def source_side_for(self, target_side: str) -> str:
        """Side of the source glyph this rule reads for ``target_side``."""
        if target_side == "width":
            return "width"
        opposite = "right" if target_side == "left" else "left"
        if self.is_symmetry or self.source_side == "opposite":
            return opposite
        return target_side

    def format(self) -> str:
        """
        Canonical rule text, which is also valid Glyphs.app syntax.

        Examples: "=A", "=A+10", "=|A", "=|A+20", "=|", "=40",
        "=A@200+5", "=|A@-50".
        """
        if self.constant is not None:
            return "=" + format_number(self.constant)
        if self.is_symmetry:
            return "=|"
        name = self.source_glyph or ""
        has_operation = self.operator is not None and self.operand is not None
        if self.at_height is not None:
            name += "@" + format_number(self.at_height)
        elif not has_operation and _TRAILING_NUMBER.search(name):
            # "=a-5" would read as "a" minus 5; spell the glyph "a-5" so
            # that it reads back as the same glyph.
            return f"={name}|" if self.source_side == "opposite" else name
        text = ("=|" if self.source_side == "opposite" else "=") + name
        if has_operation:
            text += f"{self.operator}{format_number(self.operand or 0)}"
        return text

    def apply(self, value: float) -> float | None:
        """
        Apply the rule's arithmetic to a source margin, without rounding.

        Returns:
            The computed margin, or None for a division by zero.
        """
        if self.operator is None or self.operand is None:
            return value
        if self.operator == "+":
            return value + self.operand
        if self.operator == "-":
            return value - self.operand
        if self.operator == "*":
            return value * self.operand
        if self.operator == "/":
            if self.operand == 0:
                return None
            return value / self.operand
        return value


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
