"""
Margins Editor Module.

This module provides the MarginsEditor class for managing glyph
margins operations with full undo/redo support.

The MarginsEditor is structurally identical to KerningEditor but
is kept separate for:
- Separate undo histories (kerning and margins are independent)
- Potential future margins-specific functionality
- Clear semantic separation

Example:
    Basic usage:

    >>> from ufo_spacing_lib import MarginsEditor, FontContext, AdjustMarginCommand
    >>>
    >>> editor = MarginsEditor()
    >>> context = FontContext.from_single_font(font)
    >>>
    >>> # Adjust left margin
    >>> cmd = AdjustMarginCommand(
    ...     glyph_name='A',
    ...     side='left',
    ...     delta=10
    ... )
    >>> editor.execute(cmd, context)
    >>>
    >>> # Undo
    >>> editor.undo()
"""

from __future__ import annotations

from collections.abc import Callable

from ..commands.base import Command, CommandResult
from ..contexts import FontContext


class MarginsEditor:
    """
    Editor for margins operations with undo/redo support.

    The MarginsEditor manages execution of margins commands and
    maintains a history stack for undo/redo operations. It is
    completely UI-independent and can be used in tests or scripts.

    This class is functionally identical to KerningEditor but
    maintains a separate history, allowing independent undo/redo
    for kerning and margins operations.

    Attributes:
        on_change: Optional callback called after successful execute().
            Signature: (command: Command, result: CommandResult) -> None
        on_undo: Optional callback called after successful undo().
            Signature: (command: Command, result: CommandResult) -> None
        on_redo: Optional callback called after successful redo().
            Signature: (command: Command, result: CommandResult) -> None

    Example:
        Creating and using an editor:

        >>> editor = MarginsEditor()
        >>>
        >>> # Execute a command
        >>> cmd = AdjustMarginCommand(
        ...     glyph_name='A',
        ...     side='left',
        ...     delta=10,
        ...     propagate_to_composites=True
        ... )
        >>> ctx = FontContext.from_single_font(font)
        >>> result = editor.execute(cmd, ctx)
        >>>
        >>> # Undo
        >>> editor.undo()

    Note:
        Margins operations can be expensive due to composite
        propagation. Consider batching operations when possible.
    """

    def __init__(self):
        """
        Initialize the MarginsEditor.

        Creates a new editor with empty history and no callbacks.
        """
        # History stacks
        self._history: list[tuple[Command, FontContext]] = []
        self._redo_stack: list[tuple[Command, FontContext]] = []

        # Event callbacks
        self.on_change: Callable[[Command, CommandResult], None] | None = None
        self.on_undo: Callable[[Command, CommandResult], None] | None = None
        self.on_redo: Callable[[Command, CommandResult], None] | None = None

    def execute(self, command: Command, context: FontContext) -> CommandResult:
        """
        Execute a command and add it to history.

        Executes the given command with the provided context.
        If successful, the command is added to the undo history
        and the redo stack is cleared.

        Args:
            command: The command to execute.
            context: The font context to execute in.

        Returns:
            CommandResult from the command execution.

        Example:
            >>> cmd = AdjustMarginCommand(
            ...     glyph_name='A',
            ...     side='right',
            ...     delta=-5
            ... )
            >>> result = editor.execute(cmd, context)

        Note:
            Failed commands are not added to history.
        """
        result = command.execute(context)

        if result.success:
            # Add to history
            self._history.append((command, context))

            # Clear redo stack
            self._redo_stack.clear()

            # Notify listeners
            if self.on_change:
                self.on_change(command, result)

        return result

    def undo(self) -> CommandResult | None:
        """
        Undo the last command.

        Removes the last command from history, calls its undo()
        method, and adds it to the redo stack.

        Returns:
            CommandResult from the undo operation, or None if
            there's nothing to undo.

        Example:
            >>> if editor.can_undo:
            ...     editor.undo()
        """
        if not self._history:
            return None

        # Pop from history
        command, context = self._history.pop()

        # Execute undo
        result = command.undo(context)

        # Push to redo stack
        self._redo_stack.append((command, context))

        # Notify listeners
        if self.on_undo:
            self.on_undo(command, result)

        return result

    def redo(self) -> CommandResult | None:
        """
        Redo the last undone command.

        Removes the last command from the redo stack, re-executes
        it, and adds it back to the history.

        Returns:
            CommandResult from the redo operation, or None if
            there's nothing to redo.

        Example:
            >>> if editor.can_redo:
            ...     editor.redo()
        """
        if not self._redo_stack:
            return None

        # Pop from redo stack
        command, context = self._redo_stack.pop()

        # Re-execute
        result = command.execute(context)

        # Push to history
        self._history.append((command, context))

        # Notify listeners
        if self.on_redo:
            self.on_redo(command, result)

        return result

    @property
    def can_undo(self) -> bool:
        """
        Check if there are commands to undo.

        Returns:
            True if undo() will have an effect.
        """
        return len(self._history) > 0

    @property
    def can_redo(self) -> bool:
        """
        Check if there are commands to redo.

        Returns:
            True if redo() will have an effect.
        """
        return len(self._redo_stack) > 0

    @property
    def undo_description(self) -> str | None:
        """
        Get the description of the command that would be undone.

        Returns:
            Description string, or None if nothing to undo.
        """
        if self._history:
            return self._history[-1][0].description
        return None

    @property
    def redo_description(self) -> str | None:
        """
        Get the description of the command that would be redone.

        Returns:
            Description string, or None if nothing to redo.
        """
        if self._redo_stack:
            return self._redo_stack[-1][0].description
        return None

    @property
    def history_count(self) -> int:
        """
        Get the number of commands in the undo history.

        Returns:
            Number of commands that can be undone.
        """
        return len(self._history)

    @property
    def redo_count(self) -> int:
        """
        Get the number of commands in the redo stack.

        Returns:
            Number of commands that can be redone.
        """
        return len(self._redo_stack)

    def clear_history(self):
        """
        Clear all undo/redo history.

        Use this to free memory in long sessions.
        """
        self._history.clear()
        self._redo_stack.clear()

    def get_history(self) -> list[str]:
        """
        Get descriptions of all commands in history.

        Returns:
            List of command descriptions, oldest first.
        """
        return [cmd.description for cmd, ctx in self._history]

    def __repr__(self) -> str:
        """Return string representation of the editor."""
        return (
            f"MarginsEditor(history={len(self._history)}, "
            f"redo={len(self._redo_stack)})"
        )

