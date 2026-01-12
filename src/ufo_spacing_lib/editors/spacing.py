"""
Spacing Editor Module.

This module provides the SpacingEditor class - a unified editor for managing
kerning, margins, groups, and metrics rules operations with full undo/redo support.

The editor acts as a command executor and history manager. It encapsulates
font context and rules managers, providing a simple API for host applications.

Example:
    Basic usage with fonts:

    >>> from ufo_spacing_lib import SpacingEditor
    >>> from ufo_spacing_lib import AdjustMarginCommand, SetMetricsRuleCommand
    >>>
    >>> # Create editor with font
    >>> editor = SpacingEditor(font)
    >>>
    >>> # Execute margin command
    >>> cmd = AdjustMarginCommand("A", "left", delta=10)
    >>> editor.execute(cmd)
    >>>
    >>> # Execute rule command
    >>> cmd = SetMetricsRuleCommand("Aacute", "both", "=A")
    >>> editor.execute(cmd)
    >>>
    >>> # Undo
    >>> editor.undo()

    Multi-font usage:

    >>> editor = SpacingEditor(
    ...     [light_font, bold_font],
    ...     scales={light_font: 1.0, bold_font: 1.2}
    ... )
    >>> editor.execute(AdjustMarginCommand("A", "left", 10))

Event Callbacks:
    The editor supports event callbacks for integration with UI:

    >>> def on_change(command, result):
    ...     refresh_ui()
    ...     update_undo_menu()
    >>>
    >>> editor.on_change = on_change
    >>> editor.on_undo = on_change
    >>> editor.on_redo = on_change
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..commands.base import Command, CommandResult
from ..commands.margins import AdjustMarginCommand, SetMarginCommand
from ..commands.rules import (
    RemoveMetricsRuleCommand,
    SetMetricsRuleCommand,
    SyncRulesCommand,
)
from ..contexts import FontContext
from ..rules_manager import MetricsRulesManager


class SpacingEditor:
    """
    Unified editor for spacing operations with undo/redo support.

    The SpacingEditor manages execution of all spacing-related commands
    (kerning, margins, groups, rules) and maintains a single history stack for
    undo/redo operations. This ensures consistent undo behavior when
    operations affect multiple aspects.

    The editor encapsulates FontContext and MetricsRulesManager instances,
    providing a simple API for host applications. Each font in the editor
    has its own rules manager with independent rules.

    Attributes:
        on_change: Optional callback called after successful execute().
            Signature: (command: Command, result: CommandResult) -> None
        on_undo: Optional callback called after successful undo().
            Signature: (command: Command, result: CommandResult) -> None
        on_redo: Optional callback called after successful redo().
            Signature: (command: Command, result: CommandResult) -> None

    Example:
        Creating and using an editor:

        >>> editor = SpacingEditor(font)
        >>>
        >>> # Execute commands - context is handled internally
        >>> editor.execute(AdjustMarginCommand("A", "left", 10))
        >>>
        >>> # Work with rules
        >>> editor.execute(SetMetricsRuleCommand("Aacute", "left", "=A"))
        >>>
        >>> # Undo works for all command types
        >>> editor.undo()

    Note:
        History is unlimited by default. For very long sessions,
        consider periodically calling clear_history() to free memory.
    """

    def __init__(
        self,
        fonts: Any | list[Any] | None = None,
        *,
        primary_font: Any | None = None,
        scales: dict[Any, float] | None = None,
    ):
        """
        Initialize the SpacingEditor.

        Args:
            fonts: Font or list of fonts to operate on. If None, the editor
                operates in legacy mode where context must be passed to execute().
            primary_font: The primary font for lookups (for multi-font).
                Defaults to first font.
            scales: Optional dict of scale factors per font for interpolation.

        Example:
            Single font:
            >>> editor = SpacingEditor(font)

            Multiple fonts with scaling:
            >>> editor = SpacingEditor(
            ...     [light, bold],
            ...     scales={light: 1.0, bold: 1.2}
            ... )
        """
        # Normalize fonts input
        if fonts is None:
            font_list = []
        elif isinstance(fonts, list):
            font_list = fonts
        else:
            font_list = [fonts]

        # Create internal context (may be empty for legacy mode)
        if font_list:
            self._context = FontContext(
                fonts=font_list,
                primary_font=primary_font or font_list[0],
                scales=scales or {},
            )
        else:
            self._context = None

        # Create rules manager for each font
        self._rules_managers: dict[int, MetricsRulesManager] = {}
        for font in font_list:
            self._rules_managers[id(font)] = MetricsRulesManager(font)

        # Active fonts (None = all fonts)
        self._active_fonts: list[Any] | None = None

        # History stacks
        self._history: list[tuple[Command, FontContext]] = []
        self._redo_stack: list[tuple[Command, FontContext]] = []

        # Event callbacks
        self.on_change: Callable[[Command, CommandResult], None] | None = None
        self.on_undo: Callable[[Command, CommandResult], None] | None = None
        self.on_redo: Callable[[Command, CommandResult], None] | None = None

    # =========================================================================
    # Font Access Properties
    # =========================================================================

    @property
    def font(self) -> Any | None:
        """
        Primary font (convenience for single-font case).

        Returns:
            Primary font or None if no fonts configured.
        """
        if self._context:
            return self._context.primary_font
        return None

    @property
    def fonts(self) -> list[Any]:
        """
        All fonts in the editor.

        Returns:
            List of all fonts.
        """
        if self._context:
            return self._context.fonts
        return []

    @property
    def active_fonts(self) -> list[Any]:
        """
        Fonts that commands will apply to.

        Returns:
            List of active fonts (all fonts if not explicitly set).
        """
        if self._active_fonts is not None:
            return self._active_fonts
        return self.fonts

    def set_active_fonts(self, fonts: list[Any] | Any | None = None) -> None:
        """
        Set which fonts commands apply to.

        Args:
            fonts: List of fonts, single font, or None for all fonts.

        Example:
            >>> editor.set_active_fonts([bold_font])  # Only bold
            >>> editor.set_active_fonts(None)  # All fonts
        """
        if fonts is None:
            self._active_fonts = None
        elif isinstance(fonts, list):
            self._active_fonts = fonts
        else:
            self._active_fonts = [fonts]

    # =========================================================================
    # Rules Manager Access
    # =========================================================================

    def get_rules_manager(self, font: Any | None = None) -> MetricsRulesManager:
        """
        Get rules manager for a font.

        Args:
            font: Font to get manager for. If None, returns manager for
                primary font.

        Returns:
            MetricsRulesManager for the font.

        Raises:
            KeyError: If font not found in editor.
            ValueError: If no fonts configured.

        Example:
            >>> manager = editor.get_rules_manager()
            >>> rules = manager.get_all_rules()
        """
        if font is None:
            if self._context is None:
                raise ValueError("No fonts configured in editor")
            font = self._context.primary_font

        font_id = id(font)
        if font_id not in self._rules_managers:
            raise KeyError("Font not found in editor")

        return self._rules_managers[font_id]

    # =========================================================================
    # Command Execution
    # =========================================================================

    def execute(
        self,
        command: Command,
        context: FontContext | None = None,
        *,
        font: Any | None = None,
        fonts: list[Any] | None = None,
    ) -> CommandResult:
        """
        Execute a command and add it to history.

        Executes the given command with the determined context.
        If successful, the command is added to the undo history
        and the redo stack is cleared.

        Args:
            command: The command to execute.
            context: Optional font context (for backward compatibility).
                If provided, overrides font/fonts parameters.
            font: Optional single font override.
            fonts: Optional multiple fonts override.

        If neither context, font, nor fonts is specified, uses active_fonts.

        Returns:
            CommandResult from the command execution.

        Example:
            >>> # Using internal context (recommended)
            >>> editor.execute(AdjustMarginCommand("A", "left", 10))
            >>>
            >>> # Override to specific font
            >>> editor.execute(cmd, font=bold_font)
            >>>
            >>> # Legacy mode with explicit context
            >>> editor.execute(cmd, context)

        Note:
            Failed commands are not added to history.
        """
        # Determine execution context
        if context is not None:
            # Legacy mode: use provided context
            exec_context = context
        else:
            # New mode: build context from editor state
            exec_context = self._build_execution_context(font, fonts)

        # Execute command with appropriate handling
        if self._is_rules_command(command):
            result = command.execute(exec_context, self._rules_managers)
        elif self._is_margin_command(command):
            # Pass rules managers for cascade if apply_rules is True
            rules_managers = None
            if getattr(command, 'apply_rules', False):
                rules_managers = self._rules_managers
            result = command.execute(exec_context, rules_managers)
        else:
            result = command.execute(exec_context)

        if result.success:
            # Add to history
            self._history.append((command, exec_context))

            # Clear redo stack (new action invalidates redo)
            self._redo_stack.clear()

            # Notify listeners
            if self.on_change:
                self.on_change(command, result)

        return result

    def _build_execution_context(
        self,
        font: Any | None,
        fonts: list[Any] | None,
    ) -> FontContext:
        """Build FontContext for command execution."""
        if self._context is None:
            raise ValueError(
                "No fonts configured. Either pass context to execute() "
                "or initialize SpacingEditor with fonts."
            )

        # Determine target fonts
        if font is not None:
            target_fonts = [font]
        elif fonts is not None:
            target_fonts = fonts
        else:
            target_fonts = self.active_fonts

        # Create execution context
        return FontContext(
            fonts=target_fonts,
            primary_font=target_fonts[0] if target_fonts else None,
            scales={f: self._context.get_scale(f) for f in target_fonts},
        )

    def _is_rules_command(self, command: Command) -> bool:
        """Check if command requires rules managers."""
        return isinstance(
            command, (SetMetricsRuleCommand, RemoveMetricsRuleCommand, SyncRulesCommand)
        )

    def _is_margin_command(self, command: Command) -> bool:
        """Check if command is a margin command (may need rules manager)."""
        return isinstance(command, (SetMarginCommand, AdjustMarginCommand))

    # =========================================================================
    # Undo / Redo
    # =========================================================================

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
            ...     result = editor.undo()
            ...     print(f"Undid: {result.message}")
        """
        if not self._history:
            return None

        # Pop from history
        command, context = self._history.pop()

        # Execute undo with appropriate handling
        if self._is_rules_command(command):
            result = command.undo(context, self._rules_managers)
        elif self._is_margin_command(command):
            # Margin commands accept rules_manager for API consistency
            result = command.undo(context)
        else:
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
            ...     result = editor.redo()
            ...     print(f"Redid: {result.message}")
        """
        if not self._redo_stack:
            return None

        # Pop from redo stack
        command, context = self._redo_stack.pop()

        # Re-execute with appropriate handling
        if self._is_rules_command(command):
            result = command.execute(context, self._rules_managers)
        elif self._is_margin_command(command):
            # Pass rules managers for cascade if apply_rules is True
            rules_managers = None
            if getattr(command, 'apply_rules', False):
                rules_managers = self._rules_managers
            result = command.execute(context, rules_managers)
        else:
            result = command.execute(context)

        # Push to history
        self._history.append((command, context))

        # Notify listeners
        if self.on_redo:
            self.on_redo(command, result)

        return result

    # =========================================================================
    # History Properties
    # =========================================================================

    @property
    def can_undo(self) -> bool:
        """
        Check if there are commands to undo.

        Returns:
            True if undo() will have an effect.

        Example:
            >>> undo_button.enabled = editor.can_undo
        """
        return len(self._history) > 0

    @property
    def can_redo(self) -> bool:
        """
        Check if there are commands to redo.

        Returns:
            True if redo() will have an effect.

        Example:
            >>> redo_button.enabled = editor.can_redo
        """
        return len(self._redo_stack) > 0

    @property
    def undo_description(self) -> str | None:
        """
        Get the description of the command that would be undone.

        Returns:
            Description string, or None if nothing to undo.

        Example:
            >>> menu_item.title = f"Undo {editor.undo_description}"
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

        Example:
            >>> menu_item.title = f"Redo {editor.redo_description}"
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

    def clear_history(self) -> None:
        """
        Clear all undo/redo history.

        Use this to free memory in long sessions or when
        starting a new editing context.

        Example:
            >>> # Starting fresh
            >>> editor.clear_history()
        """
        self._history.clear()
        self._redo_stack.clear()

    def get_history(self) -> list[str]:
        """
        Get descriptions of all commands in history.

        Returns:
            List of command descriptions, oldest first.

        Example:
            >>> for desc in editor.get_history():
            ...     print(desc)
        """
        return [cmd.description for cmd, ctx in self._history]

    def __repr__(self) -> str:
        """Return string representation of the editor."""
        font_count = len(self.fonts)
        return (
            f"SpacingEditor(fonts={font_count}, "
            f"history={len(self._history)}, "
            f"redo={len(self._redo_stack)})"
        )
