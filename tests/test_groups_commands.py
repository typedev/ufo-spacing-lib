"""
Tests for Group Commands.

This module tests all group command classes:
- AddGlyphsToGroupCommand
- RemoveGlyphsFromGroupCommand
- DeleteGroupCommand
- RenameGroupCommand

Also tests integration with SpacingEditor for unified undo/redo.
"""

import unittest

from ufo_spacing_lib import (
    FontContext,
    FontGroupsManager,
    SpacingEditor,
)
from ufo_spacing_lib.commands.groups import (
    AddGlyphsToGroupCommand,
    DeleteGroupCommand,
    RemoveGlyphsFromGroupCommand,
    RenameGroupCommand,
)
from ufo_spacing_lib.commands.kerning import AdjustKerningCommand
from .mocks import create_test_font


class TestAddGlyphsToGroupCommand(unittest.TestCase):
    """Tests for AddGlyphsToGroupCommand."""

    def setUp(self):
        self.font = create_test_font()
        self.context = FontContext.from_single_font(self.font)
        self.manager = FontGroupsManager(self.font)

    def test_add_to_new_group(self):
        """Adding glyphs creates a new group."""
        cmd = AddGlyphsToGroupCommand(
            group_name='public.kern1.A',
            glyphs=['A', 'Aacute'],
            groups_manager=self.manager,
            check_kerning=False,
        )
        result = cmd.execute(self.context)

        self.assertTrue(result.success)
        self.assertIn('public.kern1.A', self.font.groups)
        self.assertEqual(list(self.font.groups['public.kern1.A']), ['A', 'Aacute'])

    def test_add_to_existing_group(self):
        """Adding glyphs to an existing group appends them."""
        self.font.groups['public.kern1.A'] = ('A',)
        self.manager._build_reverse_mapping()

        cmd = AddGlyphsToGroupCommand(
            group_name='public.kern1.A',
            glyphs=['Aacute', 'Agrave'],
            groups_manager=self.manager,
            check_kerning=False,
        )
        result = cmd.execute(self.context)

        self.assertTrue(result.success)
        self.assertEqual(
            list(self.font.groups['public.kern1.A']),
            ['A', 'Aacute', 'Agrave']
        )

    def test_add_with_kerning_promotes_to_group(self):
        """When creating new group, glyph's kerning is promoted to group."""
        self.font.kerning[('A', 'V')] = -50
        self.font.kerning[('A', 'T')] = -30

        cmd = AddGlyphsToGroupCommand(
            group_name='public.kern1.A',
            glyphs=['A'],
            groups_manager=self.manager,
            check_kerning=True,
        )
        cmd.execute(self.context)

        # Original pairs should be deleted
        self.assertNotIn(('A', 'V'), self.font.kerning)
        self.assertNotIn(('A', 'T'), self.font.kerning)
        # Group pairs should be created
        self.assertEqual(self.font.kerning[('public.kern1.A', 'V')], -50)
        self.assertEqual(self.font.kerning[('public.kern1.A', 'T')], -30)

    def test_undo_removes_group(self):
        """Undo should remove a newly created group."""
        cmd = AddGlyphsToGroupCommand(
            group_name='public.kern1.A',
            glyphs=['A', 'Aacute'],
            groups_manager=self.manager,
            check_kerning=False,
        )
        cmd.execute(self.context)
        cmd.undo(self.context)

        self.assertNotIn('public.kern1.A', self.font.groups)

    def test_undo_restores_kerning(self):
        """Undo should restore deleted kerning pairs."""
        self.font.kerning[('A', 'V')] = -50

        cmd = AddGlyphsToGroupCommand(
            group_name='public.kern1.A',
            glyphs=['A'],
            groups_manager=self.manager,
            check_kerning=True,
        )
        cmd.execute(self.context)
        cmd.undo(self.context)

        # Original pair should be restored
        self.assertEqual(self.font.kerning[('A', 'V')], -50)
        # Group pair should be removed
        self.assertNotIn(('public.kern1.A', 'V'), self.font.kerning)

    def test_undo_restores_previous_members(self):
        """Undo restores group to previous state."""
        self.font.groups['public.kern1.A'] = ('A',)
        self.manager._build_reverse_mapping()

        cmd = AddGlyphsToGroupCommand(
            group_name='public.kern1.A',
            glyphs=['Aacute'],
            groups_manager=self.manager,
            check_kerning=False,
        )
        cmd.execute(self.context)
        cmd.undo(self.context)

        self.assertEqual(list(self.font.groups['public.kern1.A']), ['A'])


