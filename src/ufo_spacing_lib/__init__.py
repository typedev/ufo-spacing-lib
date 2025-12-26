"""
UFO Spacing Library - Font spacing and metrics management.

A framework-agnostic library for managing font kerning and margins
with undo/redo support, designed to work with any font editor that
provides a compatible font interface.

Main Components:
    - FontContext: Context for multi-font operations
    - KerningEditor: Editor with undo/redo for kerning operations
    - MarginsEditor: Editor with undo/redo for margins operations
    - FontGroupsManager: Groups management with reverse lookup
    - Commands: Undoable command classes for all operations

Quick Start:
    >>> from ufo_spacing_lib import KerningEditor, FontContext, AdjustKerningCommand
    >>>
    >>> # Create editor
    >>> editor = KerningEditor()
    >>>
    >>> # Create context (single font)
    >>> context = FontContext.from_single_font(font)
    >>>
    >>> # Execute command
    >>> command = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
    >>> result = editor.execute(command, context)
    >>>
    >>> # Undo
    >>> editor.undo()

Compatibility:
    This library is designed to work with any font object that implements:
    - font.kerning: dict-like with __getitem__, __setitem__, __delitem__, __contains__
    - font.groups: dict-like for group management
    - font[glyph_name]: access to glyph objects (for margins)
    - glyph.leftMargin, glyph.rightMargin, glyph.width (for margins)

License:
    MIT License

Author:
    Alexander Lubovenko (typedev)
"""

__version__ = "0.2.0"
__author__ = "Alexander Lubovenko"

# Core components
# Commands
from .commands.base import Command, CommandResult
from .commands.groups import (
    AddGlyphsToGroupCommand,
    DeleteGroupCommand,
    RemoveGlyphsFromGroupCommand,
    RenameGroupCommand,
)
from .commands.kerning import (
    AdjustKerningCommand,
    CreateExceptionCommand,
    RemoveKerningCommand,
    SetKerningCommand,
)
from .commands.margins import (
    AdjustMarginCommand,
    SetMarginCommand,
)
from .contexts import FontContext
from .editors.kerning import KerningEditor
from .editors.margins import MarginsEditor
from .editors.spacing import SpacingEditor

# Virtual font for preview/simulation
from .virtual import VirtualFont, VirtualGroups, VirtualKerning

# Groups management
from .groups_core import (
    EDITMODE_KERNING,
    EDITMODE_MARGINS,
    EDITMODE_OFF,
    # Constants
    SIDE_LEFT,
    SIDE_RIGHT,
    ExceptionSide,
    FontGroupsManager,
    KerningGroupsIndex,
    KernPairInfo,
    # Backward compatibility
    TDHashGroupsDic,
    researchPair,
    resolve_kern_pair,
)

__all__ = [
    # Version
    "__version__",
    # Contexts
    "FontContext",
    # Virtual font
    "VirtualFont",
    "VirtualKerning",
    "VirtualGroups",
    # Editors
    "KerningEditor",
    "MarginsEditor",
    "SpacingEditor",
    # Commands - Base
    "Command",
    "CommandResult",
    # Commands - Kerning
    "SetKerningCommand",
    "AdjustKerningCommand",
    "RemoveKerningCommand",
    "CreateExceptionCommand",
    # Commands - Groups
    "AddGlyphsToGroupCommand",
    "RemoveGlyphsFromGroupCommand",
    "DeleteGroupCommand",
    "RenameGroupCommand",
    # Commands - Margins
    "SetMarginCommand",
    "AdjustMarginCommand",
    # Groups
    "FontGroupsManager",
    "KernPairInfo",
    "ExceptionSide",
    "resolve_kern_pair",
    # Constants
    "SIDE_LEFT",
    "SIDE_RIGHT",
    "EDITMODE_OFF",
    "EDITMODE_KERNING",
    "EDITMODE_MARGINS",
    # Backward compatibility
    "TDHashGroupsDic",
    "KerningGroupsIndex",
    "researchPair",
]

