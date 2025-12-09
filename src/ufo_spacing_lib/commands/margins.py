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
    - Full undo/redo capability

Example:
    Basic margin adjustment:

    >>> from ufo_spacing_lib import MarginsEditor, FontContext, AdjustMarginCommand
    >>>
    >>> editor = MarginsEditor()
    >>> context = FontContext.from_single_font(font)
    >>>
    >>> # Increase left margin by 10 units
    >>> cmd = AdjustMarginCommand(
    ...     glyph_name='A',
    ...     side='left',
    ...     delta=10,
    ...     propagate_to_composites=True
    ... )
    >>> editor.execute(cmd, context)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..contexts import FontContext
from .base import Command, CommandResult

# Side constants
SIDE_LEFT = 'left'
SIDE_RIGHT = 'right'


@dataclass
class SetMarginCommand(Command):
    """
    Command to set a glyph margin to an absolute value.

    Sets the left or right margin of a glyph to a specific value.
    Optionally propagates the change to composite glyphs that
    use this glyph as a component.

    Attributes:
        glyph_name: Name of the glyph to modify.
        side: Which margin to set - 'left' or 'right'.
        value: The margin value to set.
        propagate_to_composites: If True (default), also updates
            composite glyphs that use this glyph as a base component.
        recursive_propagate: If True, propagation continues recursively
            to composites of composites. Default is False.

    Example:
        >>> cmd = SetMarginCommand(
        ...     glyph_name='A',
        ...     side='left',
        ...     value=50,
        ...     propagate_to_composites=True,
        ...     recursive_propagate=False  # Only direct composites
        ... )
        >>> editor.execute(cmd, context)

    Note:
        For glyphs without contours (like /space), modifying the
        margin affects the glyph width instead.
    """

    glyph_name: str
    side: str  # 'left' or 'right'
    value: int
    propagate_to_composites: bool = True
    recursive_propagate: bool = False
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
        state = {
            'leftMargin': glyph.leftMargin,
            'rightMargin': glyph.rightMargin,
            'width': glyph.width,
        }
        # Save component offsets if any
        if hasattr(glyph, 'components') and glyph.components:
            state['component_offsets'] = [
                (c.baseGlyph, c.offset) for c in glyph.components
            ]
        return state

    def _restore_glyph_state(self, font: Any, glyph_name: str, state: dict):
        """Restore a glyph to a previous state."""
        glyph = font[glyph_name]

        # Restore margins/width
        if state['leftMargin'] is not None:
            glyph.leftMargin = state['leftMargin']
        if state['rightMargin'] is not None:
            glyph.rightMargin = state['rightMargin']

        # Restore component offsets if saved
        if 'component_offsets' in state and hasattr(glyph, 'components'):
            for i, (base, offset) in enumerate(state['component_offsets']):
                if i < len(glyph.components):
                    glyph.components[i].offset = offset

    def execute(self, context: FontContext) -> CommandResult:
        """
        Set the margin value for the glyph in all context fonts.

        Args:
            context: FontContext with fonts to modify.

        Returns:
            CommandResult indicating success.
        """
        for font in context:
            if self.glyph_name not in font:
                continue

            font_state = {'main': {}, 'composites': {}}
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

            # Propagate to composites
            if self.propagate_to_composites and delta != 0:
                self._propagate_to_composites(
                    font, self.glyph_name, self.side, delta, font_state,
                    recursive=self.recursive_propagate
                )

            self._previous_state[id(font)] = font_state

        return CommandResult.ok(self.description)

    def _propagate_to_composites(
        self,
        font: Any,
        glyph_name: str,
        side: str,
        delta: int,
        font_state: dict,
        recursive: bool = False,
        _visited: set | None = None
    ) -> list[str]:
        """
        Propagate margin change to composite glyphs.

        When a base glyph's margin changes, composites using it
        need to be updated to maintain proper spacing.

        Args:
            font: The font object.
            glyph_name: Name of the base glyph that changed.
            side: Which side changed ('left' or 'right').
            delta: The amount the margin changed.
            font_state: State dict to save composite states into.
            recursive: If True, continue propagating to composites of composites.
            _visited: Internal set to track visited glyphs (prevents infinite loops).

        Returns:
            List of composite glyph names that were modified.
        """
        modified = []

        # Initialize visited set for recursion tracking
        if _visited is None:
            _visited = set()

        # Prevent infinite loops
        if glyph_name in _visited:
            return modified
        _visited.add(glyph_name)

        # Get reverse component mapping if available
        if not hasattr(font, 'getReverseComponentMapping'):
            return modified

        map_glyphs = font.getReverseComponentMapping()
        if glyph_name not in map_glyphs:
            return modified

        for comp_name in map_glyphs[glyph_name]:
            if comp_name not in font:
                continue

            # Skip already processed glyphs
            if comp_name in _visited:
                continue

            comp_glyph = font[comp_name]

            # Save composite state (only if not already saved)
            if comp_name not in font_state['composites']:
                font_state['composites'][comp_name] = self._save_glyph_state(
                    font, comp_name
                )

            if hasattr(comp_glyph, 'changed'):
                comp_glyph.changed()

            if side == SIDE_LEFT:
                # Adjust component positions for left margin change
                if hasattr(comp_glyph, 'components') and comp_glyph.components:
                    if len(comp_glyph.components) > 1:
                        # Move all components
                        for component in comp_glyph.components:
                            component.moveBy((delta, 0))
                        # Move first one back
                        comp_glyph.components[0].moveBy((-delta, 0))
                    elif len(comp_glyph.components) == 1:
                        comp_glyph.components[0].moveBy((-delta, 0))

                        # Handle offset
                        offset_x, offset_y = comp_glyph.components[0].offset
                        if offset_x != 0:
                            comp_glyph.moveBy((-offset_x, 0))
                            if hasattr(comp_glyph, 'changed'):
                                comp_glyph.changed()

                comp_glyph.width += delta

            elif side == SIDE_RIGHT:
                if comp_glyph.rightMargin is not None:
                    comp_glyph.rightMargin += delta

            modified.append(comp_name)

            # Recursive propagation
            if recursive:
                nested_modified = self._propagate_to_composites(
                    font, comp_name, side, delta, font_state,
                    recursive=True, _visited=_visited
                )
                modified.extend(nested_modified)

        return modified

    def undo(self, context: FontContext) -> CommandResult:
        """
        Restore the previous margin values.

        Args:
            context: FontContext (same as used in execute).

        Returns:
            CommandResult indicating success.
        """
        for font in context:
            font_state = self._previous_state.get(id(font))
            if not font_state:
                continue

            # Restore main glyph
            if 'main' in font_state and self.glyph_name in font:
                self._restore_glyph_state(
                    font, self.glyph_name, font_state['main']
                )

            # Restore composites
            for comp_name, comp_state in font_state.get('composites', {}).items():
                if comp_name in font:
                    self._restore_glyph_state(font, comp_name, comp_state)

        return CommandResult.ok(f"Undid: {self.description}")


