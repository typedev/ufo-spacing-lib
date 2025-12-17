"""
Tests for VirtualFont.

Tests cover:
- VirtualFont creation from existing fonts
- Isolation of kerning/groups changes
- Live glyph access through source font
- Diff tracking
- Apply changes to real font
"""

import unittest

from ufo_spacing_lib import (
    AdjustKerningCommand,
    FontContext,
    KerningEditor,
    SetKerningCommand,
    VirtualFont,
)
from ufo_spacing_lib.groups_core import FontGroupsManager

from .mocks import MockFont, create_test_font_with_kerning


class TestVirtualFontCreation(unittest.TestCase):
    """Tests for VirtualFont creation and basic interface."""

    def test_from_font_copies_kerning(self):
        """VirtualFont.from_font should copy kerning data."""
        font = create_test_font_with_kerning()
        virtual = VirtualFont.from_font(font)

        # Should have same kerning initially
        self.assertEqual(
            virtual.kerning[('public.kern1.A', 'V')],
            font.kerning[('public.kern1.A', 'V')]
        )

    def test_from_font_copies_groups(self):
        """VirtualFont.from_font should copy groups data."""
        font = create_test_font_with_kerning()
        virtual = VirtualFont.from_font(font)

        # Should have same groups initially
        self.assertEqual(
            virtual.groups['public.kern1.A'],
            font.groups['public.kern1.A']
        )

    def test_from_font_maintains_source_reference(self):
        """VirtualFont should maintain reference to source font."""
        font = create_test_font_with_kerning()
        virtual = VirtualFont.from_font(font)

        self.assertIs(virtual.source, font)

    def test_empty_creates_empty_virtual_font(self):
        """VirtualFont.empty should create empty kerning/groups."""
        font = create_test_font_with_kerning()
        virtual = VirtualFont.empty(source=font)

        self.assertEqual(len(virtual.kerning), 0)
        self.assertEqual(len(virtual.groups), 0)
        self.assertIs(virtual.source, font)


class TestVirtualFontIsolation(unittest.TestCase):
    """Tests for data isolation between virtual and source fonts."""

    def test_kerning_changes_isolated_from_source(self):
        """Changes to virtual kerning should not affect source font."""
        font = create_test_font_with_kerning()
        original_value = font.kerning[('public.kern1.A', 'V')]

        virtual = VirtualFont.from_font(font)
        virtual.kerning[('public.kern1.A', 'V')] = -999

        # Source font should be unchanged
        self.assertEqual(font.kerning[('public.kern1.A', 'V')], original_value)
        # Virtual should have new value
        self.assertEqual(virtual.kerning[('public.kern1.A', 'V')], -999)

    def test_groups_changes_isolated_from_source(self):
        """Changes to virtual groups should not affect source font."""
        font = create_test_font_with_kerning()
        original_members = font.groups['public.kern1.A']

        virtual = VirtualFont.from_font(font)
        virtual.groups['public.kern1.A'] = ('A', 'Aacute', 'Agrave', 'Adieresis')

        # Source font should be unchanged
        self.assertEqual(font.groups['public.kern1.A'], original_members)
        # Virtual should have new value
        self.assertEqual(
            virtual.groups['public.kern1.A'],
            ('A', 'Aacute', 'Agrave', 'Adieresis')
        )

    def test_new_kerning_pairs_isolated(self):
        """New kerning pairs in virtual should not appear in source."""
        font = create_test_font_with_kerning()
        virtual = VirtualFont.from_font(font)

        virtual.kerning[('X', 'Y')] = -100

        self.assertIn(('X', 'Y'), virtual.kerning)
        self.assertNotIn(('X', 'Y'), font.kerning)

    def test_removed_kerning_pairs_isolated(self):
        """Removed kerning pairs from virtual should remain in source."""
        font = create_test_font_with_kerning()
        virtual = VirtualFont.from_font(font)

        del virtual.kerning[('public.kern1.A', 'V')]

        self.assertNotIn(('public.kern1.A', 'V'), virtual.kerning)
        self.assertIn(('public.kern1.A', 'V'), font.kerning)


