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

__version__ = "0.8.0"
__author__ = "Alexander Lubovenko"

# Core components
# Commands
# Beam measurement (margins at a height)
from .beam import beam_margins
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
from .commands.rules import (
    RemoveMetricsRuleCommand,
    SetMetricsRuleCommand,
    SyncRulesCommand,
)
from .contexts import FontContext
from .editors.kerning import KerningEditor
from .editors.margins import MarginsEditor
from .editors.spacing import SpacingEditor

# Glyphs.app metrics keys
from .glyphs_keys import (
    GLYPHS_GLYPH_KEY,
    GLYPHS_LAYER_KEY,
    glyphs_key_from_rule,
    rules_from_glyphs_keys,
)

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

# Margins utilities
from .margins_utils import (
    get_angled_margins,
    get_italic_angle,
    get_slant_factor,
    get_unskewed_bounds,
    set_angled_left_margin,
    set_angled_right_margin,
)

# Margin planner
from .planner import (
    BrokenRule,
    GlyphChange,
    MarginReader,
    OutOfSync,
    Plan,
    RulesStatus,
    angled_margins,
    apply_plan,
    build_reverse_component_map,
    check_rules,
    component_shift,
    margin_reader,
    plan_margin_edit,
    plan_restore,
    plan_sync,
    upright_margins,
)

# Metrics rules
from .rules_core import (
    # Issue codes
    E_CYCLE,
    E_PARSE_ERROR,
    I_SINGLE_COMPONENT,
    W_AMBIGUOUS_NAME,
    W_COMPONENT_WIDER,
    W_EMPTY_GLYPH,
    W_EVALUATION_FAILED,
    W_EXTENDS_LEFT,
    W_EXTENDS_RIGHT,
    W_MISSING_BASE,
    W_MISSING_GLYPH,
    W_MIXED_CONTOURS,
    W_MULTI_BODY,
    W_NO_OUTLINE_AT_HEIGHT,
    W_READER_NO_HEIGHT,
    W_RULE_OVERRIDDEN,
    W_SELF_REFERENCE,
    W_WIDTH_RIGHT_CONFLICT,
    W_ZERO_WIDTH,
    RuleIssue,
    ValidationReport,
)
from .rules_generator import (
    RuleGenerationResult,
    RuleWarning,  # Backwards compatibility alias
    generate_rules_from_composites,
)
from .rules_manager import MetricsRulesManager

# Virtual font for preview/simulation
from .virtual import VirtualFont, VirtualGroups, VirtualKerning

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
    # Margins Utilities
    "get_italic_angle",
    "get_slant_factor",
    "get_unskewed_bounds",
    "get_angled_margins",
    "set_angled_left_margin",
    "set_angled_right_margin",
    # Commands - Rules
    "SetMetricsRuleCommand",
    "RemoveMetricsRuleCommand",
    "SyncRulesCommand",
    # Metrics Rules
    "MetricsRulesManager",
    "ValidationReport",
    "RuleIssue",
    # Issue Codes
    "E_PARSE_ERROR",
    "E_CYCLE",
    "W_MISSING_GLYPH",
    "W_SELF_REFERENCE",
    "W_COMPONENT_WIDER",
    "W_EXTENDS_LEFT",
    "W_EXTENDS_RIGHT",
    "W_ZERO_WIDTH",
    "W_MIXED_CONTOURS",
    "W_MISSING_BASE",
    "W_MULTI_BODY",
    "W_RULE_OVERRIDDEN",
    "W_EMPTY_GLYPH",
    "W_EVALUATION_FAILED",
    "W_AMBIGUOUS_NAME",
    "W_WIDTH_RIGHT_CONFLICT",
    "W_NO_OUTLINE_AT_HEIGHT",
    "W_READER_NO_HEIGHT",
    # Glyphs.app metrics keys
    "rules_from_glyphs_keys",
    "glyphs_key_from_rule",
    "GLYPHS_GLYPH_KEY",
    "GLYPHS_LAYER_KEY",
    "I_SINGLE_COMPONENT",
    # Planner
    "plan_margin_edit",
    "plan_sync",
    "plan_restore",
    "check_rules",
    "apply_plan",
    "Plan",
    "GlyphChange",
    "RulesStatus",
    "OutOfSync",
    "BrokenRule",
    "MarginReader",
    "upright_margins",
    "margin_reader",
    "beam_margins",
    "angled_margins",
    "component_shift",
    "build_reverse_component_map",
    # Rules Generator
    "generate_rules_from_composites",
    "RuleGenerationResult",
    "RuleWarning",  # Backwards compatibility
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

