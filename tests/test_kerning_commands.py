"""
Tests for Kerning Commands.

This module tests all kerning command classes:
- SetKerningCommand
- AdjustKerningCommand
- RemoveKerningCommand
- CreateExceptionCommand
"""

import unittest

from ufo_spacing_lib.commands.kerning import (
    AdjustKerningCommand,
    CreateExceptionCommand,
    RemoveKerningCommand,
    SetKerningCommand,
)
from ufo_spacing_lib.contexts import FontContext
from .mocks import create_test_font


class TestSetKerningCommand(unittest.TestCase):
    """Tests for SetKerningCommand."""

    def setUp(self):
        self.font = create_test_font()
        self.context = FontContext.from_single_font(self.font)

    def test_set_new_pair(self):
        """Setting kerning for a new pair."""
        cmd = SetKerningCommand(pair=('A', 'V'), value=-50)
        result = cmd.execute(self.context)

        self.assertTrue(result.success)
        self.assertEqual(self.font.kerning[('A', 'V')], -50)

    def test_set_existing_pair(self):
        """Setting kerning for an existing pair."""
        self.font.kerning[('A', 'V')] = -30

        cmd = SetKerningCommand(pair=('A', 'V'), value=-50)
        result = cmd.execute(self.context)

        self.assertTrue(result.success)
        self.assertEqual(self.font.kerning[('A', 'V')], -50)

    def test_undo_new_pair(self):
        """Undo should remove a newly created pair."""
        cmd = SetKerningCommand(pair=('A', 'V'), value=-50)
        cmd.execute(self.context)
        cmd.undo(self.context)

        self.assertNotIn(('A', 'V'), self.font.kerning)

    def test_undo_existing_pair(self):
        """Undo should restore the previous value."""
        self.font.kerning[('A', 'V')] = -30

        cmd = SetKerningCommand(pair=('A', 'V'), value=-50)
        cmd.execute(self.context)
        cmd.undo(self.context)

        self.assertEqual(self.font.kerning[('A', 'V')], -30)

    def test_scaled_value(self):
        """Value should be scaled when context has scale."""
        context = FontContext.from_single_font(self.font, scale=1.5)

        cmd = SetKerningCommand(pair=('A', 'V'), value=-50)
        cmd.execute(context)

        self.assertEqual(self.font.kerning[('A', 'V')], -75)  # -50 * 1.5


class TestAdjustKerningCommand(unittest.TestCase):
    """Tests for AdjustKerningCommand."""

    def setUp(self):
        self.font = create_test_font()
        self.context = FontContext.from_single_font(self.font)

    def test_adjust_new_pair(self):
        """Adjusting a non-existent pair starts from 0."""
        cmd = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
        result = cmd.execute(self.context)

        self.assertTrue(result.success)
        self.assertEqual(self.font.kerning[('A', 'V')], -10)

    def test_adjust_existing_pair(self):
        """Adjusting adds to the existing value."""
        self.font.kerning[('A', 'V')] = -40

        cmd = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
        cmd.execute(self.context)

        self.assertEqual(self.font.kerning[('A', 'V')], -50)

    def test_adjust_positive(self):
        """Positive delta increases the value."""
        self.font.kerning[('A', 'V')] = -50

        cmd = AdjustKerningCommand(pair=('A', 'V'), delta=10)
        cmd.execute(self.context)

        self.assertEqual(self.font.kerning[('A', 'V')], -40)

    def test_adjust_to_zero_removes(self):
        """Adjusting to zero removes the pair by default."""
        self.font.kerning[('A', 'V')] = -10

        cmd = AdjustKerningCommand(pair=('A', 'V'), delta=10)
        cmd.execute(self.context)

        self.assertNotIn(('A', 'V'), self.font.kerning)

    def test_adjust_to_zero_keeps_if_disabled(self):
        """Setting remove_zero=False keeps zero values."""
        self.font.kerning[('A', 'V')] = -10

        cmd = AdjustKerningCommand(pair=('A', 'V'), delta=10, remove_zero=False)
        cmd.execute(self.context)

        self.assertEqual(self.font.kerning[('A', 'V')], 0)

    def test_undo(self):
        """Undo restores the original value."""
        self.font.kerning[('A', 'V')] = -40

        cmd = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
        cmd.execute(self.context)
        cmd.undo(self.context)

        self.assertEqual(self.font.kerning[('A', 'V')], -40)

    def test_undo_removes_new_pair(self):
        """Undo removes a pair that didn't exist before."""
        cmd = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
        cmd.execute(self.context)
        cmd.undo(self.context)

        self.assertNotIn(('A', 'V'), self.font.kerning)

    def test_scaled_delta(self):
        """Delta should be scaled when context has scale."""
        self.font.kerning[('A', 'V')] = -40
        context = FontContext.from_single_font(self.font, scale=2.0)

        cmd = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
        cmd.execute(context)

        self.assertEqual(self.font.kerning[('A', 'V')], -60)  # -40 + (-10 * 2)