class TestVirtualFontGlyphAccess(unittest.TestCase):
    """Tests for glyph access through source font."""

    def test_glyph_access_delegates_to_source(self):
        """Accessing glyphs should delegate to source font."""
        font = create_test_font_with_kerning()
        virtual = VirtualFont.from_font(font)

        # Should get same glyph object
        self.assertIs(virtual['A'], font['A'])

    def test_glyph_changes_in_source_visible_in_virtual(self):
        """Changes to source font glyphs should be visible through virtual."""
        font = create_test_font_with_kerning()
        virtual = VirtualFont.from_font(font)

        # Modify glyph in source font
        font['A'].leftMargin = 999

        # Should see change through virtual
        self.assertEqual(virtual['A'].leftMargin, 999)

    def test_glyph_contains_check(self):
        """__contains__ should check source font."""
        font = create_test_font_with_kerning()
        virtual = VirtualFont.from_font(font)

        self.assertIn('A', virtual)
        self.assertNotIn('nonexistent', virtual)

    def test_glyph_access_without_source_raises(self):
        """Glyph access without source font should raise KeyError."""
        virtual = VirtualFont(kerning={}, groups={}, source=None)

        with self.assertRaises(KeyError):
            _ = virtual['A']


class TestVirtualFontWithCommands(unittest.TestCase):
    """Tests for using VirtualFont with commands and editors."""

    def test_set_kerning_command(self):
        """SetKerningCommand should work with VirtualFont."""
        font = create_test_font_with_kerning()
        virtual = VirtualFont.from_font(font)

        editor = KerningEditor()
        context = FontContext.from_single_font(virtual)

        cmd = SetKerningCommand(pair=('A', 'V'), value=-100)
        result = editor.execute(cmd, context)

        self.assertTrue(result.success)
        self.assertEqual(virtual.kerning[('A', 'V')], -100)
        # Source unchanged
        self.assertNotEqual(font.kerning.get(('A', 'V')), -100)

    def test_adjust_kerning_command(self):
        """AdjustKerningCommand should work with VirtualFont."""
        font = create_test_font_with_kerning()
        original = font.kerning[('public.kern1.A', 'V')]

        virtual = VirtualFont.from_font(font)
        editor = KerningEditor()
        context = FontContext.from_single_font(virtual)

        cmd = AdjustKerningCommand(pair=('public.kern1.A', 'V'), delta=-10)
        result = editor.execute(cmd, context)

        self.assertTrue(result.success)
        self.assertEqual(virtual.kerning[('public.kern1.A', 'V')], original - 10)
        # Source unchanged
        self.assertEqual(font.kerning[('public.kern1.A', 'V')], original)

    def test_undo_redo_with_virtual_font(self):
        """Undo/redo should work correctly with VirtualFont."""
        font = create_test_font_with_kerning()
        virtual = VirtualFont.from_font(font)
        original = virtual.kerning[('public.kern1.A', 'V')]

        editor = KerningEditor()
        context = FontContext.from_single_font(virtual)

        cmd = SetKerningCommand(pair=('public.kern1.A', 'V'), value=-999)
        editor.execute(cmd, context)
        self.assertEqual(virtual.kerning[('public.kern1.A', 'V')], -999)

        editor.undo()
        self.assertEqual(virtual.kerning[('public.kern1.A', 'V')], original)

        editor.redo()
        self.assertEqual(virtual.kerning[('public.kern1.A', 'V')], -999)


class TestVirtualFontWithGroupsManager(unittest.TestCase):
    """Tests for using VirtualFont with FontGroupsManager."""

    def test_groups_manager_works_with_virtual_font(self):
        """FontGroupsManager should work with VirtualFont."""
        font = create_test_font_with_kerning()
        virtual = VirtualFont.from_font(font)

        manager = FontGroupsManager(virtual)

        # Should find groups
        group = manager.get_group_for_glyph('A', 'L')
        self.assertEqual(group, 'public.kern1.A')

    def test_groups_manager_modifications_isolated(self):
        """FontGroupsManager modifications should only affect virtual."""
        font = create_test_font_with_kerning()
        original_groups = dict(font.groups)

        virtual = VirtualFont.from_font(font)
        manager = FontGroupsManager(virtual)

        # Add glyph to group
        manager.add_glyphs_to_group('public.kern1.A', ['Adieresis'])

        # Virtual should be modified
        self.assertIn('Adieresis', virtual.groups['public.kern1.A'])
        # Source should be unchanged
        self.assertEqual(font.groups['public.kern1.A'], original_groups['public.kern1.A'])


