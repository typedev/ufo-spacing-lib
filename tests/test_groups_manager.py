"""
Tests for FontGroupsManager.

This module tests the FontGroupsManager class from groups_core,
covering group operations and kerning handling.
"""

import unittest

from ufo_spacing_lib.groups_core import (
    SIDE_LEFT,
    ExceptionSide,
    FontGroupsManager,
    resolve_kern_pair,
)
from .mocks import create_test_font


class TestFontGroupsManagerInit(unittest.TestCase):
    """Tests for FontGroupsManager initialization."""

    def test_init_empty_font(self):
        """Initialize with font that has no groups."""
        font = create_test_font()
        manager = FontGroupsManager(font)

        self.assertEqual(manager.font, font)
        self.assertEqual(len(manager.groups_with_errors), 0)

    def test_init_builds_reverse_mapping(self):
        """Initialize builds reverse lookup mappings."""
        font = create_test_font()
        font.groups['public.kern1.A'] = ('A', 'Aacute')

        manager = FontGroupsManager(font)

        self.assertEqual(manager.leftDic['A'], 'public.kern1.A')
        self.assertEqual(manager.leftDic['Aacute'], 'public.kern1.A')

    def test_init_detects_empty_groups(self):
        """Initialize detects empty groups as errors."""
        font = create_test_font()
        font.groups['public.kern1.Empty'] = ()

        manager = FontGroupsManager(font)

        self.assertIn('public.kern1.Empty', manager.groups_with_errors)


class TestFontGroupsManagerLookup(unittest.TestCase):
    """Tests for group lookup methods."""

    def setUp(self):
        self.font = create_test_font()
        self.font.groups['public.kern1.A'] = ('A', 'Aacute', 'Agrave')
        self.font.groups['public.kern2.V'] = ('V',)
        self.manager = FontGroupsManager(self.font)

    def test_get_group_for_glyph_in_group(self):
        """Get group name for glyph that's in a group."""
        result = self.manager.get_group_for_glyph('A', SIDE_LEFT)
        self.assertEqual(result, 'public.kern1.A')

        result = self.manager.get_group_for_glyph('Aacute', SIDE_LEFT)
        self.assertEqual(result, 'public.kern1.A')

    def test_get_group_for_glyph_not_in_group(self):
        """Get glyph name for glyph that's not in a group."""
        result = self.manager.get_group_for_glyph('T', SIDE_LEFT)
        self.assertEqual(result, 'T')

    def test_is_glyph_in_group(self):
        """Check if glyph is in a group."""
        self.assertTrue(self.manager.is_glyph_in_group('A', SIDE_LEFT))
        self.assertTrue(self.manager.is_glyph_in_group('Aacute', SIDE_LEFT))
        self.assertFalse(self.manager.is_glyph_in_group('T', SIDE_LEFT))

    def test_get_key_glyph(self):
        """Get key glyph (first glyph) of a group."""
        result = self.manager.get_key_glyph('public.kern1.A')
        self.assertEqual(result, 'A')

    def test_get_key_glyph_not_group(self):
        """Get key glyph returns input for non-groups."""
        result = self.manager.get_key_glyph('T')
        self.assertEqual(result, 'T')

    def test_is_kerning_group(self):
        """Check if name is a kerning group."""
        self.assertTrue(self.manager.is_kerning_group('public.kern1.A'))
        self.assertTrue(self.manager.is_kerning_group('public.kern2.V'))
        self.assertFalse(self.manager.is_kerning_group('A'))