class TestRemoveKerningCommand(unittest.TestCase):
    """Tests for RemoveKerningCommand."""

    def setUp(self):
        self.font = create_test_font()
        self.context = FontContext.from_single_font(self.font)

    def test_remove_existing(self):
        """Removing an existing pair."""
        self.font.kerning[('A', 'V')] = -50

        cmd = RemoveKerningCommand(pair=('A', 'V'))
        result = cmd.execute(self.context)

        self.assertTrue(result.success)
        self.assertNotIn(('A', 'V'), self.font.kerning)

    def test_remove_nonexistent(self):
        """Removing a non-existent pair succeeds (idempotent)."""
        cmd = RemoveKerningCommand(pair=('A', 'V'))
        result = cmd.execute(self.context)

        self.assertTrue(result.success)

    def test_undo(self):
        """Undo restores the removed pair."""
        self.font.kerning[('A', 'V')] = -50

        cmd = RemoveKerningCommand(pair=('A', 'V'))
        cmd.execute(self.context)
        cmd.undo(self.context)

        self.assertEqual(self.font.kerning[('A', 'V')], -50)

    def test_undo_nonexistent(self):
        """Undo of non-existent pair does nothing."""
        cmd = RemoveKerningCommand(pair=('A', 'V'))
        cmd.execute(self.context)
        cmd.undo(self.context)

        self.assertNotIn(('A', 'V'), self.font.kerning)


class TestCreateExceptionCommand(unittest.TestCase):
    """Tests for CreateExceptionCommand."""

    def setUp(self):
        self.font = create_test_font()
        self.context = FontContext.from_single_font(self.font)

    def test_create_exception(self):
        """Creating an exception pair."""
        cmd = CreateExceptionCommand(pair=('Aacute', 'V'), value=-30)
        result = cmd.execute(self.context)

        self.assertTrue(result.success)
        self.assertEqual(self.font.kerning[('Aacute', 'V')], -30)

    def test_create_exception_zero(self):
        """Creating an exception with zero value."""
        cmd = CreateExceptionCommand(pair=('Aacute', 'V'), value=0)
        cmd.execute(self.context)

        self.assertEqual(self.font.kerning[('Aacute', 'V')], 0)

    def test_create_exception_default_zero(self):
        """Exception defaults to 0 if no value specified."""
        cmd = CreateExceptionCommand(pair=('Aacute', 'V'))
        cmd.execute(self.context)

        self.assertEqual(self.font.kerning[('Aacute', 'V')], 0)

    def test_undo(self):
        """Undo removes the created exception."""
        cmd = CreateExceptionCommand(pair=('Aacute', 'V'), value=-30)
        cmd.execute(self.context)
        cmd.undo(self.context)

        self.assertNotIn(('Aacute', 'V'), self.font.kerning)

    def test_undo_restores_previous(self):
        """Undo restores previous value if exception existed."""
        self.font.kerning[('Aacute', 'V')] = -20

        cmd = CreateExceptionCommand(pair=('Aacute', 'V'), value=-30)
        cmd.execute(self.context)
        cmd.undo(self.context)

        self.assertEqual(self.font.kerning[('Aacute', 'V')], -20)


class TestMultiFontOperations(unittest.TestCase):
    """Tests for multi-font operations."""

    def test_adjust_multiple_fonts(self):
        """Command applies to all fonts in context."""
        font1 = create_test_font()
        font2 = create_test_font()
        font1.kerning[('A', 'V')] = -40
        font2.kerning[('A', 'V')] = -40

        context = FontContext.from_linked_fonts(
            fonts=[font1, font2],
            primary=font1
        )

        cmd = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
        cmd.execute(context)

        self.assertEqual(font1.kerning[('A', 'V')], -50)
        self.assertEqual(font2.kerning[('A', 'V')], -50)

    def test_adjust_with_different_scales(self):
        """Each font gets scaled delta."""
        font1 = create_test_font()
        font2 = create_test_font()
        font1.kerning[('A', 'V')] = -40
        font2.kerning[('A', 'V')] = -40

        context = FontContext.from_linked_fonts(
            fonts=[font1, font2],
            primary=font1,
            scales={font1: 1.0, font2: 1.5}
        )

        cmd = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
        cmd.execute(context)

        self.assertEqual(font1.kerning[('A', 'V')], -50)  # -40 + (-10 * 1.0)
        self.assertEqual(font2.kerning[('A', 'V')], -55)  # -40 + (-10 * 1.5)

    def test_undo_multiple_fonts(self):
        """Undo works on all fonts."""
        font1 = create_test_font()
        font2 = create_test_font()
        font1.kerning[('A', 'V')] = -40
        font2.kerning[('A', 'V')] = -40

        context = FontContext.from_linked_fonts([font1, font2])

        cmd = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
        cmd.execute(context)
        cmd.undo(context)

        self.assertEqual(font1.kerning[('A', 'V')], -40)
        self.assertEqual(font2.kerning[('A', 'V')], -40)


if __name__ == '__main__':
    unittest.main(verbosity=2)

