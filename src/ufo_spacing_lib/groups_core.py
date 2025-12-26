"""
Groups Core Module.

This module provides font groups management and kerning pair analysis.

Main Components:
    FontGroupsManager: Centralized management of kerning and margins groups
        with reverse lookup, automatic kerning handling, and operation logging.

    KernPairInfo: Structured dataclass for kerning pair information,
        returned by resolve_kern_pair().

    ExceptionSide: Enum describing which side of a kerning pair has
        an exception.

    resolve_kern_pair(): Function to analyze a kerning pair and return
        detailed information about its resolution.

Example:
    >>> from ufo_spacing_lib import FontGroupsManager, resolve_kern_pair
    >>>
    >>> # Create manager for a font
    >>> manager = FontGroupsManager(font)
    >>>
    >>> # Look up group for a glyph
    >>> group = manager.get_group_for_glyph('A', SIDE_LEFT)
    >>>
    >>> # Add glyphs to a group
    >>> skipped, new_pairs, deleted = manager.add_glyphs_to_group(
    ...     'public.kern1.A', ['Aacute', 'Agrave']
    ... )
    >>>
    >>> # Analyze a kerning pair
    >>> info = resolve_kern_pair(font, manager, ('A', 'V'))
    >>> print(f"Value: {info.value}, Exception: {info.is_exception}")

Backward Compatibility:
    The following aliases are provided for backward compatibility:
    - TDHashGroupsDic → FontGroupsManager
    - KerningGroupsIndex → FontGroupsManager
    - researchPair → resolve_kern_pair
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Avoid circular imports, these are only for type hints
    pass


# =============================================================================
# Constants
# =============================================================================

# Side identifiers
SIDE_LEFT = "L"
SIDE_RIGHT = "R"
SIDE_1 = SIDE_LEFT  # Alias for compatibility
SIDE_2 = SIDE_RIGHT  # Alias for compatibility

# Edit modes
EDITMODE_OFF = 0
EDITMODE_KERNING = 1
EDITMODE_MARGINS = 2

# Group prefixes
ID_KERNING_GROUP = "public.kern"
ID_MARGINS_GROUP = "com.typedev.margins"
ID_GROUP_LEFT = "kern1"
ID_MARGINS_GROUP_LEFT = "margins1"

# Pair info types (for sorting and display)
PAIR_INFO_NONE = 0
PAIR_INFO_ATTENTION = 10  # Unusual state - needs attention
PAIR_INFO_EXCEPTION = 20  # Normal exception (one side differs)
PAIR_INFO_ORPHAN = 30  # Both sides differ from groups
PAIR_INFO_EMPTY = 40  # Empty group
PAIR_INFO_ERROR = 90  # Error state
PAIR_INFO_EXCEPTION_DELETED = 100  # Exception was deleted

# Group check results
GROUP_IS_EMPTY = 1
GROUP_MISSING_GLYPH = 2
GROUP_NOT_FOUNDED = 3


# =============================================================================
# Exception Side Enum
# =============================================================================


class ExceptionSide(Enum):
    """
    Describes the exception status of a resolved kerning pair.

    This enum is returned by KernPairInfo.exception_side property after
    resolve_kern_pair() processes a glyph pair.

    Values:
        NONE: Input glyph names resolved to groups, and the group-group pair
              exists in kerning. This is the normal case - not an exception.

        LEFT: Left side is an exception. The left glyph belongs to a group,
              but a specific glyph-group pair exists in kerning instead of
              the group-group pair.

        RIGHT: Right side is an exception. The right glyph belongs to a group,
               but a specific group-glyph pair exists in kerning.

        BOTH: Both sides are exceptions (orphan pair). Both glyphs belong to
              groups, but a specific glyph-glyph pair exists in kerning.

        DIRECT_KEY: Input was already kerning keys (group names), not glyph names.
                    The pair exists in kerning as given. This typically occurs
                    when resolve_kern_pair() is called with group names like
                    ('public.kern1.A', 'public.kern2.t') instead of glyph names.
                    Not an exception in the traditional sense, but indicates
                    unusual input that may need attention.

    Note:
        For most UI purposes, both NONE and DIRECT_KEY mean "not an exception".
        The distinction exists because DIRECT_KEY indicates the input wasn't
        resolved (it was already in key form), which may be relevant for
        debugging or validation.
    """

    NONE = auto()
    LEFT = auto()
    RIGHT = auto()
    BOTH = auto()
    DIRECT_KEY = auto()

    # Backward compatibility alias
    GLYPH_PAIR = DIRECT_KEY


# =============================================================================
# KernPairInfo Dataclass
# =============================================================================


@dataclass(slots=True, frozen=True)
class KernPairInfo:
    """
    Structured information about a kerning pair.

    This replaces the old dictionary return type from researchPair().

    Field name mapping from old code:
        L_realName    → left
        R_realName    → right
        kernValue     → value
        exception     → is_exception
        L_nameForKern → left_group
        R_nameForKern → right_group

    Removed unused fields:
        L_inGroup, R_inGroup, L_markException, R_markException
    """

    left: str  # Actual left key in kerning dict (glyph or group name)
    right: str  # Actual right key in kerning dict
    value: int | None  # Kerning value (None if not found)
    is_exception: bool  # True if this is an exception to group kerning
    left_group: str  # Group name for left glyph (or glyph name if not in group)
    right_group: str  # Group name for right glyph (or glyph name if not in group)

    @property
    def exception_side(self) -> ExceptionSide:
        """
        Determines which side has the exception.

        Returns:
            ExceptionSide.NONE: No exception (normal group-group pair)
            ExceptionSide.LEFT: Exception on left side only
            ExceptionSide.RIGHT: Exception on right side only
            ExceptionSide.BOTH: Exception on both sides (orphan)
            ExceptionSide.DIRECT_KEY: Input was already kerning keys (group names)
        """
        if not self.is_exception:
            return ExceptionSide.NONE

        left_differs = self.left != self.left_group
        right_differs = self.right != self.right_group

        if not left_differs and not right_differs:
            return ExceptionSide.DIRECT_KEY
        if left_differs and not right_differs:
            return ExceptionSide.LEFT
        if right_differs and not left_differs:
            return ExceptionSide.RIGHT
        return ExceptionSide.BOTH

    @property
    def is_left_exception(self) -> bool:
        """Is this a left-side only exception?"""
        return self.exception_side == ExceptionSide.LEFT

    @property
    def is_right_exception(self) -> bool:
        """Is this a right-side only exception?"""
        return self.exception_side == ExceptionSide.RIGHT

    @property
    def is_orphan(self) -> bool:
        """Is this an orphan (both sides differ from groups)?"""
        return self.exception_side == ExceptionSide.BOTH

    @property
    def has_value(self) -> bool:
        """Does this pair have a kerning value?"""
        return self.value is not None


# =============================================================================
# Helper Functions
# =============================================================================


def cut_unique_suffix(name: str) -> str:
    """
    Remove unique numeric suffix from glyph name.

    Examples:
        'A.uuid12345' → 'A'
        'A.ss01'  → 'A.ss01' (not numeric, kept)
        'A'       → 'A'
    """
    if ".uuid" in name:
        parts = name.rsplit(".uuid", 1)
        if parts[1].isdigit():
            return parts[0]
    return name


# Alias for backward compatibility
cutUniqName = cut_unique_suffix


# =============================================================================
# FontGroupsManager - Font Groups Manager with Reverse Lookup
# =============================================================================


class FontGroupsManager:
    """
    Font groups manager with reverse lookup and kerning handling.

    This class provides centralized management of kerning and margins groups
    in a font, including:

    - Reverse mappings (glyph → group) for O(1) lookups instead of
      iterating through all groups
    - CRUD operations for group membership (add/remove/reposition glyphs)
    - Automatic kerning handling when modifying groups:
        * Creating exceptions when removing glyphs from groups
        * Merging or preserving kerning when adding glyphs to groups
        * Updating kerning references when renaming/deleting groups
    - Group validation (empty groups, missing glyphs)
    - Language compatibility checking for kerning pairs
    - Operation history tracking for undo support

    Supports both kerning groups (public.kern1.*, public.kern2.*) and
    margins groups (com.typedev.margins1.*, com.typedev.margins2.*).

    Attributes:
        font: The RoboFont font object being managed
        lang_set: Optional language compatibility checker
        groups_with_errors: List of group names with validation errors

    Example:
        >>> manager = FontGroupsManager(font, lang_set)
        >>> group_name = manager.get_group_for_glyph('A', SIDE_LEFT)
        >>> skipped, new_pairs, deleted = manager.add_glyphs_to_group(
        ...     'public.kern1.A', ['Aacute', 'Agrave'], check_kerning=True
        ... )
    """

    def __init__(self, font, lang_set=None):
        """
        Initialize the hash dictionary for a font.

        Args:
            font: RoboFont font object
            lang_set: Optional language compatibility checker
        """
        self.font = font
        self.lang_set = lang_set

        # Reverse mappings: glyph_name → group_name
        self._left_kern_groups: dict[str, str] = {}
        self._right_kern_groups: dict[str, str] = {}
        self._left_margins_groups: dict[str, str] = {}
        self._right_margins_groups: dict[str, str] = {}

        # First glyph in each group (key glyph)
        self._key_glyphs: dict[str, str] = {}

        # History for undo operations
        self._history: list[tuple] = []
        self._track_history: bool = True

        # Groups with errors (empty or missing glyphs)
        self.groups_with_errors: list[str] = []

        # Logging system
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._logger.addHandler(logging.NullHandler())
        self._collect_log: bool = False
        self._operation_log: list[tuple] = []

        # Build the mappings
        self._build_reverse_mapping()

    # -------------------------------------------------------------------------
    # Properties for backward compatibility
    # -------------------------------------------------------------------------

    @property
    def leftDic(self) -> dict[str, str]:
        """Backward compatibility: left kerning groups mapping."""
        return self._left_kern_groups

    @property
    def rightDic(self) -> dict[str, str]:
        """Backward compatibility: right kerning groups mapping."""
        return self._right_kern_groups

    @property
    def leftMarginsDic(self) -> dict[str, str]:
        """Backward compatibility: left margins groups mapping."""
        return self._left_margins_groups

    @property
    def rightMarginsDic(self) -> dict[str, str]:
        """Backward compatibility: right margins groups mapping."""
        return self._right_margins_groups

    @property
    def dicOfKeyGlyphsByGroup(self) -> dict[str, str]:
        """Backward compatibility: key glyphs mapping."""
        return self._key_glyphs

    @property
    def history(self) -> list[tuple]:
        """Backward compatibility: history list."""
        return self._history

    @property
    def trackHistory(self) -> bool:
        """Backward compatibility: track history flag."""
        return self._track_history

    @trackHistory.setter
    def trackHistory(self, value: bool):
        self._track_history = value

    @property
    def groupsHasErrorList(self) -> list[str]:
        """Backward compatibility: groups with errors."""
        return self.groups_with_errors

    # -------------------------------------------------------------------------
    # Setup and Configuration
    # -------------------------------------------------------------------------

    def set_font(self, font, lang_set=None):
        """
        Reinitialize for a new font.

        Args:
            font: New RoboFont font object
            lang_set: Optional language compatibility checker
        """
        self.font = font
        self.lang_set = lang_set
        self._history = []
        self.groups_with_errors = []
        self._build_reverse_mapping()

    # Backward compatibility alias
    setFont = set_font

    def clear_history(self):
        """Clear the operation history."""
        self._history = []

    clearHistory = clear_history  # Alias

    def pause_history(self):
        """Temporarily stop tracking history."""
        self._track_history = False

    setHistoryPause = pause_history  # Alias

    def resume_history(self):
        """Resume tracking history."""
        self._track_history = True

    setHistoryResume = resume_history  # Alias

    # -------------------------------------------------------------------------
    # Logging System
    # -------------------------------------------------------------------------

    def _log(self, action: str, *details):
        """
        Log an operation. Fast no-op when logging is disabled.

        Args:
            action: Action name (e.g., 'kerning_copied', 'glyph_added')
            *details: Additional details about the operation
        """
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug(f"{action}: {details}")

        if self._collect_log:
            self._operation_log.append((action, *details))

    def start_collecting_log(self):
        """
        Start collecting operations for later retrieval.

        Use this before performing operations when you need to
        show results to the user.
        """
        self._collect_log = True
        self._operation_log.clear()

    def stop_collecting_log(self) -> list[tuple]:
        """
        Stop collecting and return collected operations.

        Returns:
            List of operation tuples: [(action, detail1, detail2, ...), ...]
        """
        self._collect_log = False
        result = self._operation_log.copy()
        self._operation_log.clear()
        return result

    def get_operation_log(self) -> list[tuple]:
        """
        Get the current operation log without clearing it.

        Returns:
            List of operation tuples
        """
        return self._operation_log.copy()

    # -------------------------------------------------------------------------
    # Group Type Checks
    # -------------------------------------------------------------------------

    def is_left_side_group(self, group_name: str) -> bool:
        """Check if this is a left-side group (kern1 or margins1)."""
        return ID_GROUP_LEFT in group_name or ID_MARGINS_GROUP_LEFT in group_name

    isLeftSideGroup = is_left_side_group  # Alias

    def is_kerning_group(self, group_name: str) -> bool:
        """Check if this is a kerning group."""
        return group_name.startswith(ID_KERNING_GROUP)

    isKerningGroup = is_kerning_group  # Alias

    def is_margins_group(self, group_name: str) -> bool:
        """Check if this is a margins group."""
        return group_name.startswith(ID_MARGINS_GROUP)

    isMarginsGroup = is_margins_group  # Alias

    # -------------------------------------------------------------------------
    # Mapping Operations
    # -------------------------------------------------------------------------

    def _build_reverse_mapping(self):
        """Build reverse mappings from glyph names to group names."""
        self._left_kern_groups.clear()
        self._right_kern_groups.clear()
        self._left_margins_groups.clear()
        self._right_margins_groups.clear()
        self._key_glyphs.clear()

        for group_name, glyphs in self.font.groups.items():
            # Store key glyph (first in group)
            if glyphs:
                self._key_glyphs[group_name] = glyphs[0]
            else:
                self.groups_with_errors.append(group_name)
                continue

            # Determine group type and side, then build mapping
            if self.is_kerning_group(group_name):
                target_dict = (
                    self._left_kern_groups
                    if self.is_left_side_group(group_name)
                    else self._right_kern_groups
                )
            elif self.is_margins_group(group_name):
                target_dict = (
                    self._left_margins_groups
                    if self.is_left_side_group(group_name)
                    else self._right_margins_groups
                )
            else:
                continue

            for glyph_name in glyphs:
                if not self._add_to_mapping(target_dict, glyph_name, group_name):
                    # Glyph already in another group - error
                    pass
                if glyph_name not in self.font:
                    self.groups_with_errors.append(group_name)

    makeReverseGroupsMapping = _build_reverse_mapping  # Alias

    def _add_to_mapping(
        self, mapping: dict[str, str], glyph_name: str, group_name: str
    ) -> bool:
        """
        Add glyph to mapping, checking for conflicts.

        Returns:
            True if added successfully, False if glyph already in another group
        """
        if glyph_name not in mapping:
            mapping[glyph_name] = group_name
            return True
        else:
            print(
                f"ERROR: {glyph_name} already in group {mapping[glyph_name]} and {group_name}"
            )
            print("The extension may not work correctly.")
            return False

    checkMapAndAddGlyph2hashMap = _add_to_mapping  # Alias

    # -------------------------------------------------------------------------
    # Lookup Methods
    # -------------------------------------------------------------------------

    def get_group_for_glyph(
        self, glyph_name: str, side: str, mode: int = EDITMODE_KERNING
    ) -> str:
        """
        Get the group name for a glyph on a given side.

        Args:
            glyph_name: Name of the glyph
            side: SIDE_LEFT or SIDE_RIGHT
            mode: EDITMODE_KERNING or EDITMODE_MARGINS

        Returns:
            Group name if glyph is in a group, otherwise the glyph name itself
        """
        if mode == EDITMODE_KERNING:
            if side == SIDE_LEFT and glyph_name in self._left_kern_groups:
                return self._left_kern_groups[glyph_name]
            if side == SIDE_RIGHT and glyph_name in self._right_kern_groups:
                return self._right_kern_groups[glyph_name]
        elif mode == EDITMODE_MARGINS:
            if side == SIDE_LEFT and glyph_name in self._left_margins_groups:
                return self._left_margins_groups[glyph_name]
            if side == SIDE_RIGHT and glyph_name in self._right_margins_groups:
                return self._right_margins_groups[glyph_name]
        return glyph_name

    getGroupNameByGlyph = get_group_for_glyph  # Alias

    def is_glyph_in_group(
        self, glyph_name: str, side: str, mode: int = EDITMODE_KERNING
    ) -> bool:
        """Check if glyph is in any group on the given side."""
        if mode == EDITMODE_KERNING:
            if side == SIDE_LEFT:
                return glyph_name in self._left_kern_groups
            if side == SIDE_RIGHT:
                return glyph_name in self._right_kern_groups
        elif mode == EDITMODE_MARGINS:
            if side == SIDE_LEFT:
                return glyph_name in self._left_margins_groups
            if side == SIDE_RIGHT:
                return glyph_name in self._right_margins_groups
        return False

    thisGlyphInGroup = is_glyph_in_group  # Alias

    def get_key_glyph(self, group_name: str) -> str:
        """
        Get the key glyph (first glyph) for a group.

        Returns:
            Key glyph name, or group_name if not found
        """
        return self._key_glyphs.get(group_name, group_name)

    getKeyGlyphByGroupname = get_key_glyph  # Alias

    def get_pairs_by_key(
        self, key: str, side: str
    ) -> list[tuple[tuple[str, str], int]]:
        """
        Get all kerning pairs that contain a given key on a side.

        Args:
            key: Group or glyph name
            side: SIDE_LEFT or SIDE_RIGHT

        Returns:
            List of ((left, right), value) tuples
        """
        if side == SIDE_LEFT:
            return [
                (pair, val) for pair, val in self.font.kerning.items() if pair[0] == key
            ]
        elif side == SIDE_RIGHT:
            return [
                (pair, val) for pair, val in self.font.kerning.items() if pair[1] == key
            ]
        return []

    getPairsBy = get_pairs_by_key  # Alias

    # -------------------------------------------------------------------------
    # Group Validation
    # -------------------------------------------------------------------------

    def check_group_errors(self, group_name: str) -> int:
        """
        Check if a group has errors.

        Returns:
            0 if OK
            GROUP_IS_EMPTY if group is empty
            GROUP_MISSING_GLYPH if group contains non-existent glyphs
            GROUP_NOT_FOUNDED if group doesn't exist
        """
        if group_name not in self.font.groups:
            return GROUP_NOT_FOUNDED

        glyphs = self.font.groups[group_name]
        if len(glyphs) == 0:
            return GROUP_IS_EMPTY

        for glyph in glyphs:
            if glyph not in self.font:
                return GROUP_MISSING_GLYPH

        return 0

    checkGroupHasError = check_group_errors  # Alias

    # -------------------------------------------------------------------------
    # Language Compatibility
    # -------------------------------------------------------------------------

    def check_pair_language_compatibility(self, pair: tuple[str, str]) -> bool:
        """Check if a pair is language-compatible."""
        if self.lang_set:
            return self.lang_set.checkPairLanguageCompatibility(self.font, pair)
        return True

    checkPairLanguageCompatibility = check_pair_language_compatibility  # Alias

    def check_pair_compatibility_grouped(
        self, pair: tuple[str, str], level: int = 1
    ) -> bool:
        """
        Check pair compatibility using key glyphs if groups are involved.

        Args:
            pair: (left, right) tuple
            level: 1 for base scripts, 2 for full language check
        """
        if not self.lang_set:
            return True

        left, right = pair
        check_left = self.get_key_glyph(left) if self.is_kerning_group(left) else left
        check_right = (
            self.get_key_glyph(right) if self.is_kerning_group(right) else right
        )

        if level == 2:
            return self.lang_set.checkPairLanguageCompatibility(
                self.font, (check_left, check_right)
            )
        else:
            return self.lang_set.checkPairBaseScriptCompatibility(
                self.font, (check_left, check_right)
            )

    checkPairLanguageCompatibilityGroupped = check_pair_compatibility_grouped  # Alias

    # -------------------------------------------------------------------------
    # Group Modification Methods
    # -------------------------------------------------------------------------

    def _get_side_for_group(self, group_name: str) -> str:
        """Determine the side for a group based on its name."""
        return SIDE_LEFT if self.is_left_side_group(group_name) else SIDE_RIGHT

    def _is_glyph_in_group_for_side(
        self, glyph_name: str, side: str, mode: int = EDITMODE_KERNING
    ) -> bool:
        """Check if glyph is already in a group on the given side."""
        return self.is_glyph_in_group(glyph_name, side, mode)

    def copy_kerning(
        self,
        source_pair: tuple[str, str],
        dest_pair: tuple[str, str],
        check_language_compatibility: bool = False,
    ) -> bool:
        """
        Copy kerning value from source pair to destination pair.

        Args:
            source_pair: Source (left, right) pair
            dest_pair: Destination (left, right) pair
            check_language_compatibility: If True, check language compatibility before copying

        Returns:
            True if copied successfully, False otherwise
        """
        if not check_language_compatibility:
            value = self.font.kerning[source_pair]
            self.font.kerning[dest_pair] = value
            self._log("kerning_copied", dest_pair, value, "from", source_pair)
            return True
        else:
            if self.check_pair_compatibility_grouped(
                dest_pair
            ) and self.check_pair_compatibility_grouped(source_pair):
                value = self.font.kerning[source_pair]
                self.font.kerning[dest_pair] = value
                self._log("kerning_copied_compatible", dest_pair, value, "from", source_pair)
                return True
            else:
                value = self.font.kerning[source_pair]
                self._log("pair_not_compatible", dest_pair, value)
                return False

    copyKern = copy_kerning  # Alias

    def add_glyphs_to_group(
        self,
        group_name: str,
        glyph_list: list[str],
        check_kerning: bool = True,
        check_language_compatibility: bool = False,
        show_alert: bool = False,
    ) -> tuple[list[str], list[tuple], list[tuple]]:
        """
        Add glyphs to a group.

        If the group doesn't exist, it will be created.
        If a glyph is already in a group of the same class, it will be skipped.
        If check_kerning is True, existing kerning will be handled:
            - Identical kerning: glyph's kerning removed (becomes part of group)
            - Different kerning: kept as exception

        Args:
            group_name: Name of the group
            glyph_list: List of glyph names to add
            check_kerning: Whether to check and handle existing kerning
            check_language_compatibility: Whether to check language compatibility
            show_alert: Unused, kept for compatibility

        Returns:
            Tuple of (skipped_glyphs, new_pairs, deleted_pairs)
        """
        # Remove duplicates while preserving order
        glyphs_to_add = list(dict.fromkeys(glyph_list))

        if self._track_history:
            self._history.append(
                (
                    "add",
                    group_name,
                    glyphs_to_add,
                    check_kerning,
                    check_language_compatibility,
                )
            )

        is_new_group = False
        new_content = []
        skipped = []
        new_pairs = []
        deleted_pairs = []

        # Create group if it doesn't exist
        if group_name not in self.font.groups:
            self.font.groups[group_name] = ()
            is_new_group = True

        side = self._get_side_for_group(group_name)

        for glyph_name in glyphs_to_add:
            if self.is_kerning_group(group_name):
                # Check if glyph is already in a kerning group on this side
                if self._is_glyph_in_group_for_side(glyph_name, side, EDITMODE_KERNING):
                    skipped.append(glyph_name)
                    self._log("glyph_skipped", glyph_name, "already in group on side", side)
                    continue
                if glyph_name in self.font.groups[group_name]:
                    skipped.append(glyph_name)
                    self._log("glyph_skipped", glyph_name, "already in this group")
                    continue

                new_content.append(glyph_name)

                if check_kerning:
                    self._handle_kerning_on_add(
                        glyph_name,
                        group_name,
                        side,
                        is_new_group,
                        new_pairs,
                        deleted_pairs,
                        check_language_compatibility,
                    )
                    is_new_group = False  # After first glyph, treat as existing

            elif self.is_margins_group(group_name):
                if self._is_glyph_in_group_for_side(glyph_name, side, EDITMODE_MARGINS):
                    skipped.append(glyph_name)
                    self._log("glyph_skipped", glyph_name, "already in margins group on side", side)
                    continue
                if glyph_name in self.font.groups[group_name]:
                    skipped.append(glyph_name)
                    self._log("glyph_skipped", glyph_name, "already in this group")
                    continue
                new_content.append(glyph_name)
            else:
                # Non-special group
                new_content.append(glyph_name)

        if new_content:
            self.font.groups[group_name] += tuple(new_content)
            self._build_reverse_mapping()
            self._log("glyphs_added", group_name, new_content)

        # Log operation summary
        self._log("add_glyphs_summary", group_name,
                  "added", len(new_content),
                  "skipped", len(skipped),
                  "new_pairs", len(new_pairs),
                  "deleted_pairs", len(deleted_pairs))

        return (skipped, new_pairs, deleted_pairs)

    addGlyphsToGroup = add_glyphs_to_group  # Alias

    def _handle_kerning_on_add(
        self,
        glyph_name: str,
        group_name: str,
        side: str,
        is_new_group: bool,
        new_pairs: list,
        deleted_pairs: list,
        check_language_compatibility: bool,
    ):
        """Handle kerning when adding a glyph to a group."""
        glyph_pairs = self.get_pairs_by_key(glyph_name, side)

        if is_new_group:
            # New group: move glyph's kerning to group
            for pair, value in glyph_pairs:
                if side == SIDE_LEFT:
                    new_pair = (group_name, pair[1])
                else:
                    new_pair = (pair[0], group_name)

                if self.copy_kerning(pair, new_pair, check_language_compatibility):
                    new_pairs.append(new_pair)
                self._log("kerning_removed", pair, "moved to group")
                self.font.kerning.remove(pair)
                deleted_pairs.append(pair)
        else:
            # Existing group: compare with group's kerning
            group_pairs = self.get_pairs_by_key(group_name, side)
            for pair, value in glyph_pairs:
                for group_pair, group_value in group_pairs:
                    if side == SIDE_LEFT:
                        if pair[1] == group_pair[1]:
                            if value == group_value:
                                self._log("kerning_cleared", pair, value, "equals group", group_pair, group_value)
                                self.font.kerning.remove(pair)
                                deleted_pairs.append(pair)
                            else:
                                self._log("kerning_kept_exception", pair, value, "differs from group", group_pair, group_value)
                    else:
                        if pair[0] == group_pair[0]:
                            if value == group_value:
                                self._log("kerning_cleared", pair, value, "equals group", group_pair, group_value)
                                self.font.kerning.remove(pair)
                                deleted_pairs.append(pair)
                            else:
                                self._log("kerning_kept_exception", pair, value, "differs from group", group_pair, group_value)

    def remove_glyphs_from_group(
        self,
        group_name: str,
        glyph_list: list[str],
        check_kerning: bool = True,
        rebuild_map: bool = True,
        check_language_compatibility: bool = False,
    ) -> tuple[list[tuple], list[tuple]]:
        """
        Remove glyphs from a group.

        If check_kerning is True, group's kerning will be copied to the removed glyphs
        as exceptions.

        Args:
            group_name: Name of the group
            glyph_list: List of glyph names to remove
            check_kerning: Whether to copy group kerning to removed glyphs
            rebuild_map: Whether to rebuild the reverse mapping after removal
            check_language_compatibility: Whether to check language compatibility

        Returns:
            Tuple of (new_pairs, deleted_pairs)
        """
        new_pairs = []
        deleted_pairs = []

        if not glyph_list:
            return (new_pairs, deleted_pairs)

        if self._track_history:
            self._history.append(
                (
                    "remove",
                    group_name,
                    glyph_list,
                    check_kerning,
                    check_language_compatibility,
                )
            )

        if group_name not in self.font.groups:
            self._log("group_not_found", group_name)
            return (new_pairs, deleted_pairs)

        # Build new content without removed glyphs
        new_content = [g for g in self.font.groups[group_name] if g not in glyph_list]

        if check_kerning and self.is_kerning_group(group_name):
            side = self._get_side_for_group(group_name)
            group_pairs = self.get_pairs_by_key(group_name, side)

            for glyph_name in glyph_list:
                for pair, value in group_pairs:
                    # Create exception pair for the removed glyph
                    if side == SIDE_LEFT:
                        exception_pair = (glyph_name, pair[1])
                    else:
                        exception_pair = (pair[0], glyph_name)

                    # Check if glyph already has different kerning
                    if exception_pair in self.font.kerning:
                        if self.font.kerning[exception_pair] != value:
                            self._log("kept_existing_exception", exception_pair)
                            continue

                    if self.copy_kerning(pair, exception_pair, check_language_compatibility):
                        new_pairs.append(exception_pair)

        self.font.groups[group_name] = tuple(new_content)
        self._log("glyphs_removed", group_name, glyph_list)

        if rebuild_map:
            self._build_reverse_mapping()

        # Log operation summary
        self._log("remove_glyphs_summary", group_name,
                  "removed", len(glyph_list),
                  "new_pairs", len(new_pairs),
                  "deleted_pairs", len(deleted_pairs))

        return (new_pairs, deleted_pairs)

    removeGlyphsFromGroup = remove_glyphs_from_group  # Alias

    def delete_group(
        self,
        group_name: str,
        check_kerning: bool = True,
        check_language_compatibility: bool = False,
    ) -> tuple[list[tuple], list[tuple]]:
        """
        Delete a group completely.

        If check_kerning is True, group's kerning will be copied to member glyphs
        as exceptions before deletion.

        Args:
            group_name: Name of the group to delete
            check_kerning: Whether to preserve kerning as exceptions
            check_language_compatibility: Whether to check language compatibility

        Returns:
            Tuple of (new_pairs, deleted_pairs)
        """
        new_pairs = []
        deleted_pairs = []

        if group_name not in self.font.groups:
            self._log("group_not_found", group_name)
            return (new_pairs, deleted_pairs)

        glyph_list = list(self.font.groups[group_name])

        # First remove all glyphs (this copies kerning to them as exceptions)
        new_pairs, _ = self.remove_glyphs_from_group(
            group_name,
            glyph_list,
            check_kerning=check_kerning,
            rebuild_map=False,
            check_language_compatibility=check_language_compatibility,
        )

        # Delete all kerning that references this group
        if self.is_kerning_group(group_name):
            side = self._get_side_for_group(group_name)
            group_pairs = self.get_pairs_by_key(group_name, side)
            for pair, value in group_pairs:
                self._log("kerning_removed", pair, value)
                self.font.kerning.remove(pair)
                deleted_pairs.append(pair)

        # Delete the group
        del self.font.groups[group_name]
        self._log("group_deleted", group_name, "glyphs", len(glyph_list))

        if self._track_history:
            self._history.append(
                ("delete", group_name, [], check_kerning, check_language_compatibility)
            )

        self._build_reverse_mapping()

        # Log operation summary
        self._log("delete_group_summary", group_name,
                  "new_pairs", len(new_pairs),
                  "deleted_pairs", len(deleted_pairs))

        return (new_pairs, deleted_pairs)

    deleteGroup = delete_group  # Alias

    def rename_group(
        self,
        old_name: str,
        new_name: str,
        check_kerning: bool = True,
        check_language_compatibility: bool = False,
    ) -> tuple[list[tuple], list[tuple]]:
        """
        Rename a group.

        If check_kerning is True, kerning will be updated to use the new group name.

        Args:
            old_name: Current group name
            new_name: New group name
            check_kerning: Whether to update kerning references
            check_language_compatibility: Whether to check language compatibility

        Returns:
            Tuple of (new_pairs, deleted_pairs)
        """
        new_pairs = []
        deleted_pairs = []

        if old_name not in self.font.groups:
            self._log("group_not_found", old_name)
            return (new_pairs, deleted_pairs)
        if new_name in self.font.groups:
            self._log("group_already_exists", new_name, "cannot rename")
            return (new_pairs, deleted_pairs)  # Can't rename to existing group

        if self._track_history:
            self._history.append(
                (
                    "rename",
                    old_name,
                    new_name,
                    check_kerning,
                    check_language_compatibility,
                )
            )

        # Copy content to new group
        content = list(self.font.groups[old_name])
        self.font.groups[new_name] = tuple(content)

        # Update kerning references
        if self.is_kerning_group(old_name) and check_kerning:
            side = self._get_side_for_group(old_name)
            old_pairs = self.get_pairs_by_key(old_name, side)

            for pair, value in old_pairs:
                if side == SIDE_LEFT:
                    new_pair = (new_name, pair[1])
                else:
                    new_pair = (pair[0], new_name)

                if self.copy_kerning(pair, new_pair, check_language_compatibility):
                    new_pairs.append(new_pair)
                self._log("kerning_removed", pair, "replaced by", new_pair)
                self.font.kerning.remove(pair)
                deleted_pairs.append(pair)

        # Remove old group
        self.font.groups.remove(old_name)
        self._log("group_renamed", old_name, "to", new_name)

        self._build_reverse_mapping()

        # Log operation summary
        self._log("rename_group_summary", old_name, "->", new_name,
                  "new_pairs", len(new_pairs),
                  "deleted_pairs", len(deleted_pairs))

        return (new_pairs, deleted_pairs)

    renameGroup = rename_group  # Alias

    def reposition_glyph_in_group(
        self,
        group_name: str,
        target_index: int = 0,
        glyph_list: list[str] | None = None,
    ):
        """
        Reposition glyphs within a group.

        Moves the specified glyphs to the target position in the group.

        Args:
            group_name: Name of the group
            target_index: Index position to insert glyphs at
            glyph_list: List of glyph names to reposition
        """
        if group_name not in self.font.groups:
            return
        if glyph_list is None:
            return
        if target_index > len(self.font.groups[group_name]):
            return

        try:
            temp_list = list(self.font.groups[group_name])
            target_glyph = temp_list[target_index]

            # Remove glyphs to reposition
            for name in glyph_list:
                temp_list.remove(name)

            # Find new position of target glyph
            new_index = 0
            for i, name in enumerate(temp_list):
                if name == target_glyph:
                    new_index = i
                    break

            # Insert glyphs at new position
            for name in glyph_list:
                temp_list.insert(new_index, name)
                new_index += 1

            self.font.groups[group_name] = tuple(temp_list)
        except (ValueError, IndexError):
            pass

    repositionGlyphsInGroup = reposition_glyph_in_group  # Alias

    def insert_temp_glyph_in_mapping(
        self, glyph_names: tuple[str, str]
    ) -> tuple[str, str]:
        """
        Temporarily insert glyph names into mapping for display purposes.

        Used when displaying glyphs with unique suffixes that need to inherit
        their base glyph's group membership temporarily.

        Args:
            glyph_names: Tuple of (left_glyph, right_glyph) names

        Returns:
            Tuple of resolved names (may be group names if base glyphs are in groups)
        """
        left, right = glyph_names
        left_base = cut_unique_suffix(left)
        right_base = cut_unique_suffix(right)

        if left_base in self._left_kern_groups:
            self._left_kern_groups[left] = self._left_kern_groups[left_base]
            left = self._left_kern_groups[left]

        if right_base in self._right_kern_groups:
            self._right_kern_groups[right] = self._right_kern_groups[right_base]
            right = self._right_kern_groups[right]

        return left, right

    insertTempGlyphInGroup = insert_temp_glyph_in_mapping  # Alias


# Backward compatibility aliases
TDHashGroupsDic = FontGroupsManager
KerningGroupsIndex = FontGroupsManager


# =============================================================================
# Refactored researchPair function
# =============================================================================


def resolve_kern_pair(
    font, groups_index: FontGroupsManager, glyph_pair: tuple[str, str]
) -> KernPairInfo:
    """
    Research a kerning pair and return structured information.

    This is the refactored version of researchPair() that returns
    a KernPairInfo dataclass instead of a dictionary.

    Args:
        font: The font object with kerning data
        groups_index: FontGroupsManager instance with group information
        glyph_pair: Tuple of (left_glyph, right_glyph) names

    Returns:
        KernPairInfo dataclass with all pair information
    """
    tl, tr = glyph_pair
    left_name = cut_unique_suffix(tl)
    right_name = cut_unique_suffix(tr)

    kerning = font.kerning

    # Get group names (or glyph names if not in group)
    left_group = groups_index.get_group_for_glyph(left_name, SIDE_LEFT)
    right_group = groups_index.get_group_for_glyph(right_name, SIDE_RIGHT)

    left_in_group = groups_index.is_kerning_group(left_group)
    right_in_group = groups_index.is_kerning_group(right_group)

    # Case 1: Direct glyph-glyph pair exists
    if (left_name, right_name) in kerning and kerning[
        (left_name, right_name)
    ] is not None:
        is_exception = left_in_group or right_in_group
        return KernPairInfo(
            left=left_name,
            right=right_name,
            value=kerning[(left_name, right_name)],
            is_exception=is_exception,
            left_group=left_group,
            right_group=right_group,
        )

    # Case 2: Group-glyph pair exists
    if (left_group, right_name) in kerning and kerning[
        (left_group, right_name)
    ] is not None:
        return KernPairInfo(
            left=left_group,
            right=right_name,
            value=kerning[(left_group, right_name)],
            is_exception=right_in_group,
            left_group=left_group,
            right_group=right_group,
        )

    # Case 3: Glyph-group pair exists
    if (left_name, right_group) in kerning and kerning[
        (left_name, right_group)
    ] is not None:
        return KernPairInfo(
            left=left_name,
            right=right_group,
            value=kerning[(left_name, right_group)],
            is_exception=left_in_group,
            left_group=left_group,
            right_group=right_group,
        )

    # Case 4: Group-group pair exists
    if (left_group, right_group) in kerning and kerning[
        (left_group, right_group)
    ] is not None:
        return KernPairInfo(
            left=left_group,
            right=right_group,
            value=kerning[(left_group, right_group)],
            is_exception=False,
            left_group=left_group,
            right_group=right_group,
        )

    # Case 5: No kerning found
    return KernPairInfo(
        left=left_group,
        right=right_group,
        value=None,
        is_exception=False,
        left_group=left_group,
        right_group=right_group,
    )


# Aliases for backward compatibility
researchPair = resolve_kern_pair
research_pair = resolve_kern_pair


# =============================================================================
# Usage Examples and Migration Guide
# =============================================================================


def get_kern_pair_notes_v2(
    font, groups_index: FontGroupsManager, pair: tuple[str, str]
):
    """
    Example of refactored getKernPairNotes using KernPairInfo.

    Demonstrates how the new dataclass simplifies exception handling.
    """
    tl, tr = pair

    # Early checks for empty groups
    for side, name in [(SIDE_LEFT, tl), (SIDE_RIGHT, tr)]:
        if groups_index.is_kerning_group(name):
            group = groups_index.get_group_for_glyph(name, side)
            if len(font.groups.get(group, [])) == 0:
                return (PAIR_INFO_EMPTY, tl, tr)

    # Check if pair was deleted
    if (tl, tr) not in font.kerning:
        parent_l = groups_index.get_group_for_glyph(tl, SIDE_LEFT)
        parent_r = groups_index.get_group_for_glyph(tr, SIDE_RIGHT)
        return (PAIR_INFO_EXCEPTION_DELETED, parent_l, parent_r)

    # Get key glyphs
    left_key = groups_index.get_key_glyph(tl)
    right_key = groups_index.get_key_glyph(tr)

    # Check for exceptions within groups
    if groups_index.is_kerning_group(tl):
        for nl in font.groups[tl]:
            if (nl, tr) in font.kerning:
                return (PAIR_INFO_ATTENTION, nl, tr)

    if groups_index.is_kerning_group(tr):
        for nr in font.groups[tr]:
            if (tl, nr) in font.kerning:
                return (PAIR_INFO_ATTENTION, tl, nr)

    # Resolve the pair - now returns KernPairInfo!
    pair_info = resolve_kern_pair(font, groups_index, (left_key, right_key))

    # Simplified exception handling using exception_side property
    if pair_info.is_exception:
        match pair_info.exception_side:
            case ExceptionSide.DIRECT_KEY:
                # Input was already kerning keys (group names), not glyph names
                return (
                    PAIR_INFO_ATTENTION,
                    pair_info.left_group,
                    pair_info.right_group,
                )
            case ExceptionSide.BOTH:
                return (PAIR_INFO_ORPHAN, pair_info.left_group, pair_info.right_group)
            case ExceptionSide.LEFT | ExceptionSide.RIGHT:
                return (
                    PAIR_INFO_EXCEPTION,
                    pair_info.left_group,
                    pair_info.right_group,
                )

    # Check for deep exceptions
    if groups_index.is_kerning_group(tl) and groups_index.is_kerning_group(tr):
        for nl in font.groups[tl]:
            for nr in font.groups[tr]:
                if (nl, nr) in font.kerning:
                    return (PAIR_INFO_ATTENTION, tl, nr)

    return (PAIR_INFO_NONE, tl, tr)


# =============================================================================
# Migration Guide (see docstrings in classes above for field mappings)
# =============================================================================

# Field mapping from old dict to new KernPairInfo:
#   pair['L_realName']    -> pair.left
#   pair['R_realName']    -> pair.right
#   pair['kernValue']     -> pair.value
#   pair['exception']     -> pair.is_exception
#   pair['L_nameForKern'] -> pair.left_group
#   pair['R_nameForKern'] -> pair.right_group
#
# Exception type checks:
#   if L == L_group and R == R_group  -> pair.exception_side == ExceptionSide.DIRECT_KEY
#   if L != L_group and R != R_group  -> pair.exception_side == ExceptionSide.BOTH
#   if L != L_group xor R != R_group  -> pair.exception_side in (LEFT, RIGHT)
#
# Note: GLYPH_PAIR is deprecated, use DIRECT_KEY instead (GLYPH_PAIR is kept as alias)
#
# Shortcut properties:
#   pair.is_left_exception  - True if only left side differs
#   pair.is_right_exception - True if only right side differs
#   pair.is_orphan          - True if both sides differ
#   pair.has_value          - True if kerning value exists
#
# Removed unused fields:
#   L_inGroup, R_inGroup, L_markException, R_markException