class TestRemoveGlyphsFromGroupCommand(unittest.TestCase):
    """Tests for RemoveGlyphsFromGroupCommand."""

    def setUp(self):
        self.font = create_test_font()
        self.context = FontContext.from_single_font(self.font)
        # Set up group with kerning
        self.font.groups['public.kern1.A'] = ('A', 'Aacute', 'Agrave')
        self.font.kerning[('public.kern1.A', 'V')] = -50
        self.manager = FontGroupsManager(self.font)

    def test_remove_glyph(self):
        """Removing a glyph removes it from the group."""
        cmd = RemoveGlyphsFromGroupCommand(
            group_name='public.kern1.A',
            glyphs=['Aacute'],
            groups_manager=self.manager,
            check_kerning=False,
        )
        result = cmd.execute(self.context)

        self.assertTrue(result.success)
        self.assertEqual(
            list(self.font.groups['public.kern1.A']),
            ['A', 'Agrave']
        )

    def test_remove_creates_exception_pairs(self):
        """Removing with check_kerning creates exception pairs."""
        cmd = RemoveGlyphsFromGroupCommand(
            group_name='public.kern1.A',
            glyphs=['Aacute'],
            groups_manager=self.manager,
            check_kerning=True,
        )
        cmd.execute(self.context)

        # Exception pair should be created
        self.assertEqual(self.font.kerning[('Aacute', 'V')], -50)

    def test_undo_restores_members(self):
        """Undo restores removed glyphs."""
        cmd = RemoveGlyphsFromGroupCommand(
            group_name='public.kern1.A',
            glyphs=['Aacute'],
            groups_manager=self.manager,
            check_kerning=False,
        )
        cmd.execute(self.context)
        cmd.undo(self.context)

        self.assertEqual(
            list(self.font.groups['public.kern1.A']),
            ['A', 'Aacute', 'Agrave']
        )

    def test_undo_removes_exception_pairs(self):
        """Undo removes exception pairs that were created."""
        cmd = RemoveGlyphsFromGroupCommand(
            group_name='public.kern1.A',
            glyphs=['Aacute'],
            groups_manager=self.manager,
            check_kerning=True,
        )
        cmd.execute(self.context)
        cmd.undo(self.context)

        # Exception pair should be removed
        self.assertNotIn(('Aacute', 'V'), self.font.kerning)


