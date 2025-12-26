"""
Commands Package.

This package contains all command classes for undoable operations.

Commands follow the Command Pattern, providing:
- execute(): Perform the operation
- undo(): Reverse the operation
- description: Human-readable description for UI

Available Commands:
    Kerning:
        - SetKerningCommand: Set kerning to absolute value
        - AdjustKerningCommand: Adjust kerning by delta
        - RemoveKerningCommand: Remove a kerning pair
        - CreateExceptionCommand: Create kerning exception from group

    Groups:
        - AddGlyphsToGroupCommand: Add glyphs to a kerning group
        - RemoveGlyphsFromGroupCommand: Remove glyphs from a kerning group
        - DeleteGroupCommand: Delete a kerning group
        - RenameGroupCommand: Rename a kerning group

    Margins:
        - SetMarginCommand: Set margin to absolute value
        - AdjustMarginCommand: Adjust margin by delta

Example:
    >>> from ufo_spacing_lib.commands import AdjustKerningCommand
    >>>
    >>> cmd = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
    >>> result = cmd.execute(context)
    >>> cmd.undo(context)  # Reverse the change
"""

from .base import Command, CommandResult
from .groups import (
    AddGlyphsToGroupCommand,
    DeleteGroupCommand,
    RemoveGlyphsFromGroupCommand,
    RenameGroupCommand,
)
from .kerning import (
    AdjustKerningCommand,
    CreateExceptionCommand,
    RemoveKerningCommand,
    SetKerningCommand,
)
from .margins import (
    AdjustMarginCommand,
    SetMarginCommand,
)

__all__ = [
    # Base
    "Command",
    "CommandResult",
    # Kerning
    "SetKerningCommand",
    "AdjustKerningCommand",
    "RemoveKerningCommand",
    "CreateExceptionCommand",
    # Groups
    "AddGlyphsToGroupCommand",
    "RemoveGlyphsFromGroupCommand",
    "DeleteGroupCommand",
    "RenameGroupCommand",
    # Margins
    "SetMarginCommand",
    "AdjustMarginCommand",
]

