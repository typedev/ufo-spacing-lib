"""
Margins Commands.

This module contains all commands for glyph margins operations.

Commands:
    - SetMarginCommand: Set margin to an absolute value
    - AdjustMarginCommand: Adjust margin by a delta value

Both commands are thin wrappers over the margin planner
(`ufo_spacing_lib.planner`): they plan the edit for each font in the
context, apply the plan and keep it so undo can apply the inverted plan.

Features:
    - Support for left and right margins
    - Composites built on an edited glyph stay intact (transform-aware
      compensation, always on)
    - Per-font scaling for interpolation-aware editing
    - Automatic application of metrics rules with cascade
    - Full undo/redo capability

Example:
    Basic margin adjustment:

    >>> from ufo_spacing_lib import SpacingEditor, AdjustMarginCommand
    >>>
    >>> editor = SpacingEditor(font)
    >>>
    >>> # Increase left margin by 10 units (rules apply by default)
    >>> cmd = AdjustMarginCommand(
    ...     glyph_name='A',
    ...     side='left',
    ...     delta=10,
    ... )
    >>> editor.execute(cmd)
    >>>
    >>> # Without rules application
    >>> cmd = AdjustMarginCommand('B', 'left', 10, apply_rules=False)
    >>> editor.execute(cmd)
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..contexts import FontContext
from ..margins_utils import get_italic_angle
from ..planner import Plan, angled_margins, apply_plan, plan_margin_edit
from .base import Command, CommandResult

if TYPE_CHECKING:
    from ..rules_manager import MetricsRulesManager

# Side constants
SIDE_LEFT = 'left'
SIDE_RIGHT = 'right'


def _warn_deprecated_propagation(command: Any) -> None:
    if not command.propagate_to_composites or command.recursive_propagate:
        warnings.warn(
            "propagate_to_composites and recursive_propagate have no effect "
            "since 0.5.0: composites built on an edited glyph are always "
            "kept in place, and follow only through metrics rules.",
            DeprecationWarning,
            stacklevel=3,
        )


class _MarginCommandMixin:
    """Shared execute/undo over the planner."""

    glyph_name: str
    side: str
    apply_rules: bool
    _plans: dict[int, Plan]

    def _plan(
        self,
        context: FontContext,
        font: Any,
        rules_manager: MetricsRulesManager | None,
    ) -> Plan:
        raise NotImplementedError

    def plan_for(
        self,
        font: Any,
        context: FontContext | None = None,
        rules_manager: MetricsRulesManager | None = None,
    ) -> Plan:
        """
        Plan what this command would do to one font, without mutating it.

        Args:
            font: Font (or layer) to plan for.
            context: Context used for per-font scaling. Defaults to a
                single-font context with scale 1.
            rules_manager: Rules to cascade; ignored when apply_rules is False.

        Returns:
            The Plan `execute` would apply to this font.
        """
        if context is None:
            context = FontContext.from_single_font(font)
        return self._plan(context, font, rules_manager if self.apply_rules else None)

    def _run(
        self,
        context: FontContext,
        rules_managers: dict[int, MetricsRulesManager] | None,
    ) -> CommandResult:
        warning_messages: list[str] = []
        affected: list[str] = []
        self._plans = {}

        for font in context:
            if self.glyph_name not in font:
                continue
            rules_manager = None
            if self.apply_rules and rules_managers is not None:
                rules_manager = rules_managers.get(id(font))

            plan = self._plan(context, font, rules_manager)
            apply_plan(font, plan)
            self._plans[id(font)] = plan

            warning_messages.extend(str(issue) for issue in plan.issues)
            for name in plan.ordered_names:
                if name not in affected:
                    affected.append(name)

        if not affected:
            affected.append(self.glyph_name)
        return CommandResult.ok(
            message=self.description,  # type: ignore[attr-defined]
            warnings=warning_messages,
            affected_glyphs=affected,
        )

    def _undo(self, context: FontContext) -> CommandResult:
        for font in context:
            plan = self._plans.get(id(font))
            if plan is not None:
                apply_plan(font, plan.inverted())
        self._plans = {}
        return CommandResult.ok(f"Undid: {self.description}")  # type: ignore[attr-defined]


@dataclass
class SetMarginCommand(_MarginCommandMixin, Command):
    """
    Command to set a glyph margin to an absolute value.

    Sets the left or right margin of a glyph to a specific value.
    Composites built on the glyph stay in place; glyphs with metrics
    rules depending on it are updated through the rules cascade.

    Attributes:
        glyph_name: Name of the glyph to modify.
        side: Which margin to set - 'left' or 'right'.
        value: The margin value to set.
        value_is_angled: If True, the value is an angled (visual) margin,
            measured along the font's italic angle. Default is False.
        propagate_to_composites: Deprecated, no effect since 0.5.0.
        recursive_propagate: Deprecated, no effect since 0.5.0.
        apply_rules: If True (default), applies metrics rules to glyphs
            that depend on this glyph.

    Example:
        >>> cmd = SetMarginCommand(glyph_name='A', side='left', value=50)
        >>> editor.execute(cmd)
        >>>
        >>> # Set angled margin (for italic UI)
        >>> cmd = SetMarginCommand('A', 'left', 50, value_is_angled=True)
        >>> editor.execute(cmd)

    Note:
        A glyph without outline has no margin to set: the command leaves
        it unchanged and reports a W11 warning.
    """

    glyph_name: str
    side: str  # 'left' or 'right'
    value: int
    value_is_angled: bool = False
    propagate_to_composites: bool = True
    recursive_propagate: bool = False
    apply_rules: bool = True
    _plans: dict[int, Plan] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        _warn_deprecated_propagation(self)

    @property
    def description(self) -> str:
        """
        Human-readable description of the command.

        Returns:
            String like "Set left margin A = 50"
        """
        return f"Set {self.side} margin {self.glyph_name} = {self.value}"

    def _plan(
        self,
        context: FontContext,
        font: Any,
        rules_manager: MetricsRulesManager | None,
    ) -> Plan:
        margins = None
        if self.value_is_angled:
            margins = angled_margins(font, get_italic_angle(font))
        return plan_margin_edit(
            font,
            self.glyph_name,
            self.side,
            value=context.scale_value(font, self.value),
            rules=rules_manager,
            margins=margins,
        )

    def execute(
        self,
        context: FontContext,
        rules_managers: dict[int, MetricsRulesManager] | None = None,
    ) -> CommandResult:
        """
        Set the margin value for the glyph in all context fonts.

        Args:
            context: FontContext with fonts (or layers) to modify.
            rules_managers: Optional dict of rules managers keyed by font id.

        Returns:
            CommandResult with rule issues as warnings.
        """
        return self._run(context, rules_managers)

    def undo(
        self,
        context: FontContext,
        rules_managers: dict[int, MetricsRulesManager] | None = None,
    ) -> CommandResult:
        """
        Restore every glyph the command changed, by applying the inverted plan.

        Args:
            context: FontContext (same as used in execute).
            rules_managers: Not used, kept for API consistency.

        Returns:
            CommandResult indicating success.
        """
        return self._undo(context)


@dataclass
class AdjustMarginCommand(_MarginCommandMixin, Command):
    """
    Command to adjust a glyph margin by a delta value.

    Adds the delta to the current margin value. This is the most
    common operation when using keyboard shortcuts to adjust spacing.
    Composites built on the glyph stay in place; glyphs with metrics
    rules depending on it are updated through the rules cascade.

    Attributes:
        glyph_name: Name of the glyph to modify.
        side: Which margin to adjust - 'left' or 'right'.
        delta: The amount to add (negative to decrease).
        propagate_to_composites: Deprecated, no effect since 0.5.0.
        recursive_propagate: Deprecated, no effect since 0.5.0.
        apply_rules: If True (default), applies metrics rules to glyphs
            that depend on this glyph.

    Example:
        >>> cmd = AdjustMarginCommand(glyph_name='A', side='right', delta=-5)
        >>> editor.execute(cmd)

    Note:
        For glyphs without outline (like /space), the delta changes the
        glyph width.
    """

    glyph_name: str
    side: str  # 'left' or 'right'
    delta: int
    propagate_to_composites: bool = True
    recursive_propagate: bool = False
    apply_rules: bool = True
    _plans: dict[int, Plan] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        _warn_deprecated_propagation(self)

    @property
    def description(self) -> str:
        """
        Human-readable description of the command.

        Returns:
            String like "Adjust left margin A +10"
        """
        sign = "+" if self.delta > 0 else ""
        return f"Adjust {self.side} margin {self.glyph_name} {sign}{self.delta}"

    def _plan(
        self,
        context: FontContext,
        font: Any,
        rules_manager: MetricsRulesManager | None,
    ) -> Plan:
        return plan_margin_edit(
            font,
            self.glyph_name,
            self.side,
            delta=context.scale_value(font, self.delta),
            rules=rules_manager,
        )

    def execute(
        self,
        context: FontContext,
        rules_managers: dict[int, MetricsRulesManager] | None = None,
    ) -> CommandResult:
        """
        Adjust the margin value for the glyph in all context fonts.

        Args:
            context: FontContext with fonts (or layers) to modify.
            rules_managers: Optional dict of rules managers keyed by font id.

        Returns:
            CommandResult with rule issues as warnings.
        """
        return self._run(context, rules_managers)

    def undo(
        self,
        context: FontContext,
        rules_managers: dict[int, MetricsRulesManager] | None = None,
    ) -> CommandResult:
        """
        Restore every glyph the command changed, by applying the inverted plan.

        Args:
            context: FontContext (same as used in execute).
            rules_managers: Not used, kept for API consistency.

        Returns:
            CommandResult indicating success.
        """
        return self._undo(context)