class TestDeleteGroupCommand(unittest.TestCase):
    """Tests for DeleteGroupCommand."""

    def setUp(self):
        self.font = create_test_font()
        self.context = FontContext.from_single_font(self.font)
        # Set up group with kerning
        self.font.groups['public.kern1.A'] = ('A', 'Aacute')
        self.font.kerning[('public.kern1.A', 'V')] = -50
        self.font.kerning[('public.kern1.A', 'T')] = -30
        self.manager = FontGroupsManager(self.font)

    def test_delete_group(self):
        """Deleting a group removes it."""
        cmd = DeleteGroupCommand(
            group_name='public.kern1.A',
            groups_manager=self.manager,
            check_kerning=False,
        )
        result = cmd.execute(self.context)

        self.assertTrue(result.success)
        self.assertNotIn('public.kern1.A', self.font.groups)

    def test_delete_removes_group_kerning(self):
        """Deleting removes group kerning pairs."""
        cmd = DeleteGroupCommand(
            group_name='public.kern1.A',
            groups_manager=self.manager,
            check_kerning=True,
        )
        cmd.execute(self.context)

        # Group kerning should be removed
        self.assertNotIn(('public.kern1.A', 'V'), self.font.kerning)
        self.assertNotIn(('public.kern1.A', 'T'), self.font.kerning)

    def test_delete_creates_exception_pairs(self):
        """Deleting with check_kerning creates exception pairs for members."""
        cmd = DeleteGroupCommand(
            group_name='public.kern1.A',
            groups_manager=self.manager,
            check_kerning=True,
        )
        cmd.execute(self.context)

        # Exception pairs should be created for members
        self.assertEqual(self.font.kerning[('A', 'V')], -50)
        self.assertEqual(self.font.kerning[('Aacute', 'V')], -50)

    def test_delete_nonexistent_fails(self):
        """Deleting non-existent group returns error."""
        cmd = DeleteGroupCommand(
            group_name='public.kern1.NONEXISTENT',
            groups_manager=self.manager,
            check_kerning=False,
        )
        result = cmd.execute(self.context)

        self.assertFalse(result.success)

    def test_undo_restores_group(self):
        """Undo restores the deleted group."""
        cmd = DeleteGroupCommand(
            group_name='public.kern1.A',
            groups_manager=self.manager,
            check_kerning=False,
        )
        cmd.execute(self.context)
        cmd.undo(self.context)

        self.assertIn('public.kern1.A', self.font.groups)
        self.assertEqual(
            list(self.font.groups['public.kern1.A']),
            ['A', 'Aacute']
        )

    def test_undo_restores_group_kerning(self):
        """Undo restores group kerning pairs."""
        cmd = DeleteGroupCommand(
            group_name='public.kern1.A',
            groups_manager=self.manager,
            check_kerning=True,
        )
        cmd.execute(self.context)
        cmd.undo(self.context)

        # Group kerning should be restored
        self.assertEqual(self.font.kerning[('public.kern1.A', 'V')], -50)
        self.assertEqual(self.font.kerning[('public.kern1.A', 'T')], -30)
        # Exception pairs should be removed
        self.assertNotIn(('A', 'V'), self.font.kerning)
        self.assertNotIn(('Aacute', 'V'), self.font.kerning)


class TestRenameGroupCommand(unittest.TestCase):
    """Tests for RenameGroupCommand."""

    def setUp(self):
        self.font = create_test_font()
        self.context = FontContext.from_single_font(self.font)
        # Set up group with kerning
        self.font.groups['public.kern1.A'] = ('A', 'Aacute')
        self.font.kerning[('public.kern1.A', 'V')] = -50
        self.manager = FontGroupsManager(self.font)

    def test_rename_group(self):
        """Renaming changes the group name."""
        cmd = RenameGroupCommand(
            old_name='public.kern1.A',
            new_name='public.kern1.A.cap',
            groups_manager=self.manager,
            check_kerning=False,
        )
        result = cmd.execute(self.context)

        self.assertTrue(result.success)
        self.assertNotIn('public.kern1.A', self.font.groups)
        self.assertIn('public.kern1.A.cap', self.font.groups)
        self.assertEqual(
            list(self.font.groups['public.kern1.A.cap']),
            ['A', 'Aacute']
        )

    def test_rename_updates_kerning(self):
        """Renaming with check_kerning updates kerning references."""
        cmd = RenameGroupCommand(
            old_name='public.kern1.A',
            new_name='public.kern1.A.cap',
            groups_manager=self.manager,
            check_kerning=True,
        )
        cmd.execute(self.context)

        # Old kerning should be removed
        self.assertNotIn(('public.kern1.A', 'V'), self.font.kerning)
        # New kerning should exist
        self.assertEqual(self.font.kerning[('public.kern1.A.cap', 'V')], -50)

    def test_rename_to_existing_fails(self):
        """Renaming to an existing group name fails."""
        self.font.groups['public.kern1.B'] = ('B',)
        self.manager._build_reverse_mapping()

        cmd = RenameGroupCommand(
            old_name='public.kern1.A',
            new_name='public.kern1.B',
            groups_manager=self.manager,
            check_kerning=False,
        )
        result = cmd.execute(self.context)

        self.assertFalse(result.success)

    def test_rename_nonexistent_fails(self):
        """Renaming non-existent group fails."""
        cmd = RenameGroupCommand(
            old_name='public.kern1.NONEXISTENT',
            new_name='public.kern1.NEW',
            groups_manager=self.manager,
            check_kerning=False,
        )
        result = cmd.execute(self.context)

        self.assertFalse(result.success)

    def test_undo_restores_name(self):
        """Undo restores the original name."""
        cmd = RenameGroupCommand(
            old_name='public.kern1.A',
            new_name='public.kern1.A.cap',
            groups_manager=self.manager,
            check_kerning=False,
        )
        cmd.execute(self.context)
        cmd.undo(self.context)

        self.assertIn('public.kern1.A', self.font.groups)
        self.assertNotIn('public.kern1.A.cap', self.font.groups)

    def test_undo_restores_kerning(self):
        """Undo restores original kerning references."""
        cmd = RenameGroupCommand(
            old_name='public.kern1.A',
            new_name='public.kern1.A.cap',
            groups_manager=self.manager,
            check_kerning=True,
        )
        cmd.execute(self.context)
        cmd.undo(self.context)

        # Original kerning should be restored
        self.assertEqual(self.font.kerning[('public.kern1.A', 'V')], -50)
        # New kerning should be removed
        self.assertNotIn(('public.kern1.A.cap', 'V'), self.font.kerning)


