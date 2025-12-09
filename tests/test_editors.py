"""
Tests for Editors.

This module tests the KerningEditor and MarginsEditor classes,
focusing on undo/redo functionality and event callbacks.
"""

import unittest

from ufo_spacing_lib.commands.kerning import AdjustKerningCommand, SetKerningCommand
from ufo_spacing_lib.commands.margins import AdjustMarginCommand
from ufo_spacing_lib.contexts import FontContext
from ufo_spacing_lib.editors.kerning import KerningEditor
from ufo_spacing_lib.editors.margins import MarginsEditor
from .mocks import create_test_font


class TestKerningEditorBasic(unittest.TestCase):
    """Basic tests for KerningEditor."""

    def setUp(self):
        self.font = create_test_font()
        self.context = FontContext.from_single_font(self.font)
        self.editor = KerningEditor()

    def test_execute_success(self):
        """Successful command execution."""
        cmd = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
        result = self.editor.execute(cmd, self.context)

        self.assertTrue(result.success)
        self.assertEqual(self.font.kerning[('A', 'V')], -10)

    def test_execute_adds_to_history(self):
        """Successful execution adds command to history."""
        cmd = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
        self.editor.execute(cmd, self.context)

        self.assertEqual(self.editor.history_count, 1)
        self.assertTrue(self.editor.can_undo)

    def test_initial_state(self):
        """Editor starts with empty history."""
        self.assertEqual(self.editor.history_count, 0)
        self.assertEqual(self.editor.redo_count, 0)
        self.assertFalse(self.editor.can_undo)
        self.assertFalse(self.editor.can_redo)


class TestKerningEditorUndo(unittest.TestCase):
    """Tests for KerningEditor undo functionality."""

    def setUp(self):
        self.font = create_test_font()
        self.context = FontContext.from_single_font(self.font)
        self.editor = KerningEditor()

    def test_undo_single(self):
        """Undo a single command."""
        cmd = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
        self.editor.execute(cmd, self.context)
        self.editor.undo()

        self.assertNotIn(('A', 'V'), self.font.kerning)
        self.assertFalse(self.editor.can_undo)
        self.assertTrue(self.editor.can_redo)

    def test_undo_multiple(self):
        """Undo multiple commands in order."""
        cmd1 = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
        cmd2 = AdjustKerningCommand(pair=('A', 'V'), delta=-10)

        self.editor.execute(cmd1, self.context)
        self.editor.execute(cmd2, self.context)

        self.assertEqual(self.font.kerning[('A', 'V')], -20)

        self.editor.undo()
        self.assertEqual(self.font.kerning[('A', 'V')], -10)

        self.editor.undo()
        self.assertNotIn(('A', 'V'), self.font.kerning)

    def test_undo_empty_returns_none(self):
        """Undo with empty history returns None."""
        result = self.editor.undo()
        self.assertIsNone(result)


class TestKerningEditorRedo(unittest.TestCase):
    """Tests for KerningEditor redo functionality."""

    def setUp(self):
        self.font = create_test_font()
        self.context = FontContext.from_single_font(self.font)
        self.editor = KerningEditor()

    def test_redo_after_undo(self):
        """Redo restores the undone command."""
        cmd = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
        self.editor.execute(cmd, self.context)
        self.editor.undo()
        self.editor.redo()

        self.assertEqual(self.font.kerning[('A', 'V')], -10)
        self.assertTrue(self.editor.can_undo)
        self.assertFalse(self.editor.can_redo)

    def test_redo_multiple(self):
        """Redo multiple commands in order."""
        cmd1 = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
        cmd2 = AdjustKerningCommand(pair=('A', 'V'), delta=-10)

        self.editor.execute(cmd1, self.context)
        self.editor.execute(cmd2, self.context)
        self.editor.undo()
        self.editor.undo()

        self.editor.redo()
        self.assertEqual(self.font.kerning[('A', 'V')], -10)

        self.editor.redo()
        self.assertEqual(self.font.kerning[('A', 'V')], -20)

    def test_redo_empty_returns_none(self):
        """Redo with empty stack returns None."""
        result = self.editor.redo()
        self.assertIsNone(result)

    def test_new_command_clears_redo(self):
        """New command clears redo stack."""
        cmd1 = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
        cmd2 = AdjustKerningCommand(pair=('A', 'T'), delta=-10)

        self.editor.execute(cmd1, self.context)
        self.editor.undo()

        self.assertTrue(self.editor.can_redo)

        self.editor.execute(cmd2, self.context)

        self.assertFalse(self.editor.can_redo)