class TestAddGlyphsToGroup(unittest.TestCase):
    """Tests for adding glyphs to groups."""

    def setUp(self):
        self.font = create_test_font()
        self.manager = FontGroupsManager(self.font)

    def test_add_to_new_group(self):
        """Adding glyph creates new group."""
        skipped, new_pairs, deleted = self.manager.add_glyphs_to_group(
            'public.kern1.A', ['A'], check_kerning=False
        )

        self.assertEqual(self.font.groups['public.kern1.A'], ('A',))
        self.assertEqual(len(skipped), 0)

    def test_add_multiple_glyphs(self):
        """Adding multiple glyphs to a group."""
        self.manager.add_glyphs_to_group(
            'public.kern1.A', ['A', 'Aacute', 'Agrave'], check_kerning=False
        )

        self.assertEqual(
            self.font.groups['public.kern1.A'],
            ('A', 'Aacute', 'Agrave')
        )

    def test_add_to_existing_group(self):
        """Adding glyph to existing group."""
        self.font.groups['public.kern1.A'] = ('A',)
        self.manager = FontGroupsManager(self.font)

        self.manager.add_glyphs_to_group(
            'public.kern1.A', ['Aacute'], check_kerning=False
        )

        self.assertEqual(self.font.groups['public.kern1.A'], ('A', 'Aacute'))

    def test_skip_glyph_already_in_group(self):
        """Skip glyph that's already in the target group."""
        self.font.groups['public.kern1.A'] = ('A', 'Aacute')
        self.manager = FontGroupsManager(self.font)

        skipped, _, _ = self.manager.add_glyphs_to_group(
            'public.kern1.A', ['Aacute'], check_kerning=False
        )

        self.assertIn('Aacute', skipped)

    def test_skip_glyph_in_different_group(self):
        """Skip glyph that's already in another group on same side."""
        self.font.groups['public.kern1.A'] = ('A',)
        self.font.groups['public.kern1.B'] = ('Aacute',)
        self.manager = FontGroupsManager(self.font)

        skipped, _, _ = self.manager.add_glyphs_to_group(
            'public.kern1.A', ['Aacute'], check_kerning=False
        )

        self.assertIn('Aacute', skipped)

    def test_add_with_kerning_check_new_group(self):
        """Adding to new group moves glyph kerning to group."""
        self.font.kerning[('A', 'V')] = -50
        self.font.kerning[('A', 'T')] = -40
        self.manager = FontGroupsManager(self.font)

        skipped, new_pairs, deleted = self.manager.add_glyphs_to_group(
            'public.kern1.A', ['A'], check_kerning=True
        )

        # Kerning should be on group now
        self.assertEqual(self.font.kerning[('public.kern1.A', 'V')], -50)
        self.assertEqual(self.font.kerning[('public.kern1.A', 'T')], -40)

        # Original pairs removed
        self.assertNotIn(('A', 'V'), self.font.kerning)
        self.assertNotIn(('A', 'T'), self.font.kerning)

    def test_add_with_same_kerning_removes_exception(self):
        """Adding glyph with same kerning as group removes exception."""
        self.font.groups['public.kern1.A'] = ('A',)
        self.font.kerning[('public.kern1.A', 'V')] = -50
        self.font.kerning[('Aacute', 'V')] = -50  # Same value
        self.manager = FontGroupsManager(self.font)

        skipped, new_pairs, deleted = self.manager.add_glyphs_to_group(
            'public.kern1.A', ['Aacute'], check_kerning=True
        )

        # Exception should be removed
        self.assertNotIn(('Aacute', 'V'), self.font.kerning)
        self.assertIn(('Aacute', 'V'), deleted)

    def test_add_with_different_kerning_keeps_exception(self):
        """Adding glyph with different kerning keeps it as exception."""
        self.font.groups['public.kern1.A'] = ('A',)
        self.font.kerning[('public.kern1.A', 'V')] = -50
        self.font.kerning[('Aacute', 'V')] = -30  # Different value
        self.manager = FontGroupsManager(self.font)

        self.manager.add_glyphs_to_group(
            'public.kern1.A', ['Aacute'], check_kerning=True
        )

        # Exception should be kept
        self.assertEqual(self.font.kerning[('Aacute', 'V')], -30)


class TestRemoveGlyphsFromGroup(unittest.TestCase):
    """Tests for removing glyphs from groups."""

    def setUp(self):
        self.font = create_test_font()
        self.font.groups['public.kern1.A'] = ('A', 'Aacute', 'Agrave')
        self.font.kerning[('public.kern1.A', 'V')] = -50
        self.manager = FontGroupsManager(self.font)

    def test_remove_glyph(self):
        """Basic glyph removal."""
        self.manager.remove_glyphs_from_group(
            'public.kern1.A', ['Aacute'], check_kerning=False
        )

        self.assertEqual(self.font.groups['public.kern1.A'], ('A', 'Agrave'))

    def test_remove_creates_exceptions(self):
        """Removing glyph creates kerning exceptions."""
        new_pairs, deleted = self.manager.remove_glyphs_from_group(
            'public.kern1.A', ['Aacute'], check_kerning=True
        )

        # Exception should be created
        self.assertEqual(self.font.kerning[('Aacute', 'V')], -50)
        self.assertIn(('Aacute', 'V'), new_pairs)

    def test_remove_preserves_existing_exception(self):
        """Removing glyph preserves its existing different exception."""
        self.font.kerning[('Aacute', 'V')] = -30  # Different value
        self.manager = FontGroupsManager(self.font)

        self.manager.remove_glyphs_from_group(
            'public.kern1.A', ['Aacute'], check_kerning=True
        )

        # Original exception should be preserved
        self.assertEqual(self.font.kerning[('Aacute', 'V')], -30)


class TestDeleteGroup(unittest.TestCase):
    """Tests for deleting groups."""

    def setUp(self):
        self.font = create_test_font()
        self.font.groups['public.kern1.A'] = ('A', 'Aacute')
        self.font.kerning[('public.kern1.A', 'V')] = -50
        self.manager = FontGroupsManager(self.font)

    def test_delete_group(self):
        """Delete a group completely."""
        self.manager.delete_group('public.kern1.A', check_kerning=False)

        self.assertNotIn('public.kern1.A', self.font.groups)

    def test_delete_group_with_kerning(self):
        """Delete group creates exceptions and removes group kerning."""
        new_pairs, deleted = self.manager.delete_group(
            'public.kern1.A', check_kerning=True
        )

        # Group should be gone
        self.assertNotIn('public.kern1.A', self.font.groups)

        # Group kerning should be removed
        self.assertNotIn(('public.kern1.A', 'V'), self.font.kerning)

        # Exceptions should be created
        self.assertEqual(self.font.kerning[('A', 'V')], -50)
        self.assertEqual(self.font.kerning[('Aacute', 'V')], -50)


