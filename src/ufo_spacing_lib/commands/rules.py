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


class SyncRulesCommand(Command):
    """
    Command to synchronize all rules (batch apply).

    This command applies all metrics rules to their dependent glyphs.
    Use this when you've made multiple margin changes with apply_rules=False
    and want to synchronize all dependents in one operation.

    The command:
    1. Collects all affected glyphs via topological sort
    2. Applies rules in correct dependency order
    3. Supports full undo

    Attributes:
        source_glyphs: Optional list of glyphs that changed. If None,
            syncs all glyphs that have dependents.

    Example:
        >>> # Make changes without triggering rules
        >>> editor.execute(AdjustMarginCommand("A", "left", 10, apply_rules=False))
        >>> editor.execute(AdjustMarginCommand("H", "left", 5, apply_rules=False))
        >>>
        >>> # Sync all rules at once
        >>> editor.execute(SyncRulesCommand(["A", "H"]))
        >>>
        >>> # Or sync everything
        >>> editor.execute(SyncRulesCommand())
    """

    def __init__(self, source_glyphs: list[str] | None = None):
        """
        Initialize the command.

        Args:
            source_glyphs: Optional list of glyphs that changed.
                If None, syncs all glyphs with dependents.
        """
        self.source_glyphs = source_glyphs
        # Previous margin values per font for undo: {font_id: {glyph: {side: value}}}
        self._previous_values: dict[int, dict[str, dict[str, int | None]]] = {}
        # Glyphs that were actually modified
        self._affected_glyphs: list[str] = []

    @property
    def description(self) -> str:
        """Human-readable description of the command."""
        if self.source_glyphs:
            return f"Sync rules for {len(self.source_glyphs)} glyphs"
        return "Sync all rules"

    def execute(
        self,
        context: FontContext,
        rules_managers: dict[int, MetricsRulesManager] | None = None,
    ) -> CommandResult:
        """
        Execute the command, applying all rules.

        Args:
            context: Font context containing fonts to operate on.
            rules_managers: Dict mapping font id to MetricsRulesManager.

        Returns:
            CommandResult with affected glyphs.
        """
        if rules_managers is None:
            return CommandResult.error("Rules managers not provided")

        all_affected: set[str] = set()

        for font in context:
            font_id = id(font)
            manager = rules_managers.get(font_id)
            if manager is None:
                continue

            # Determine source glyphs
            if self.source_glyphs:
                sources = self.source_glyphs
            else:
                # Get all glyphs that have dependents
                sources = list(manager._dependents_cache.keys())

            # Collect all affected glyphs in topological order
            glyphs_to_sync: list[str] = []
            seen: set[str] = set()

            for source in sources:
                cascade = manager.get_cascade_order(source)
                for g in cascade:
                    if g not in seen:
                        seen.add(g)
                        glyphs_to_sync.append(g)

            if not glyphs_to_sync:
                continue

            # Save previous values for undo
            self._previous_values[font_id] = {}
            for glyph in glyphs_to_sync:
                if glyph not in font:
                    continue
                g = font[glyph]
                self._previous_values[font_id][glyph] = {
                    'left': g.leftMargin,
                    'right': g.rightMargin,
                }

            # Apply rules in order
            for glyph in glyphs_to_sync:
                if glyph not in font:
                    continue

                g = font[glyph]

                # Check and apply left rule
                left_value = manager.evaluate(glyph, 'left')
                if left_value is not None and g.leftMargin != left_value:
                    g.leftMargin = left_value
                    all_affected.add(glyph)

                # Check and apply right rule
                right_value = manager.evaluate(glyph, 'right')
                if right_value is not None and g.rightMargin != right_value:
                    g.rightMargin = right_value
                    all_affected.add(glyph)

        self._affected_glyphs = list(all_affected)

        if all_affected:
            return CommandResult.ok(
                f"Synced {len(all_affected)} glyphs",
                affected_glyphs=self._affected_glyphs,
            )
        return CommandResult.ok("No changes needed")

    def undo(
        self,
        context: FontContext,
        rules_managers: dict[int, MetricsRulesManager] | None = None,
    ) -> CommandResult:
        """
        Undo the sync, restoring previous margin values.

        Args:
            context: Font context containing fonts to operate on.
            rules_managers: Dict mapping font id to MetricsRulesManager.

        Returns:
            CommandResult indicating success.
        """
        for font in context:
            font_id = id(font)
            previous = self._previous_values.get(font_id, {})

            for glyph, values in previous.items():
                if glyph not in font:
                    continue
                g = font[glyph]
                if values['left'] is not None:
                    g.leftMargin = values['left']
                if values['right'] is not None:
                    g.rightMargin = values['right']

        return CommandResult.ok(
            f"Restored {len(self._affected_glyphs)} glyphs",
            affected_glyphs=self._affected_glyphs,
        )