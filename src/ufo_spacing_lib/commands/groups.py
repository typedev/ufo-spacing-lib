"""
Group Commands.

This module contains all commands for kerning group operations.

Commands:
    - AddGlyphsToGroupCommand: Add glyphs to a kerning group
    - RemoveGlyphsFromGroupCommand: Remove glyphs from a kerning group
    - DeleteGroupCommand: Delete a kerning group entirely
    - RenameGroupCommand: Rename a kerning group

All commands support:
    - Full undo/redo capability
    - Automatic kerning handling (exceptions, inheritance)
    - Integration with FontGroupsManager

Example:
    Adding glyphs to a group:

    >>> from ufo_spacing_lib import SpacingEditor, FontContext
    >>> from ufo_spacing_lib import AddGlyphsToGroupCommand
    >>>
    >>> editor = SpacingEditor()
    >>> context = FontContext.from_single_font(font)
    >>>
    >>> cmd = AddGlyphsToGroupCommand(
    ...     group_name='public.kern1.A',
    ...     glyphs=['Aacute', 'Agrave'],
    ...     groups_manager=manager,
    ...     check_kerning=True
    ... )
    >>> editor.execute(cmd, context)
    >>>
    >>> # Undo the change
    >>> editor.undo()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..contexts import FontContext
from .base import Command, CommandResult

if TYPE_CHECKING:
    from ..groups_core import FontGroupsManager


@dataclass
class AddGlyphsToGroupCommand(Command):
    """
    Command to add glyphs to a kerning group.

    If the group doesn't exist, it will be created.
    If a glyph is already in a group of the same class (same side),
    it will be skipped.

    When check_kerning is True, existing kerning is handled:
    - For new groups: glyph's kerning is promoted to group kerning
    - For existing groups: matching kerning is removed, different
      values are kept as exceptions

    Attributes:
        group_name: Full group name (e.g., 'public.kern1.A')
        glyphs: List of glyph names to add
        groups_manager: FontGroupsManager instance for the font
        check_kerning: Whether to handle kerning automatically

    Example:
        >>> cmd = AddGlyphsToGroupCommand(
        ...     group_name='public.kern1.A',
        ...     glyphs=['Aacute', 'Agrave'],
        ...     groups_manager=manager,
        ...     check_kerning=True
        ... )
        >>> result = editor.execute(cmd, context)
    """

    group_name: str
    glyphs: list[str]
    groups_manager: "FontGroupsManager"
    check_kerning: bool = True

    # Undo state
    _group_existed: bool = field(default=False, repr=False, compare=False)
    _prev_members: list[str] = field(default_factory=list, repr=False, compare=False)
    _deleted_pairs: dict[tuple[str, str], int] = field(
        default_factory=dict, repr=False, compare=False
    )
    _created_pairs: list[tuple[str, str]] = field(
        default_factory=list, repr=False, compare=False
    )
    _actually_added: list[str] = field(
        default_factory=list, repr=False, compare=False
    )

    @property
    def description(self) -> str:
        """Human-readable description of the command."""
        count = len(self.glyphs)
        short_name = self.group_name.split(".")[-1]
        return f"Add {count} glyph(s) to group {short_name}"

    def execute(self, context: FontContext) -> CommandResult:
        """
        Add glyphs to the group.

        Args:
            context: FontContext with fonts to modify.

        Returns:
            CommandResult with success status.
            result.data contains (skipped, new_pairs, deleted_pairs).
        """
        font = context.fonts[0]
        manager = self.groups_manager

        # Save state for undo
        self._group_existed = self.group_name in font.groups
        self._prev_members = list(font.groups.get(self.group_name, []))
        self._deleted_pairs.clear()
        self._created_pairs.clear()

        # Save kerning that will be deleted (with values!)
        if self.check_kerning:
            side = manager._get_side_for_group(self.group_name)
            for glyph in self.glyphs:
                pairs = manager.get_pairs_by_key(glyph, side)
                for pair, value in pairs:
                    self._deleted_pairs[pair] = value

        # Pause manager's internal history (we handle undo ourselves)
        manager.pause_history()

        try:
            # Execute the operation
            skipped, new_pairs, deleted_pairs = manager.add_glyphs_to_group(
                self.group_name,
                self.glyphs,
                check_kerning=self.check_kerning,
            )

            # Track what was actually added
            skipped_set = set(skipped)
            self._actually_added = [g for g in self.glyphs if g not in skipped_set]

            # Track created pairs
            self._created_pairs = list(new_pairs)

            # Update deleted pairs with actual deletions
            # (manager may have deleted different pairs than we predicted)
            for pair in deleted_pairs:
                if pair not in self._deleted_pairs:
                    # Get value from font if still there, otherwise it was already saved
                    if pair in font.kerning:
                        self._deleted_pairs[pair] = font.kerning[pair]

        finally:
            manager.resume_history()

        return CommandResult.ok(
            f"Added {len(self._actually_added)} glyph(s) to {self.group_name}",
            data=(skipped, new_pairs, deleted_pairs),
        )

    def undo(self, context: FontContext) -> CommandResult:
        """
        Undo the add operation.

        Restores the group to its previous state and restores
        any kerning that was deleted.

        Args:
            context: FontContext (same as used in execute).

        Returns:
            CommandResult indicating success.
        """
        font = context.fonts[0]
        manager = self.groups_manager

        # Remove created kerning pairs
        for pair in self._created_pairs:
            if pair in font.kerning:
                del font.kerning[pair]

        # Restore deleted kerning pairs
        for pair, value in self._deleted_pairs.items():
            font.kerning[pair] = value

        # Restore group state
        if self._group_existed:
            font.groups[self.group_name] = tuple(self._prev_members)
        else:
            # Group didn't exist before - delete it
            if self.group_name in font.groups:
                del font.groups[self.group_name]

        # Rebuild manager's reverse mapping
        manager._build_reverse_mapping()

        return CommandResult.ok(f"Undid: {self.description}")


@dataclass
class RemoveGlyphsFromGroupCommand(Command):
    """
    Command to remove glyphs from a kerning group.

    When check_kerning is True, group's kerning will be copied
    to the removed glyphs as exception pairs.

    Attributes:
        group_name: Full group name (e.g., 'public.kern1.A')
        glyphs: List of glyph names to remove
        groups_manager: FontGroupsManager instance for the font
        check_kerning: Whether to create exception pairs

    Example:
        >>> cmd = RemoveGlyphsFromGroupCommand(
        ...     group_name='public.kern1.A',
        ...     glyphs=['Aacute'],
        ...     groups_manager=manager,
        ...     check_kerning=True
        ... )
        >>> result = editor.execute(cmd, context)
    """

    group_name: str
    glyphs: list[str]
    groups_manager: "FontGroupsManager"
    check_kerning: bool = True

    # Undo state
    _prev_members: list[str] = field(default_factory=list, repr=False, compare=False)
    _created_pairs: dict[tuple[str, str], int] = field(
        default_factory=dict, repr=False, compare=False
    )

    @property
    def description(self) -> str:
        """Human-readable description of the command."""
        count = len(self.glyphs)
        short_name = self.group_name.split(".")[-1]
        return f"Remove {count} glyph(s) from group {short_name}"

    def execute(self, context: FontContext) -> CommandResult:
        """
        Remove glyphs from the group.

        Args:
            context: FontContext with fonts to modify.

        Returns:
            CommandResult with success status.
            result.data contains (new_pairs, deleted_pairs).
        """
        font = context.fonts[0]
        manager = self.groups_manager

        # Save state for undo
        self._prev_members = list(font.groups.get(self.group_name, []))
        self._created_pairs.clear()

        # Pause manager's internal history
        manager.pause_history()

        try:
            # Execute the operation
            new_pairs, deleted_pairs = manager.remove_glyphs_from_group(
                self.group_name,
                self.glyphs,
                check_kerning=self.check_kerning,
            )

            # Track created pairs with their values
            for pair in new_pairs:
                if pair in font.kerning:
                    self._created_pairs[pair] = font.kerning[pair]

        finally:
            manager.resume_history()

        return CommandResult.ok(
            f"Removed {len(self.glyphs)} glyph(s) from {self.group_name}",
            data=(new_pairs, deleted_pairs),
        )

    def undo(self, context: FontContext) -> CommandResult:
        """
        Undo the remove operation.

        Restores the group to its previous state and removes
        any exception pairs that were created.

        Args:
            context: FontContext (same as used in execute).

        Returns:
            CommandResult indicating success.
        """
        font = context.fonts[0]
        manager = self.groups_manager

        # Remove created exception pairs
        for pair in self._created_pairs:
            if pair in font.kerning:
                del font.kerning[pair]

        # Restore group members
        font.groups[self.group_name] = tuple(self._prev_members)

        # Rebuild manager's reverse mapping
        manager._build_reverse_mapping()

        return CommandResult.ok(f"Undid: {self.description}")


@dataclass
class DeleteGroupCommand(Command):
    """
    Command to delete a kerning group entirely.

    When check_kerning is True, group's kerning will be copied
    to member glyphs as exception pairs before deletion, and
    all group kerning pairs will be removed.

    Attributes:
        group_name: Full group name to delete (e.g., 'public.kern1.A')
        groups_manager: FontGroupsManager instance for the font
        check_kerning: Whether to preserve kerning as exceptions

    Example:
        >>> cmd = DeleteGroupCommand(
        ...     group_name='public.kern1.A',
        ...     groups_manager=manager,
        ...     check_kerning=True
        ... )
        >>> result = editor.execute(cmd, context)
    """

    group_name: str
    groups_manager: "FontGroupsManager"
    check_kerning: bool = True

    # Undo state
    _prev_members: list[str] = field(default_factory=list, repr=False, compare=False)
    _deleted_group_pairs: dict[tuple[str, str], int] = field(
        default_factory=dict, repr=False, compare=False
    )
    _created_pairs: dict[tuple[str, str], int] = field(
        default_factory=dict, repr=False, compare=False
    )

    @property
    def description(self) -> str:
        """Human-readable description of the command."""
        short_name = self.group_name.split(".")[-1]
        return f"Delete group {short_name}"

    def execute(self, context: FontContext) -> CommandResult:
        """
        Delete the group.

        Args:
            context: FontContext with fonts to modify.

        Returns:
            CommandResult with success status.
            result.data contains (new_pairs, deleted_pairs).
        """
        font = context.fonts[0]
        manager = self.groups_manager

        if self.group_name not in font.groups:
            return CommandResult.error(f"Group {self.group_name} not found")

        # Save state for undo
        self._prev_members = list(font.groups[self.group_name])
        self._deleted_group_pairs.clear()
        self._created_pairs.clear()

        # Save group's kerning pairs before deletion
        side = manager._get_side_for_group(self.group_name)
        group_pairs = manager.get_pairs_by_key(self.group_name, side)
        for pair, value in group_pairs:
            self._deleted_group_pairs[pair] = value

        # Pause manager's internal history
        manager.pause_history()

        try:
            # Execute the operation
            new_pairs, deleted_pairs = manager.delete_group(
                self.group_name,
                check_kerning=self.check_kerning,
            )

            # Track created exception pairs with their values
            for pair in new_pairs:
                if pair in font.kerning:
                    self._created_pairs[pair] = font.kerning[pair]

        finally:
            manager.resume_history()

        return CommandResult.ok(
            f"Deleted group {self.group_name}",
            data=(new_pairs, deleted_pairs),
        )

    def undo(self, context: FontContext) -> CommandResult:
        """
        Undo the delete operation.

        Restores the group and its kerning pairs, removes
        exception pairs that were created.

        Args:
            context: FontContext (same as used in execute).

        Returns:
            CommandResult indicating success.
        """
        font = context.fonts[0]
        manager = self.groups_manager

        # Remove created exception pairs
        for pair in self._created_pairs:
            if pair in font.kerning:
                del font.kerning[pair]

        # Restore group
        font.groups[self.group_name] = tuple(self._prev_members)

        # Restore group's kerning pairs
        for pair, value in self._deleted_group_pairs.items():
            font.kerning[pair] = value

        # Rebuild manager's reverse mapping
        manager._build_reverse_mapping()

        return CommandResult.ok(f"Undid: {self.description}")


@dataclass
class RenameGroupCommand(Command):
    """
    Command to rename a kerning group.

    When check_kerning is True, all kerning pairs that reference
    the group will be updated to use the new name.

    Attributes:
        old_name: Current full group name
        new_name: New full group name
        groups_manager: FontGroupsManager instance for the font
        check_kerning: Whether to update kerning references

    Example:
        >>> cmd = RenameGroupCommand(
        ...     old_name='public.kern1.A',
        ...     new_name='public.kern1.A.cap',
        ...     groups_manager=manager,
        ...     check_kerning=True
        ... )
        >>> result = editor.execute(cmd, context)
    """

    old_name: str
    new_name: str
    groups_manager: "FontGroupsManager"
    check_kerning: bool = True

    # Undo state
    _renamed_pairs: dict[tuple[str, str], tuple[str, str]] = field(
        default_factory=dict, repr=False, compare=False
    )
    _pair_values: dict[tuple[str, str], int] = field(
        default_factory=dict, repr=False, compare=False
    )

    @property
    def description(self) -> str:
        """Human-readable description of the command."""
        old_short = self.old_name.split(".")[-1]
        new_short = self.new_name.split(".")[-1]
        return f"Rename group {old_short} to {new_short}"

    def execute(self, context: FontContext) -> CommandResult:
        """
        Rename the group.

        Args:
            context: FontContext with fonts to modify.

        Returns:
            CommandResult with success status.
            result.data contains (new_pairs, deleted_pairs).
        """
        font = context.fonts[0]
        manager = self.groups_manager

        if self.old_name not in font.groups:
            return CommandResult.error(f"Group {self.old_name} not found")

        if self.new_name in font.groups:
            return CommandResult.error(f"Group {self.new_name} already exists")

        # Clear undo state
        self._renamed_pairs.clear()
        self._pair_values.clear()

        # Track kerning pairs that will be renamed
        if self.check_kerning:
            side = manager._get_side_for_group(self.old_name)
            old_pairs = manager.get_pairs_by_key(self.old_name, side)
            for old_pair, value in old_pairs:
                if side == "L":
                    new_pair = (self.new_name, old_pair[1])
                else:
                    new_pair = (old_pair[0], self.new_name)
                self._renamed_pairs[old_pair] = new_pair
                self._pair_values[old_pair] = value

        # Pause manager's internal history
        manager.pause_history()

        try:
            # Execute the operation
            new_pairs, deleted_pairs = manager.rename_group(
                self.old_name,
                self.new_name,
                check_kerning=self.check_kerning,
            )

        finally:
            manager.resume_history()

        return CommandResult.ok(
            f"Renamed {self.old_name} to {self.new_name}",
            data=(new_pairs, deleted_pairs),
        )

    def undo(self, context: FontContext) -> CommandResult:
        """
        Undo the rename operation.

        Restores the original group name and kerning references.

        Args:
            context: FontContext (same as used in execute).

        Returns:
            CommandResult indicating success.
        """
        font = context.fonts[0]
        manager = self.groups_manager

        # Get current group content
        members = list(font.groups.get(self.new_name, []))

        # Delete new name
        if self.new_name in font.groups:
            del font.groups[self.new_name]

        # Restore old name
        font.groups[self.old_name] = tuple(members)

        # Restore kerning pairs with old names
        for old_pair, new_pair in self._renamed_pairs.items():
            # Remove new pair
            if new_pair in font.kerning:
                del font.kerning[new_pair]
            # Restore old pair
            if old_pair in self._pair_values:
                font.kerning[old_pair] = self._pair_values[old_pair]

        # Rebuild manager's reverse mapping
        manager._build_reverse_mapping()

        return CommandResult.ok(f"Undid: {self.description}")
