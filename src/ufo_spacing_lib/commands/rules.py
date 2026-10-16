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
from ..planner import Plan, apply_plan, plan_sync
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
            syncs every glyph that has a rule.

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
                If None, syncs all glyphs with rules.
        """
        self.source_glyphs = source_glyphs
        # Applied plans per font for undo: {font_id: Plan}
        self._plans: dict[int, Plan] = {}
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

        Composites built on a glyph that a rule moves stay in place.

        Args:
            context: Font context containing fonts to operate on.
            rules_managers: Dict mapping font id to MetricsRulesManager.

        Returns:
            CommandResult with affected glyphs and rule issues as warnings.
        """
        if rules_managers is None:
            return CommandResult.error("Rules managers not provided")

        affected: list[str] = []
        warnings: list[str] = []
        self._plans = {}

        for font in context:
            manager = rules_managers.get(id(font))
            if manager is None:
                continue

            # Targets: the glyphs whose rules read the changed glyphs
            targets: set[str] | None = None
            if self.source_glyphs:
                targets = set()
                for source in self.source_glyphs:
                    targets.update(manager.get_affected_glyphs(source))

            plan = plan_sync(font, manager, targets)
            apply_plan(font, plan)
            self._plans[id(font)] = plan
            warnings.extend(str(issue) for issue in plan.issues)
            for name in plan.ordered_names:
                if name not in affected:
                    affected.append(name)

        self._affected_glyphs = affected

        if affected:
            return CommandResult.ok(
                f"Synced {len(affected)} glyphs",
                warnings=warnings,
                affected_glyphs=self._affected_glyphs,
            )
        return CommandResult.ok("No changes needed", warnings=warnings)

    def undo(
        self,
        context: FontContext,
        rules_managers: dict[int, MetricsRulesManager] | None = None,
    ) -> CommandResult:
        """
        Undo the sync by applying the inverted plans.

        Args:
            context: Font context containing fonts to operate on.
            rules_managers: Dict mapping font id to MetricsRulesManager.

        Returns:
            CommandResult indicating success.
        """
        for font in context:
            plan = self._plans.get(id(font))
            if plan is not None:
                apply_plan(font, plan.inverted())
        self._plans = {}

        return CommandResult.ok(
            f"Restored {len(self._affected_glyphs)} glyphs",
            affected_glyphs=self._affected_glyphs,
        )