class TestKerningEditorCallbacks(unittest.TestCase):
    """Tests for KerningEditor event callbacks."""

    def setUp(self):
        self.font = create_test_font()
        self.context = FontContext.from_single_font(self.font)
        self.editor = KerningEditor()
        self.callback_calls = []

    def test_on_change_callback(self):
        """on_change is called after execute."""
        def callback(cmd, result):
            self.callback_calls.append(('change', cmd, result))

        self.editor.on_change = callback

        cmd = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
        self.editor.execute(cmd, self.context)

        self.assertEqual(len(self.callback_calls), 1)
        self.assertEqual(self.callback_calls[0][0], 'change')
        self.assertEqual(self.callback_calls[0][1], cmd)

    def test_on_undo_callback(self):
        """on_undo is called after undo."""
        def callback(cmd, result):
            self.callback_calls.append(('undo', cmd, result))

        self.editor.on_undo = callback

        cmd = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
        self.editor.execute(cmd, self.context)
        self.editor.undo()

        self.assertEqual(len(self.callback_calls), 1)
        self.assertEqual(self.callback_calls[0][0], 'undo')

    def test_on_redo_callback(self):
        """on_redo is called after redo."""
        def callback(cmd, result):
            self.callback_calls.append(('redo', cmd, result))

        self.editor.on_redo = callback

        cmd = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
        self.editor.execute(cmd, self.context)
        self.editor.undo()
        self.editor.redo()

        self.assertEqual(len(self.callback_calls), 1)
        self.assertEqual(self.callback_calls[0][0], 'redo')


class TestKerningEditorDescriptions(unittest.TestCase):
    """Tests for undo/redo descriptions."""

    def setUp(self):
        self.font = create_test_font()
        self.context = FontContext.from_single_font(self.font)
        self.editor = KerningEditor()

    def test_undo_description(self):
        """undo_description returns the last command's description."""
        cmd = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
        self.editor.execute(cmd, self.context)

        self.assertEqual(
            self.editor.undo_description,
            "Adjust kerning ('A', 'V') -10"
        )

    def test_undo_description_empty(self):
        """undo_description is None when history is empty."""
        self.assertIsNone(self.editor.undo_description)

    def test_redo_description(self):
        """redo_description returns the next redo command's description."""
        cmd = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
        self.editor.execute(cmd, self.context)
        self.editor.undo()

        self.assertEqual(
            self.editor.redo_description,
            "Adjust kerning ('A', 'V') -10"
        )

    def test_redo_description_empty(self):
        """redo_description is None when redo stack is empty."""
        self.assertIsNone(self.editor.redo_description)


class TestKerningEditorHistory(unittest.TestCase):
    """Tests for history management."""

    def setUp(self):
        self.font = create_test_font()
        self.context = FontContext.from_single_font(self.font)
        self.editor = KerningEditor()

    def test_clear_history(self):
        """clear_history removes all history."""
        cmd = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
        self.editor.execute(cmd, self.context)
        self.editor.undo()

        self.editor.clear_history()

        self.assertFalse(self.editor.can_undo)
        self.assertFalse(self.editor.can_redo)
        self.assertEqual(self.editor.history_count, 0)
        self.assertEqual(self.editor.redo_count, 0)

    def test_get_history(self):
        """get_history returns list of descriptions."""
        cmd1 = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
        cmd2 = SetKerningCommand(pair=('A', 'T'), value=-40)

        self.editor.execute(cmd1, self.context)
        self.editor.execute(cmd2, self.context)

        history = self.editor.get_history()

        self.assertEqual(len(history), 2)
        self.assertIn("-10", history[0])
        self.assertIn("-40", history[1])


class TestMarginsEditorBasic(unittest.TestCase):
    """Basic tests for MarginsEditor."""

    def setUp(self):
        self.font = create_test_font()
        self.context = FontContext.from_single_font(self.font)
        self.editor = MarginsEditor()

    def test_execute_and_undo(self):
        """MarginsEditor works like KerningEditor."""
        original_margin = self.font['A'].leftMargin

        cmd = AdjustMarginCommand(
            glyph_name='A',
            side='left',
            delta=10,
            propagate_to_composites=False
        )
        self.editor.execute(cmd, self.context)

        self.assertEqual(self.font['A'].leftMargin, original_margin + 10)

        self.editor.undo()

        self.assertEqual(self.font['A'].leftMargin, original_margin)


if __name__ == '__main__':
    unittest.main(verbosity=2)