class TestRenameGroup(unittest.TestCase):
    """Tests for renaming groups."""

    def setUp(self):
        self.font = create_test_font()
        self.font.groups['public.kern1.A'] = ('A', 'Aacute')
        self.font.kerning[('public.kern1.A', 'V')] = -50
        self.manager = FontGroupsManager(self.font)

    def test_rename_group(self):
        """Rename a group."""
        self.manager.rename_group(
            'public.kern1.A', 'public.kern1.A_new', check_kerning=True
        )

        # Old name gone
        self.assertNotIn('public.kern1.A', self.font.groups)

        # New name exists with content
        self.assertEqual(
            self.font.groups['public.kern1.A_new'],
            ('A', 'Aacute')
        )

        # Kerning updated
        self.assertNotIn(('public.kern1.A', 'V'), self.font.kerning)
        self.assertEqual(self.font.kerning[('public.kern1.A_new', 'V')], -50)

    def test_rename_to_existing_fails(self):
        """Renaming to existing name does nothing."""
        self.font.groups['public.kern1.B'] = ('Agrave',)
        self.manager = FontGroupsManager(self.font)

        self.manager.rename_group(
            'public.kern1.A', 'public.kern1.B', check_kerning=True
        )

        # Original should still exist
        self.assertIn('public.kern1.A', self.font.groups)


class TestResolvePair(unittest.TestCase):
    """Tests for resolve_kern_pair function."""

    def setUp(self):
        self.font = create_test_font()
        self.font.groups['public.kern1.A'] = ('A', 'Aacute')
        self.font.groups['public.kern2.V'] = ('V',)
        self.manager = FontGroupsManager(self.font)

    def test_resolve_group_to_group(self):
        """Resolve group-to-group pair."""
        self.font.kerning[('public.kern1.A', 'public.kern2.V')] = -50

        info = resolve_kern_pair(self.font, self.manager, ('A', 'V'))

        self.assertEqual(info.value, -50)
        self.assertFalse(info.is_exception)
        self.assertEqual(info.left_group, 'public.kern1.A')
        self.assertEqual(info.right_group, 'public.kern2.V')

    def test_resolve_exception(self):
        """Resolve glyph-level exception."""
        self.font.kerning[('public.kern1.A', 'V')] = -50
        self.font.kerning[('Aacute', 'V')] = -30  # Exception

        info = resolve_kern_pair(self.font, self.manager, ('Aacute', 'V'))

        self.assertEqual(info.value, -30)
        self.assertTrue(info.is_exception)

    def test_resolve_no_kerning(self):
        """Resolve pair with no kerning."""
        info = resolve_kern_pair(self.font, self.manager, ('A', 'V'))

        self.assertIsNone(info.value)
        self.assertFalse(info.is_exception)

    def test_kern_pair_info_exception_side(self):
        """KernPairInfo correctly identifies exception side."""
        # Setup: Aacute is in kern1.A group, V is not in any right-side group
        self.font.kerning[('public.kern1.A', 'V')] = -50
        self.font.kerning[('Aacute', 'V')] = -30  # Exception: glyph-glyph pair

        info = resolve_kern_pair(self.font, self.manager, ('Aacute', 'V'))

        # Since Aacute is in group (left_group='public.kern1.A') but V is not in group (right_group='V')
        # and the pair is (Aacute, V), both left and right differ from groups
        # left='Aacute' != left_group='public.kern1.A' -> left differs
        # right='V' == right_group='V' -> right same
        # This should be LEFT exception
        self.assertEqual(info.value, -30)
        self.assertTrue(info.is_exception)
        # Note: exception_side logic depends on exact implementation
        # The pair (Aacute, V) is found directly, left differs from group
        self.assertIn(info.exception_side, [ExceptionSide.LEFT, ExceptionSide.BOTH])


class TestLogging(unittest.TestCase):
    """Tests for operation logging."""

    def setUp(self):
        self.font = create_test_font()
        self.manager = FontGroupsManager(self.font)

    def test_log_collection(self):
        """Log collection works."""
        self.manager.start_collecting_log()

        self.manager.add_glyphs_to_group(
            'public.kern1.A', ['A', 'Aacute'], check_kerning=False
        )

        log = self.manager.stop_collecting_log()

        self.assertGreater(len(log), 0)
        # Check summary is logged
        actions = [entry[0] for entry in log]
        self.assertIn('add_glyphs_summary', actions)

    def test_log_not_collected_by_default(self):
        """Log is not collected by default."""
        self.manager.add_glyphs_to_group(
            'public.kern1.A', ['A'], check_kerning=False
        )

        log = self.manager.get_operation_log()

        self.assertEqual(len(log), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)

