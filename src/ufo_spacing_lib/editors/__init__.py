"""
Editors Package.

This package contains editor classes that manage command execution
and undo/redo history.

Editors:
    - KerningEditor: Editor for kerning operations
    - MarginsEditor: Editor for margins operations

Both editors provide:
    - Command execution with automatic history tracking
    - Unlimited undo/redo
    - Event callbacks for change notification
    - History inspection (can_undo, undo_description, etc.)

Example:
    >>> from ufo_spacing_lib.editors import KerningEditor
    >>>
    >>> editor = KerningEditor()
    >>>
    >>> # Set up change notification
    >>> def on_change(command, result):
    ...     print(f"Changed: {command.description}")
    >>> editor.on_change = on_change
    >>>
    >>> # Execute commands
    >>> editor.execute(command, context)
    >>>
    >>> # Undo/redo
    >>> editor.undo()
    >>> editor.redo()
"""

from .kerning import KerningEditor
from .margins import MarginsEditor
from .spacing import SpacingEditor

__all__ = [
    "KerningEditor",
    "MarginsEditor",
    "SpacingEditor",
]