class TestSpacingEditorIntegration(unittest.TestCase):
    """Tests for SpacingEditor with mixed kerning and group commands."""

    def setUp(self):
        self.font = create_test_font()
        self.context = FontContext.from_single_font(self.font)
        self.font.groups['public.kern1.A'] = ('A', 'Aacute')
        self.font.kerning[('public.kern1.A', 'V')] = -50
        self.manager = FontGroupsManager(self.font)
        self.editor = SpacingEditor()

    def test_unified_history(self):
        """Kerning and group commands share the same history."""
        # Execute kerning command
        kern_cmd = AdjustKerningCommand(pair=('T', 'a'), delta=-20)
        self.editor.execute(kern_cmd, self.context)

        # Execute group command
        group_cmd = AddGlyphsToGroupCommand(
            group_name='public.kern1.A',
            glyphs=['Agrave'],
            groups_manager=self.manager,
            check_kerning=False,
        )
        self.editor.execute(group_cmd, self.context)

        self.assertEqual(self.editor.history_count, 2)

    def test_undo_order(self):
        """Undo works in correct order across command types."""
        # Execute kerning command
        kern_cmd = AdjustKerningCommand(pair=('T', 'a'), delta=-20)
        self.editor.execute(kern_cmd, self.context)

        # Execute group command
        group_cmd = AddGlyphsToGroupCommand(
            group_name='public.kern1.A',
            glyphs=['Agrave'],
            groups_manager=self.manager,
            check_kerning=False,
        )
        self.editor.execute(group_cmd, self.context)

        # Undo group command first
        self.editor.undo()
        self.assertNotIn('Agrave', self.font.groups['public.kern1.A'])
        self.assertEqual(self.font.kerning[('T', 'a')], -20)

        # Undo kerning command
        self.editor.undo()
        self.assertNotIn(('T', 'a'), self.font.kerning)

    def test_redo_order(self):
        """Redo works in correct order across command types."""
        # Execute both commands
        kern_cmd = AdjustKerningCommand(pair=('T', 'a'), delta=-20)
        self.editor.execute(kern_cmd, self.context)

        group_cmd = AddGlyphsToGroupCommand(
            group_name='public.kern1.A',
            glyphs=['Agrave'],
            groups_manager=self.manager,
            check_kerning=False,
        )
        self.editor.execute(group_cmd, self.context)

        # Undo both
        self.editor.undo()
        self.editor.undo()

        # Redo kerning first
        self.editor.redo()
        self.assertEqual(self.font.kerning[('T', 'a')], -20)
        self.assertNotIn('Agrave', self.font.groups.get('public.kern1.A', []))

        # Redo group
        self.editor.redo()
        self.assertIn('Agrave', self.font.groups['public.kern1.A'])

    def test_new_command_clears_redo(self):
        """New command after undo clears redo stack."""
        # Execute and undo
        kern_cmd = AdjustKerningCommand(pair=('T', 'a'), delta=-20)
        self.editor.execute(kern_cmd, self.context)
        self.editor.undo()

        self.assertTrue(self.editor.can_redo)

        # Execute new command
        group_cmd = AddGlyphsToGroupCommand(
            group_name='public.kern1.A',
            glyphs=['Agrave'],
            groups_manager=self.manager,
            check_kerning=False,
        )
        self.editor.execute(group_cmd, self.context)

        self.assertFalse(self.editor.can_redo)


if __name__ == '__main__':
    unittest.main(verbosity=2)