class TestVirtualFontDiff(unittest.TestCase):
    """Tests for diff tracking."""

    def test_get_kerning_diff_modified(self):
        """get_kerning_diff should track modified pairs."""
        font = create_test_font_with_kerning()
        virtual = VirtualFont.from_font(font)

        original = virtual.kerning[('public.kern1.A', 'V')]
        virtual.kerning[('public.kern1.A', 'V')] = -999

        diff = virtual.get_kerning_diff()
        self.assertIn(('public.kern1.A', 'V'), diff)
        self.assertEqual(diff[('public.kern1.A', 'V')], (original, -999))

    def test_get_kerning_diff_added(self):
        """get_kerning_diff should track added pairs."""
        font = create_test_font_with_kerning()
        virtual = VirtualFont.from_font(font)

        virtual.kerning[('X', 'Y')] = -50

        diff = virtual.get_kerning_diff()
        self.assertIn(('X', 'Y'), diff)
        self.assertEqual(diff[('X', 'Y')], (None, -50))

    def test_get_kerning_diff_removed(self):
        """get_kerning_diff should track removed pairs."""
        font = create_test_font_with_kerning()
        virtual = VirtualFont.from_font(font)

        original = virtual.kerning[('public.kern1.A', 'V')]
        del virtual.kerning[('public.kern1.A', 'V')]

        diff = virtual.get_kerning_diff()
        self.assertIn(('public.kern1.A', 'V'), diff)
        self.assertEqual(diff[('public.kern1.A', 'V')], (original, None))

    def test_has_changes_true_when_modified(self):
        """has_changes should return True after modifications."""
        font = create_test_font_with_kerning()
        virtual = VirtualFont.from_font(font)

        self.assertFalse(virtual.has_changes())

        virtual.kerning[('X', 'Y')] = -50
        self.assertTrue(virtual.has_changes())

    def test_has_changes_false_initially(self):
        """has_changes should return False for unmodified virtual font."""
        font = create_test_font_with_kerning()
        virtual = VirtualFont.from_font(font)

        self.assertFalse(virtual.has_changes())


class TestVirtualFontApply(unittest.TestCase):
    """Tests for applying changes to real font."""

    def test_apply_kerning_changes(self):
        """apply_to should apply kerning changes to target font."""
        font = create_test_font_with_kerning()
        virtual = VirtualFont.from_font(font)

        virtual.kerning[('public.kern1.A', 'V')] = -999
        virtual.kerning[('X', 'Y')] = -50
        del virtual.kerning[('A', 'W')]

        virtual.apply_to(font)

        self.assertEqual(font.kerning[('public.kern1.A', 'V')], -999)
        self.assertEqual(font.kerning[('X', 'Y')], -50)
        self.assertNotIn(('A', 'W'), font.kerning)

    def test_apply_groups_changes(self):
        """apply_to should apply groups changes to target font."""
        font = create_test_font_with_kerning()
        virtual = VirtualFont.from_font(font)

        virtual.groups['public.kern1.A'] = ('A', 'Aacute', 'Agrave', 'Adieresis')
        virtual.groups['public.kern1.NEW'] = ('X', 'Y')

        virtual.apply_to(font)

        self.assertEqual(
            font.groups['public.kern1.A'],
            ('A', 'Aacute', 'Agrave', 'Adieresis')
        )
        self.assertEqual(font.groups['public.kern1.NEW'], ('X', 'Y'))

    def test_apply_selective(self):
        """apply_to should support selective application."""
        font = create_test_font_with_kerning()
        original_groups = dict(font.groups)

        virtual = VirtualFont.from_font(font)
        virtual.kerning[('X', 'Y')] = -50
        virtual.groups['public.kern1.A'] = ('A',)

        # Apply only kerning
        virtual.apply_to(font, kerning=True, groups=False)

        self.assertEqual(font.kerning[('X', 'Y')], -50)
        self.assertEqual(font.groups['public.kern1.A'], original_groups['public.kern1.A'])


class TestVirtualFontReset(unittest.TestCase):
    """Tests for reset functionality."""

    def test_reset_restores_original_state(self):
        """reset should restore kerning and groups to original state."""
        font = create_test_font_with_kerning()
        virtual = VirtualFont.from_font(font)

        original_kerning = dict(virtual.kerning)
        original_groups = dict(virtual.groups)

        # Make changes
        virtual.kerning[('X', 'Y')] = -50
        virtual.groups['public.kern1.A'] = ('A',)

        virtual.reset()

        self.assertEqual(dict(virtual.kerning), original_kerning)
        self.assertEqual(dict(virtual.groups), original_groups)

    def test_reset_kerning_only(self):
        """reset_kerning should only restore kerning."""
        font = create_test_font_with_kerning()
        virtual = VirtualFont.from_font(font)

        original_kerning = dict(virtual.kerning)

        virtual.kerning[('X', 'Y')] = -50
        virtual.groups['public.kern1.A'] = ('A',)

        virtual.reset_kerning()

        self.assertEqual(dict(virtual.kerning), original_kerning)
        self.assertEqual(virtual.groups['public.kern1.A'], ('A',))  # Groups unchanged


if __name__ == '__main__':
    unittest.main()
