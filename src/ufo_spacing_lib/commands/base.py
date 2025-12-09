"""
Base Command Classes.

This module defines the abstract base class for all commands and the
CommandResult class for operation results.

The Command pattern is used to encapsulate operations as objects,
enabling:
- Undo/redo functionality
- Operation logging
- Batch processing
- Testing in isolation

Design Notes:
    Commands are designed to be:
    1. Immutable after creation (except for internal undo state)
    2. Self-contained (store all data needed to execute and undo)
    3. Framework-agnostic (work with any font implementation)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

# Import context type for type hints
from ..contexts import FontContext


@dataclass(frozen=True)
class CommandResult:
    """
    Result of a command execution.

    Provides information about whether a command succeeded and
    any additional data or messages.

    Attributes:
        success: True if the command executed successfully.
        message: Optional human-readable message describing the result.
        data: Optional additional data returned by the command.
            The type and content depends on the specific command.

    Example:
        Checking result:

        >>> result = command.execute(context)
        >>> if result.success:
        ...     print(f"Done: {result.message}")
        ... else:
        ...     print(f"Failed: {result.message}")

        Accessing result data:

        >>> result = check_touches_command.execute(context)
        >>> if result.data:
        ...     touching_pairs = result.data['pairs']
    """

    success: bool
    message: str = ""
    data: Any | None = None

    @classmethod
    def ok(cls, message: str = "", data: Any = None) -> CommandResult:
        """
        Create a successful result.

        Args:
            message: Optional success message.
            data: Optional result data.

        Returns:
            CommandResult with success=True.

        Example:
            >>> return CommandResult.ok("Kerning set successfully")
        """
        return cls(success=True, message=message, data=data)

    @classmethod
    def error(cls, message: str, data: Any = None) -> CommandResult:
        """
        Create a failure result.

        Args:
            message: Error message describing what went wrong.
            data: Optional additional error information.

        Returns:
            CommandResult with success=False.

        Example:
            >>> return CommandResult.error("Pair not found in kerning")
        """
        return cls(success=False, message=message, data=data)


class Command(ABC):
    """
    Abstract base class for undoable commands.

    All operations that modify font data should be implemented as
    Command subclasses. This enables consistent undo/redo behavior
    and operation tracking.

    Subclasses must implement:
        - description: Property returning human-readable description
        - execute(): Method to perform the operation
        - undo(): Method to reverse the operation

    Implementation Guidelines:
        1. Store all data needed to undo in the command instance
        2. The execute() method should store previous state for undo
        3. Commands should be idempotent when possible
        4. Use CommandResult to report success/failure

    Example:
        Implementing a custom command:

        >>> class MyCommand(Command):
        ...     def __init__(self, value: int):
        ...         self.value = value
        ...         self._previous = {}
        ...
        ...     @property
        ...     def description(self) -> str:
        ...         return f"Set value to {self.value}"
        ...
        ...     def execute(self, context: FontContext) -> CommandResult:
        ...         for font in context:
        ...             self._previous[id(font)] = font.some_value
        ...             font.some_value = self.value
        ...         return CommandResult.ok()
        ...
        ...     def undo(self, context: FontContext) -> CommandResult:
        ...         for font in context:
        ...             font.some_value = self._previous[id(font)]
        ...         return CommandResult.ok()

    Note:
        The _previous dict uses id(font) as key because font objects
        may not be hashable in all font editors.
    """

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Human-readable description of the command.

        This is used for:
        - Undo/redo menu items (e.g., "Undo: Set kerning AV = -50")
        - Operation logging
        - Debugging

        Returns:
            String description of the operation.

        Example:
            >>> command.description
            "Set kerning ('A', 'V') = -50"
        """
        pass

    @abstractmethod
    def execute(self, context: FontContext) -> CommandResult:
        """
        Execute the command.

        This method should:
        1. Store any data needed for undo (e.g., previous values)
        2. Apply the operation to all fonts in the context
        3. Return a CommandResult indicating success/failure

        Args:
            context: FontContext containing fonts to operate on.

        Returns:
            CommandResult with success status and optional message/data.

        Note:
            This method may be called multiple times (for redo).
            Ensure it handles this correctly.
        """
        pass

    @abstractmethod
    def undo(self, context: FontContext) -> CommandResult:
        """
        Undo the command.

        This method should restore the state that existed before
        execute() was called. It uses data stored during execute().

        Args:
            context: FontContext containing fonts to operate on.
                Should be the same context used for execute().

        Returns:
            CommandResult with success status and optional message.

        Note:
            This method should only be called after execute().
            Behavior is undefined if called before execute().
        """
        pass

    def __repr__(self) -> str:
        """Return string representation of command."""
        return f"{self.__class__.__name__}({self.description})"

