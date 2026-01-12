"""
Metrics Rules Commands.

This module provides commands for managing metrics rules with full
undo/redo support.

Commands:
    SetMetricsRuleCommand: Set or update a metrics rule
    RemoveMetricsRuleCommand: Remove a metrics rule

Example:
    >>> from ufo_spacing_lib import SpacingEditor, SetMetricsRuleCommand
    >>>
    >>> editor = SpacingEditor(font)
    >>> cmd = SetMetricsRuleCommand("Aacute", "left", "=A")
    >>> editor.execute(cmd)
    >>>
    >>> editor.undo()  # Restores previous rule state
"""

from __future__ import annotations

from ..contexts import FontContext
from ..rules_manager import MetricsRulesManager
from .base import Command, CommandResult


class SetMetricsRuleCommand(Command):
    """
    Command to set or update a metrics rule.

    Sets a rule for a glyph's margin. If a rule already exists, it will
    be overwritten. Supports undo to restore previous state.

    Attributes:
        glyph: Glyph name to set rule for.
        side: Side to set rule for ("left", "right", or "both").
        rule: Rule string (e.g., "=A", "=A+10", "=|").

    Example:
        >>> cmd = SetMetricsRuleCommand("Aacute", "left", "=A")
        >>> result = editor.execute(cmd)
        >>>
        >>> # Set both sides at once
        >>> cmd = SetMetricsRuleCommand("Agrave", "both", "=A")
    """

    def __init__(self, glyph: str, side: str, rule: str):
        """
        Initialize the command.

        Args:
            glyph: Glyph name to set rule for.
            side: Side to set rule for ("left", "right", or "both").
            rule: Rule string (e.g., "=A", "=A+10").
        """
        self.glyph = glyph
        self.side = side
        self.rule = rule
        # Previous rules per font for undo: {font_id: {side: rule} | None}
        self._previous_rules: dict[int, dict[str, str] | None] = {}

    @property
    def description(self) -> str:
        """Human-readable description of the command."""
        if self.side == "both":
            return f"Set rule {self.glyph} = '{self.rule}'"
        return f"Set rule {self.glyph}.{self.side} = '{self.rule}'"

    def execute(
        self,
        context: FontContext,
        rules_managers: dict[int, MetricsRulesManager] | None = None,
    ) -> CommandResult:
        """
        Execute the command.

        Args:
            context: Font context containing fonts to operate on.
            rules_managers: Dict mapping font id to MetricsRulesManager.

        Returns:
            CommandResult indicating success or failure.
        """
        if rules_managers is None:
            return CommandResult.error("Rules managers not provided")

        for font in context:
            font_id = id(font)
            manager = rules_managers.get(font_id)
            if manager is None:
                continue

            # Save previous state for undo
            self._previous_rules[font_id] = manager.get_rules_for_glyph(
                self.glyph
            )

            # Set new rule
            try:
                if self.side == "both":
                    manager.set_rule(self.glyph, "left", self.rule)
                    manager.set_rule(self.glyph, "right", self.rule)
                else:
                    manager.set_rule(self.glyph, self.side, self.rule)
            except ValueError as e:
                return CommandResult.error(str(e))

        return CommandResult.ok(f"Set rule for {self.glyph}")

    def undo(
        self,
        context: FontContext,
        rules_managers: dict[int, MetricsRulesManager] | None = None,
    ) -> CommandResult:
        """
        Undo the command, restoring previous rule state.

        Args:
            context: Font context containing fonts to operate on.
            rules_managers: Dict mapping font id to MetricsRulesManager.

        Returns:
            CommandResult indicating success.
        """
        if rules_managers is None:
            return CommandResult.error("Rules managers not provided")

        for font in context:
            font_id = id(font)
            manager = rules_managers.get(font_id)
            if manager is None:
                continue

            previous = self._previous_rules.get(font_id)

            # Clear current rules for glyph
            manager.clear_rules_for_glyph(self.glyph)

            # Restore previous rules if they existed
            if previous:
                for side, rule in previous.items():
                    manager.set_rule(self.glyph, side, rule)

        return CommandResult.ok(f"Restored rules for {self.glyph}")


class RemoveMetricsRuleCommand(Command):
    """
    Command to remove a metrics rule.

    Removes a rule for a glyph's margin. Supports undo to restore
    the removed rule.

    Attributes:
        glyph: Glyph name to remove rule from.
        side: Side to remove rule from ("left", "right", or "both").

    Example:
        >>> cmd = RemoveMetricsRuleCommand("Aacute", "left")
        >>> result = editor.execute(cmd)
        >>>
        >>> # Remove both sides at once
        >>> cmd = RemoveMetricsRuleCommand("Agrave", "both")
    """

    def __init__(self, glyph: str, side: str):
        """
        Initialize the command.

        Args:
            glyph: Glyph name to remove rule from.
            side: Side to remove rule from ("left", "right", or "both").
        """
        self.glyph = glyph
        self.side = side
        # Previous rules per font for undo
        self._previous_rules: dict[int, dict[str, str] | None] = {}

    @property
    def description(self) -> str:
        """Human-readable description of the command."""
        if self.side == "both":
            return f"Remove rules for {self.glyph}"
        return f"Remove rule {self.glyph}.{self.side}"

    def execute(
        self,
        context: FontContext,
        rules_managers: dict[int, MetricsRulesManager] | None = None,
    ) -> CommandResult:
        """
        Execute the command.

        Args:
            context: Font context containing fonts to operate on.
            rules_managers: Dict mapping font id to MetricsRulesManager.

        Returns:
            CommandResult indicating success or failure.
        """
        if rules_managers is None:
            return CommandResult.error("Rules managers not provided")

        for font in context:
            font_id = id(font)
            manager = rules_managers.get(font_id)
            if manager is None:
                continue

            # Save previous state for undo
            self._previous_rules[font_id] = manager.get_rules_for_glyph(
                self.glyph
            )

            # Remove rule(s)
            if self.side == "both":
                manager.clear_rules_for_glyph(self.glyph)
            else:
                manager.remove_rule(self.glyph, self.side)

        return CommandResult.ok(f"Removed rule for {self.glyph}")

    def undo(
        self,
        context: FontContext,
        rules_managers: dict[int, MetricsRulesManager] | None = None,
    ) -> CommandResult:
        """
        Undo the command, restoring removed rules.

        Args:
            context: Font context containing fonts to operate on.
            rules_managers: Dict mapping font id to MetricsRulesManager.

        Returns:
            CommandResult indicating success.
        """
        if rules_managers is None:
            return CommandResult.error("Rules managers not provided")

        for font in context:
            font_id = id(font)
            manager = rules_managers.get(font_id)
            if manager is None:
                continue

            previous = self._previous_rules.get(font_id)

            # Restore previous rules if they existed
            if previous:
                for side, rule in previous.items():
                    manager.set_rule(self.glyph, side, rule)

        return CommandResult.ok(f"Restored rules for {self.glyph}")
