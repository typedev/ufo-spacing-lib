"""
Margins Commands.

This module contains all commands for glyph margins operations.

Commands:
    - SetMarginCommand: Set margin to an absolute value
    - AdjustMarginCommand: Adjust margin by a delta value

Features:
    - Support for left and right margins
    - Automatic propagation to composite glyphs
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

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..contexts import FontContext
from .base import Command, CommandResult

if TYPE_CHECKING:
    from ..rules_manager import MetricsRulesManager

# Side constants
SIDE_LEFT = 'left'
SIDE_RIGHT = 'right'


@dataclass
class SetMarginCommand(Command):
    """
    Command to set a glyph margin to an absolute value.

    Sets the left or right margin of a glyph to a specific value.
    Optionally propagates the change to composite glyphs and applies
    metrics rules to dependent glyphs.

    Attributes:
        glyph_name: Name of the glyph to modify.
        side: Which margin to set - 'left' or 'right'.
        value: The margin value to set.
        propagate_to_composites: If True (default), also updates
            composite glyphs that use this glyph as a base component.
        recursive_propagate: If True, propagation continues recursively
            to composites of composites. Default is False.
        apply_rules: If True (default), applies metrics rules to glyphs
            that depend on this glyph.

    Example:
        >>> cmd = SetMarginCommand(
        ...     glyph_name='A',
        ...     side='left',
        ...     value=50,
        ... )
        >>> editor.execute(cmd)

    Note:
        For glyphs without contours (like /space), modifying the
        margin affects the glyph width instead.
    """

    glyph_name: str
    side: str  # 'left' or 'right'
    value: int
    propagate_to_composites: bool = True
    recursive_propagate: bool = False
    apply_rules: bool = True
    _previous_state: dict[int, dict] = field(
        default_factory=dict, repr=False, compare=False
    )

    @property
    def description(self) -> str:
        """
        Human-readable description of the command.

        Returns:
            String like "Set left margin A = 50"
        """
        return f"Set {self.side} margin {self.glyph_name} = {self.value}"

    def _save_glyph_state(self, font: Any, glyph_name: str) -> dict:
        """Save the current state of a glyph for undo."""
        glyph = font[glyph_name]
        return {
            'leftMargin': glyph.leftMargin,
            'rightMargin': glyph.rightMargin,
            'width': glyph.width,
        }

    def _restore_glyph_state(self, font: Any, glyph_name: str, state: dict):
        """Restore a glyph to a previous state."""
        glyph = font[glyph_name]
        # Restoring margins automatically moves contours/components
        if state['leftMargin'] is not None:
            glyph.leftMargin = state['leftMargin']
        if state['rightMargin'] is not None:
            glyph.rightMargin = state['rightMargin']

    def execute(
        self,
        context: FontContext,
        rules_managers: dict[int, MetricsRulesManager] | None = None,
    ) -> CommandResult:
        """
        Set the margin value for the glyph in all context fonts.

        Args:
            context: FontContext with fonts to modify.
            rules_managers: Optional dict of rules managers keyed by font id.

        Returns:
            CommandResult indicating success with optional warnings.
        """
        warnings: list[str] = []
        affected: list[str] = [self.glyph_name]

        for font in context:
            if self.glyph_name not in font:
                continue

            font_state = {'main': {}, 'composites': {}, 'cascade': {}}
            glyph = font[self.glyph_name]

            # Save main glyph state
            font_state['main'] = self._save_glyph_state(font, self.glyph_name)

            # Calculate delta from current value
            current_margin = (
                glyph.leftMargin if self.side == SIDE_LEFT else glyph.rightMargin
            )

            scaled_value = context.scale_value(font, self.value)

            if current_margin is not None:
                delta = scaled_value - current_margin
                if self.side == SIDE_LEFT:
                    glyph.leftMargin = scaled_value
                else:
                    glyph.rightMargin = scaled_value
            else:
                # For empty glyphs, adjust width
                delta = scaled_value
                glyph.width = scaled_value

            # Get rules manager for this font (needed for both propagate and cascade)
            rules_manager = None
            if self.apply_rules and rules_managers is not None:
                rules_manager = rules_managers.get(id(font))

            # Propagate to composites (skip those with rules - cascade handles them)
            if self.propagate_to_composites and delta != 0:
                modified = self._propagate_to_composites(
                    font, self.glyph_name, self.side, delta, font_state,
                    recursive=self.recursive_propagate,
                    rules_manager=rules_manager,
                )
                affected.extend(modified)

            # Apply rules cascade
            if rules_manager:
                cascade_warnings, cascade_affected = self._apply_rules_cascade(
                    font, rules_manager, font_state
                )
                warnings.extend(cascade_warnings)
                affected.extend(cascade_affected)

            self._previous_state[id(font)] = font_state

        return CommandResult.ok(
            message=self.description,
            warnings=warnings,
            affected_glyphs=affected,
        )

    def _propagate_to_composites(
        self,
        font: Any,
        glyph_name: str,
        side: str,
        delta: int,
        font_state: dict,
        recursive: bool = False,
        rules_manager: "MetricsRulesManager | None" = None,
        _visited: set | None = None,
    ) -> list[str]:
        """
        Propagate margin change to composite glyphs.

        Composites that have metrics rules for the affected side are skipped,
        as their margins will be updated by the rules cascade instead.

        Args:
            font: The font object.
            glyph_name: Name of the base glyph that changed.
            side: Which side changed ('left' or 'right').
            delta: The amount the margin changed.
            font_state: State dict to save composite states into.
            recursive: If True, continue to composites of composites.
            rules_manager: Optional rules manager to check for rules.
            _visited: Internal set to prevent infinite loops.

        Returns:
            List of composite glyph names that were modified.
        """
        modified = []

        if _visited is None:
            _visited = set()

        if glyph_name in _visited:
            return modified
        _visited.add(glyph_name)

        if not hasattr(font, 'getReverseComponentMapping'):
            return modified

        map_glyphs = font.getReverseComponentMapping()
        if glyph_name not in map_glyphs:
            return modified

        for comp_name in map_glyphs[glyph_name]:
            if comp_name not in font or comp_name in _visited:
                continue

            # Skip composites that have rules for this side
            # Rules take priority - cascade will handle them
            if rules_manager and rules_manager.has_rule(comp_name, side):
                continue

            comp_glyph = font[comp_name]

            # Save state (only if not already saved)
            if comp_name not in font_state['composites']:
                font_state['composites'][comp_name] = self._save_glyph_state(
                    font, comp_name
                )

            if hasattr(comp_glyph, 'changed'):
                comp_glyph.changed()

            if side == SIDE_LEFT:
                if hasattr(comp_glyph, 'components') and comp_glyph.components:
                    if len(comp_glyph.components) > 1:
                        for component in comp_glyph.components:
                            component.moveBy((delta, 0))
                        comp_glyph.components[0].moveBy((-delta, 0))
                    elif len(comp_glyph.components) == 1:
                        comp_glyph.components[0].moveBy((-delta, 0))
                        offset_x, _ = comp_glyph.components[0].offset
                        if offset_x != 0:
                            comp_glyph.moveBy((-offset_x, 0))
                            if hasattr(comp_glyph, 'changed'):
                                comp_glyph.changed()
                comp_glyph.width += delta

            elif side == SIDE_RIGHT:
                if comp_glyph.rightMargin is not None:
                    comp_glyph.rightMargin += delta

            modified.append(comp_name)

            if recursive:
                nested = self._propagate_to_composites(
                    font, comp_name, side, delta, font_state,
                    recursive=True,
                    rules_manager=rules_manager,
                    _visited=_visited,
                )
                modified.extend(nested)

        return modified

    def _apply_rules_cascade(
        self,
        font: Any,
        rules_manager: MetricsRulesManager,
        font_state: dict,
    ) -> tuple[list[str], list[str]]:
        """
        Apply metrics rules to all dependent glyphs.

        Args:
            font: The font object.
            rules_manager: MetricsRulesManager with rules.
            font_state: State dict to save cascade states into.

        Returns:
            Tuple of (warnings, affected_glyphs).
        """
        warnings: list[str] = []
        affected: list[str] = []

        # Get ordered list of glyphs to update
        cascade_glyphs = rules_manager.get_cascade_order(self.glyph_name)

        for glyph_name in cascade_glyphs:
            if glyph_name not in font:
                continue

            for side in [SIDE_LEFT, SIDE_RIGHT]:
                rule = rules_manager.get_rule(glyph_name, side)
                if not rule:
                    continue

                # Save state before modification (if not already saved)
                state_key = f"{glyph_name}.{side}"
                if state_key not in font_state['cascade']:
                    font_state['cascade'][state_key] = {
                        'glyph': glyph_name,
                        'side': side,
                        'state': self._save_glyph_state(font, glyph_name),
                    }

                # Evaluate and apply
                try:
                    new_value = rules_manager.evaluate(glyph_name, side)
                    if new_value is not None:
                        glyph = font[glyph_name]
                        if side == SIDE_LEFT:
                            glyph.leftMargin = new_value
                        else:
                            glyph.rightMargin = new_value

                        if glyph_name not in affected:
                            affected.append(glyph_name)

                        if hasattr(glyph, 'changed'):
                            glyph.changed()
                except Exception as e:
                    warnings.append(f"Rule for {glyph_name}.{side}: {e}")

        return warnings, affected

    def undo(
        self,
        context: FontContext,
        rules_managers: dict[int, MetricsRulesManager] | None = None,
    ) -> CommandResult:
        """
        Restore the previous margin values.

        Args:
            context: FontContext (same as used in execute).
            rules_managers: Not used, kept for API consistency.

        Returns:
            CommandResult indicating success.
        """
        for font in context:
            font_state = self._previous_state.get(id(font))
            if not font_state:
                continue

            # Restore cascade changes first (in reverse order)
            for item in reversed(list(font_state.get('cascade', {}).values())):
                glyph_name = item['glyph']
                if glyph_name in font:
                    self._restore_glyph_state(font, glyph_name, item['state'])

            # Restore composites
            for comp_name, comp_state in font_state.get('composites', {}).items():
                if comp_name in font:
                    self._restore_glyph_state(font, comp_name, comp_state)

            # Restore main glyph
            if 'main' in font_state and self.glyph_name in font:
                self._restore_glyph_state(
                    font, self.glyph_name, font_state['main']
                )

        return CommandResult.ok(f"Undid: {self.description}")


@dataclass
class AdjustMarginCommand(Command):
    """
    Command to adjust a glyph margin by a delta value.

    Adds the delta to the current margin value. This is the most
    common operation when using keyboard shortcuts to adjust spacing.
    Optionally applies metrics rules to dependent glyphs.

    Attributes:
        glyph_name: Name of the glyph to modify.
        side: Which margin to adjust - 'left' or 'right'.
        delta: The amount to add (negative to decrease).
        propagate_to_composites: If True (default), also updates
            composite glyphs that use this glyph as a base.
        recursive_propagate: If True, propagation continues recursively
            to composites of composites. Default is False.
        apply_rules: If True (default), applies metrics rules to glyphs
            that depend on this glyph.

    Example:
        >>> # Decrease right margin by 5 units
        >>> cmd = AdjustMarginCommand(
        ...     glyph_name='A',
        ...     side='right',
        ...     delta=-5,
        ... )
        >>> editor.execute(cmd)
    """

    glyph_name: str
    side: str  # 'left' or 'right'
    delta: int
    propagate_to_composites: bool = True
    recursive_propagate: bool = False
    apply_rules: bool = True
    _previous_state: dict[int, dict] = field(
        default_factory=dict, repr=False, compare=False
    )

    @property
    def description(self) -> str:
        """
        Human-readable description of the command.

        Returns:
            String like "Adjust left margin A +10"
        """
        sign = "+" if self.delta > 0 else ""
        return f"Adjust {self.side} margin {self.glyph_name} {sign}{self.delta}"

    def _save_glyph_state(self, font: Any, glyph_name: str) -> dict:
        """Save the current state of a glyph for undo."""
        glyph = font[glyph_name]
        return {
            'leftMargin': glyph.leftMargin,
            'rightMargin': glyph.rightMargin,
            'width': glyph.width,
        }

    def _restore_glyph_state(self, font: Any, glyph_name: str, state: dict):
        """Restore a glyph to a previous state."""
        glyph = font[glyph_name]
        # Restoring margins automatically moves contours/components
        if state['leftMargin'] is not None:
            glyph.leftMargin = state['leftMargin']
        if state['rightMargin'] is not None:
            glyph.rightMargin = state['rightMargin']

    def execute(
        self,
        context: FontContext,
        rules_managers: dict[int, MetricsRulesManager] | None = None,
    ) -> CommandResult:
        """
        Adjust the margin value for the glyph in all context fonts.

        Args:
            context: FontContext with fonts to modify.
            rules_managers: Optional dict of rules managers keyed by font id.

        Returns:
            CommandResult indicating success with optional warnings.
        """
        warnings: list[str] = []
        affected: list[str] = [self.glyph_name]

        for font in context:
            if self.glyph_name not in font:
                continue

            font_state = {'main': {}, 'composites': {}, 'cascade': {}}
            glyph = font[self.glyph_name]

            # Save state
            font_state['main'] = self._save_glyph_state(font, self.glyph_name)

            # Calculate scaled delta
            scaled_delta = context.scale_value(font, self.delta)

            # Apply delta
            if self.side == SIDE_LEFT:
                if glyph.leftMargin is not None:
                    glyph.leftMargin += scaled_delta
                else:
                    glyph.width += scaled_delta
                    self._previous_state[id(font)] = font_state
                    continue  # Don't propagate for empty glyphs
            else:
                if glyph.rightMargin is not None:
                    glyph.rightMargin += scaled_delta
                else:
                    glyph.width += scaled_delta
                    self._previous_state[id(font)] = font_state
                    continue

            # Get rules manager for this font (needed for both propagate and cascade)
            rules_manager = None
            if self.apply_rules and rules_managers is not None:
                rules_manager = rules_managers.get(id(font))

            # Propagate to composites (skip those with rules - cascade handles them)
            if self.propagate_to_composites:
                modified = self._propagate_to_composites(
                    font, self.glyph_name, self.side, scaled_delta, font_state,
                    recursive=self.recursive_propagate,
                    rules_manager=rules_manager,
                )
                affected.extend(modified)

            # Apply rules cascade
            if rules_manager:
                cascade_warnings, cascade_affected = self._apply_rules_cascade(
                    font, rules_manager, font_state
                )
                warnings.extend(cascade_warnings)
                affected.extend(cascade_affected)

            self._previous_state[id(font)] = font_state

        return CommandResult.ok(
            message=self.description,
            warnings=warnings,
            affected_glyphs=affected,
        )

    def _propagate_to_composites(
        self,
        font: Any,
        glyph_name: str,
        side: str,
        delta: int,
        font_state: dict,
        recursive: bool = False,
        rules_manager: "MetricsRulesManager | None" = None,
        _visited: set[str] | None = None,
    ) -> list[str]:
        """Propagate margin change to composite glyphs.

        Composites that have metrics rules for the affected side are skipped,
        as their margins will be updated by the rules cascade instead.
        """
        modified = []

        if _visited is None:
            _visited = set()

        if glyph_name in _visited:
            return modified
        _visited.add(glyph_name)

        if not hasattr(font, 'getReverseComponentMapping'):
            return modified

        map_glyphs = font.getReverseComponentMapping()
        if glyph_name not in map_glyphs:
            return modified

        for comp_name in map_glyphs[glyph_name]:
            if comp_name not in font or comp_name in _visited:
                continue

            # Skip composites that have rules for this side
            # Rules take priority - cascade will handle them
            if rules_manager and rules_manager.has_rule(comp_name, side):
                continue

            comp_glyph = font[comp_name]

            if comp_name not in font_state['composites']:
                font_state['composites'][comp_name] = self._save_glyph_state(
                    font, comp_name
                )

            if hasattr(comp_glyph, 'changed'):
                comp_glyph.changed()

            if side == SIDE_LEFT:
                if hasattr(comp_glyph, 'components') and comp_glyph.components:
                    if len(comp_glyph.components) > 1:
                        for component in comp_glyph.components:
                            component.moveBy((delta, 0))
                        comp_glyph.components[0].moveBy((-delta, 0))
                    elif len(comp_glyph.components) == 1:
                        comp_glyph.components[0].moveBy((-delta, 0))
                        offset_x, _ = comp_glyph.components[0].offset
                        if offset_x != 0:
                            comp_glyph.moveBy((-offset_x, 0))
                            if hasattr(comp_glyph, 'changed'):
                                comp_glyph.changed()
                comp_glyph.width += delta

            elif side == SIDE_RIGHT:
                if comp_glyph.rightMargin is not None:
                    comp_glyph.rightMargin += delta

            modified.append(comp_name)

            if recursive:
                nested = self._propagate_to_composites(
                    font, comp_name, side, delta, font_state,
                    recursive=True,
                    rules_manager=rules_manager,
                    _visited=_visited,
                )
                modified.extend(nested)

        return modified

    def _apply_rules_cascade(
        self,
        font: Any,
        rules_manager: MetricsRulesManager,
        font_state: dict,
    ) -> tuple[list[str], list[str]]:
        """Apply metrics rules to all dependent glyphs."""
        warnings: list[str] = []
        affected: list[str] = []

        cascade_glyphs = rules_manager.get_cascade_order(self.glyph_name)

        for glyph_name in cascade_glyphs:
            if glyph_name not in font:
                continue

            for side in [SIDE_LEFT, SIDE_RIGHT]:
                rule = rules_manager.get_rule(glyph_name, side)
                if not rule:
                    continue

                state_key = f"{glyph_name}.{side}"
                if state_key not in font_state['cascade']:
                    font_state['cascade'][state_key] = {
                        'glyph': glyph_name,
                        'side': side,
                        'state': self._save_glyph_state(font, glyph_name),
                    }

                try:
                    new_value = rules_manager.evaluate(glyph_name, side)
                    if new_value is not None:
                        glyph = font[glyph_name]
                        if side == SIDE_LEFT:
                            glyph.leftMargin = new_value
                        else:
                            glyph.rightMargin = new_value

                        if glyph_name not in affected:
                            affected.append(glyph_name)

                        if hasattr(glyph, 'changed'):
                            glyph.changed()
                except Exception as e:
                    warnings.append(f"Rule for {glyph_name}.{side}: {e}")

        return warnings, affected

    def undo(
        self,
        context: FontContext,
        rules_managers: dict[int, MetricsRulesManager] | None = None,
    ) -> CommandResult:
        """
        Restore the previous margin values.

        Args:
            context: FontContext (same as used in execute).
            rules_managers: Not used, kept for API consistency.

        Returns:
            CommandResult indicating success.
        """
        for font in context:
            font_state = self._previous_state.get(id(font))
            if not font_state:
                continue

            # Restore cascade first
            for item in reversed(list(font_state.get('cascade', {}).values())):
                glyph_name = item['glyph']
                if glyph_name in font:
                    self._restore_glyph_state(font, glyph_name, item['state'])

            # Restore composites
            for comp_name, comp_state in font_state.get('composites', {}).items():
                if comp_name in font:
                    self._restore_glyph_state(font, comp_name, comp_state)

            # Restore main glyph
            if 'main' in font_state and self.glyph_name in font:
                self._restore_glyph_state(
                    font, self.glyph_name, font_state['main']
                )

        return CommandResult.ok(f"Undid: {self.description}")