@dataclass
class AdjustMarginCommand(Command):
    """
    Command to adjust a glyph margin by a delta value.

    Adds the delta to the current margin value. This is the most
    common operation when using keyboard shortcuts to adjust spacing.

    Attributes:
        glyph_name: Name of the glyph to modify.
        side: Which margin to adjust - 'left' or 'right'.
        delta: The amount to add (negative to decrease).
        propagate_to_composites: If True (default), also updates
            composite glyphs that use this glyph as a base.
        recursive_propagate: If True, propagation continues recursively
            to composites of composites. Default is False.

    Example:
        >>> # Decrease right margin by 5 units
        >>> cmd = AdjustMarginCommand(
        ...     glyph_name='A',
        ...     side='right',
        ...     delta=-5,
        ...     recursive_propagate=True  # Also update composites of composites
        ... )
        >>> editor.execute(cmd, context)
    """

    glyph_name: str
    side: str  # 'left' or 'right'
    delta: int
    propagate_to_composites: bool = True
    recursive_propagate: bool = False
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
        state = {
            'leftMargin': glyph.leftMargin,
            'rightMargin': glyph.rightMargin,
            'width': glyph.width,
        }
        if hasattr(glyph, 'components') and glyph.components:
            state['component_offsets'] = [
                (c.baseGlyph, c.offset) for c in glyph.components
            ]
        return state

    def _restore_glyph_state(self, font: Any, glyph_name: str, state: dict):
        """Restore a glyph to a previous state."""
        glyph = font[glyph_name]

        if state['leftMargin'] is not None:
            glyph.leftMargin = state['leftMargin']
        if state['rightMargin'] is not None:
            glyph.rightMargin = state['rightMargin']

        if 'component_offsets' in state and hasattr(glyph, 'components'):
            for i, (base, offset) in enumerate(state['component_offsets']):
                if i < len(glyph.components):
                    glyph.components[i].offset = offset

    def execute(self, context: FontContext) -> CommandResult:
        """
        Adjust the margin value for the glyph in all context fonts.

        Args:
            context: FontContext with fonts to modify.

        Returns:
            CommandResult indicating success.
        """
        for font in context:
            if self.glyph_name not in font:
                continue

            font_state = {'main': {}, 'composites': {}}
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

            # Propagate to composites
            if self.propagate_to_composites:
                self._propagate_to_composites(
                    font, self.glyph_name, self.side, scaled_delta, font_state,
                    recursive=self.recursive_propagate
                )

            self._previous_state[id(font)] = font_state

        return CommandResult.ok(self.description)

    def _propagate_to_composites(
        self,
        font: Any,
        glyph_name: str,
        side: str,
        delta: int,
        font_state: dict,
        recursive: bool = False,
        _visited: set[str] | None = None
    ):
        """
        Propagate margin change to composite glyphs.

        Args:
            font: The font object.
            glyph_name: Name of the base glyph that changed.
            side: Which side changed.
            delta: The amount the margin changed.
            font_state: State dict to save composite states into.
            recursive: If True, continue to composites of composites.
            _visited: Internal set to prevent infinite loops.
        """
        if _visited is None:
            _visited = set()

        if glyph_name in _visited:
            return
        _visited.add(glyph_name)

        if not hasattr(font, 'getReverseComponentMapping'):
            return

        map_glyphs = font.getReverseComponentMapping()
        if glyph_name not in map_glyphs:
            return

        for comp_name in map_glyphs[glyph_name]:
            if comp_name not in font or comp_name in _visited:
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

            # Recursive propagation
            if recursive:
                self._propagate_to_composites(
                    font, comp_name, side, delta, font_state,
                    recursive=True, _visited=_visited
                )

    def undo(self, context: FontContext) -> CommandResult:
        """
        Restore the previous margin values.

        Args:
            context: FontContext (same as used in execute).

        Returns:
            CommandResult indicating success.
        """
        for font in context:
            font_state = self._previous_state.get(id(font))
            if not font_state:
                continue

            # Restore main glyph
            if 'main' in font_state and self.glyph_name in font:
                self._restore_glyph_state(
                    font, self.glyph_name, font_state['main']
                )

            # Restore composites
            for comp_name, comp_state in font_state.get('composites', {}).items():
                if comp_name in font:
                    self._restore_glyph_state(font, comp_name, comp_state)

        return CommandResult.ok(f"Undid: {self.description}")

