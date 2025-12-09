"""
Kerning Commands.

This module contains all commands for kerning operations.

Commands:
    - SetKerningCommand: Set kerning to an absolute value
    - AdjustKerningCommand: Adjust kerning by a delta (relative change)
    - RemoveKerningCommand: Remove a kerning pair
    - CreateExceptionCommand: Create an exception from group kerning

All commands support:
    - Multi-font operations via FontContext
    - Per-font scaling for interpolation-aware editing
    - Full undo/redo capability

Example:
    Basic kerning adjustment:

    >>> from ufo_spacing_lib import KerningEditor, FontContext, AdjustKerningCommand
    >>>
    >>> editor = KerningEditor()
    >>> context = FontContext.from_single_font(font)
    >>>
    >>> # Decrease kerning by 10 units
    >>> cmd = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
    >>> editor.execute(cmd, context)
    >>>
    >>> # Undo the change
    >>> editor.undo()
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..contexts import FontContext
from .base import Command, CommandResult

# Type alias for kerning pair
KernPair = tuple[str, str]


@dataclass
class SetKerningCommand(Command):
    """
    Command to set kerning to an absolute value.

    Sets the kerning value for a pair to a specific value,
    regardless of the previous value.

    Attributes:
        pair: The kerning pair as (left, right) tuple.
            Can be glyph names or group names.
        value: The kerning value to set.

    Example:
        >>> cmd = SetKerningCommand(pair=('A', 'V'), value=-50)
        >>> result = editor.execute(cmd, context)
        >>> print(font.kerning[('A', 'V')])  # -50

    Note:
        When used with scaled FontContext, the value is scaled
        per font. For example, with scale=1.5, setting value=10
        results in 15 for that font.
    """

    pair: KernPair
    value: int
    _previous_values: dict[int, int | None] = field(
        default_factory=dict, repr=False, compare=False
    )

    @property
    def description(self) -> str:
        """
        Human-readable description of the command.

        Returns:
            String like "Set kerning ('A', 'V') = -50"
        """
        return f"Set kerning {self.pair} = {self.value}"

    def execute(self, context: FontContext) -> CommandResult:
        """
        Set the kerning value for the pair in all context fonts.

        Args:
            context: FontContext with fonts to modify.

        Returns:
            CommandResult indicating success.
        """
        for font in context:
            # Store previous value for undo
            if self.pair in font.kerning:
                self._previous_values[id(font)] = font.kerning[self.pair]
            else:
                self._previous_values[id(font)] = None

            # Apply scaled value
            scaled_value = context.scale_value(font, self.value)
            font.kerning[self.pair] = scaled_value

        return CommandResult.ok(f"Set {self.pair} = {self.value}")

    def undo(self, context: FontContext) -> CommandResult:
        """
        Restore the previous kerning value.

        Args:
            context: FontContext (same as used in execute).

        Returns:
            CommandResult indicating success.
        """
        for font in context:
            prev = self._previous_values.get(id(font))
            if prev is None:
                # Pair didn't exist before - remove it
                if self.pair in font.kerning:
                    del font.kerning[self.pair]
            else:
                font.kerning[self.pair] = prev

        return CommandResult.ok(f"Undid: {self.description}")


@dataclass
class AdjustKerningCommand(Command):
    """
    Command to adjust kerning by a delta value.

    Adds the delta to the current kerning value. If the pair
    doesn't exist, starts from 0.

    Special behavior:
        - If the result is 0, the pair is removed (unless it's an exception)
        - Delta is scaled per-font when using scaled FontContext

    Attributes:
        pair: The kerning pair as (left, right) tuple.
        delta: The amount to add (negative to decrease).
        remove_zero: If True (default), remove pair when value becomes 0.

    Example:
        >>> # Current kerning: ('A', 'V') = -40
        >>> cmd = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
        >>> editor.execute(cmd, context)
        >>> print(font.kerning[('A', 'V')])  # -50
    """

    pair: KernPair
    delta: int
    remove_zero: bool = True
    _previous_values: dict[int, int | None] = field(
        default_factory=dict, repr=False, compare=False
    )

    @property
    def description(self) -> str:
        """
        Human-readable description of the command.

        Returns:
            String like "Adjust kerning ('A', 'V') +10" or "-10"
        """
        sign = "+" if self.delta > 0 else ""
        return f"Adjust kerning {self.pair} {sign}{self.delta}"

    def execute(self, context: FontContext) -> CommandResult:
        """
        Adjust the kerning value by delta for all context fonts.

        Args:
            context: FontContext with fonts to modify.

        Returns:
            CommandResult indicating success.
        """
        for font in context:
            # Store previous value
            self._previous_values[id(font)] = font.kerning.get(self.pair)

            # Get current value (0 if not exists)
            current = font.kerning.get(self.pair)
            if current is None:
                current = 0

            # Calculate new value with scaling
            scaled_delta = context.scale_value(font, self.delta)
            new_value = current + scaled_delta

            # Apply or remove
            if new_value == 0 and self.remove_zero:
                if self.pair in font.kerning:
                    del font.kerning[self.pair]
            else:
                font.kerning[self.pair] = new_value

        return CommandResult.ok(self.description)

    def undo(self, context: FontContext) -> CommandResult:
        """
        Restore the previous kerning value.

        Args:
            context: FontContext (same as used in execute).

        Returns:
            CommandResult indicating success.
        """
        for font in context:
            prev = self._previous_values.get(id(font))
            if prev is None:
                if self.pair in font.kerning:
                    del font.kerning[self.pair]
            else:
                font.kerning[self.pair] = prev

        return CommandResult.ok(f"Undid: {self.description}")


@dataclass
class RemoveKerningCommand(Command):
    """
    Command to remove a kerning pair.

    Removes the kerning pair from all fonts in the context.
    If the pair doesn't exist, the command still succeeds
    (idempotent behavior).

    Attributes:
        pair: The kerning pair to remove as (left, right) tuple.

    Example:
        >>> cmd = RemoveKerningCommand(pair=('A', 'V'))
        >>> editor.execute(cmd, context)
        >>> ('A', 'V') in font.kerning  # False
    """

    pair: KernPair
    _previous_values: dict[int, int | None] = field(
        default_factory=dict, repr=False, compare=False
    )

    @property
    def description(self) -> str:
        """
        Human-readable description of the command.

        Returns:
            String like "Remove kerning ('A', 'V')"
        """
        return f"Remove kerning {self.pair}"

    def execute(self, context: FontContext) -> CommandResult:
        """
        Remove the kerning pair from all context fonts.

        Args:
            context: FontContext with fonts to modify.

        Returns:
            CommandResult indicating success.
        """
        for font in context:
            if self.pair in font.kerning:
                self._previous_values[id(font)] = font.kerning[self.pair]
                del font.kerning[self.pair]
            else:
                self._previous_values[id(font)] = None

        return CommandResult.ok(self.description)

    def undo(self, context: FontContext) -> CommandResult:
        """
        Restore the removed kerning pair.

        Args:
            context: FontContext (same as used in execute).

        Returns:
            CommandResult indicating success.
        """
        for font in context:
            prev = self._previous_values.get(id(font))
            if prev is not None:
                font.kerning[self.pair] = prev

        return CommandResult.ok(f"Undid: {self.description}")


@dataclass
class CreateExceptionCommand(Command):
    """
    Command to create a kerning exception.

    Creates an exception pair that overrides group kerning.
    This is used when you want a specific glyph pair to have
    different kerning than its group would provide.

    Attributes:
        pair: The exception pair as (left_glyph, right_glyph).
            Must be glyph names, not group names.
        value: The exception value. If None, uses current
            effective kerning value (from group).
        side: Which side to create exception for:
            - 'left': Exception for left glyph only
            - 'right': Exception for right glyph only
            - 'both': Full glyph-to-glyph exception

    Example:
        Creating an exception:

        >>> # Group kerning: (public.kern1.A, V) = -50
        >>> # Create exception for Aacute specifically
        >>> cmd = CreateExceptionCommand(
        ...     pair=('Aacute', 'V'),
        ...     value=-30,
        ...     side='left'
        ... )
        >>> editor.execute(cmd, context)

    Note:
        To determine the effective kerning value, you may need
        to use resolve_kern_pair() from the groups module.
    """

    pair: KernPair
    value: int | None = None
    side: str = 'both'  # 'left', 'right', or 'both'
    _previous_values: dict[int, int | None] = field(
        default_factory=dict, repr=False, compare=False
    )
    _created_pairs: dict[int, KernPair] = field(
        default_factory=dict, repr=False, compare=False
    )

    @property
    def description(self) -> str:
        """
        Human-readable description of the command.

        Returns:
            String describing the exception creation.
        """
        value_str = str(self.value) if self.value is not None else "current"
        return f"Create exception {self.pair} = {value_str} ({self.side})"

    def execute(self, context: FontContext) -> CommandResult:
        """
        Create the kerning exception in all context fonts.

        Args:
            context: FontContext with fonts to modify.

        Returns:
            CommandResult indicating success.

        Note:
            If value is None, this command sets 0. To use the
            current effective value, compute it before creating
            the command.
        """
        exception_value = self.value if self.value is not None else 0

        for font in context:
            # Determine the actual pair to create based on side
            actual_pair = self.pair
            self._created_pairs[id(font)] = actual_pair

            # Store previous value if exists
            if actual_pair in font.kerning:
                self._previous_values[id(font)] = font.kerning[actual_pair]
            else:
                self._previous_values[id(font)] = None

            # Set the exception
            scaled_value = context.scale_value(font, exception_value)
            font.kerning[actual_pair] = scaled_value

        return CommandResult.ok(self.description)

    def undo(self, context: FontContext) -> CommandResult:
        """
        Remove the created exception.

        Args:
            context: FontContext (same as used in execute).

        Returns:
            CommandResult indicating success.
        """
        for font in context:
            actual_pair = self._created_pairs.get(id(font), self.pair)
            prev = self._previous_values.get(id(font))

            if prev is None:
                # Exception didn't exist before - remove it
                if actual_pair in font.kerning:
                    del font.kerning[actual_pair]
            else:
                font.kerning[actual_pair] = prev

        return CommandResult.ok(f"Undid: {self.description}")

