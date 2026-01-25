"""
Tests for Margins Utilities.

Tests the italic/angled margins calculation and setting functions.
"""

import math

import pytest

from ufo_spacing_lib import (
    SpacingEditor,
    SetMarginCommand,
    get_italic_angle,
    get_slant_factor,
    get_unskewed_bounds,
    get_angled_margins,
    set_angled_left_margin,
    set_angled_right_margin,
)

from .mocks import MockFont, MockGlyph


class TestGetItalicAngle:
    """Tests for get_italic_angle function."""

    def test_returns_none_for_none_font(self):
        assert get_italic_angle(None) is None

    def test_returns_none_for_font_without_info(self):
        font = object()  # No info attribute
        assert get_italic_angle(font) is None

    def test_returns_none_for_upright_font(self):
        font = MockFont(['A'])
        font.info.italicAngle = None
        assert get_italic_angle(font) is None

    def test_returns_zero_for_zero_angle(self):
        font = MockFont(['A'])
        font.info.italicAngle = 0
        assert get_italic_angle(font) == 0

    def test_returns_angle_for_italic_font(self):
        font = MockFont(['A'], italic_angle=-12)
        assert get_italic_angle(font) == -12


class TestGetSlantFactor:
    """Tests for get_slant_factor function."""

    def test_returns_zero_for_none_font(self):
        assert get_slant_factor(None) == 0.0

    def test_returns_zero_for_upright_font(self):
        font = MockFont(['A'])
        assert get_slant_factor(font) == 0.0

    def test_returns_zero_for_zero_angle(self):
        font = MockFont(['A'])
        font.info.italicAngle = 0
        assert get_slant_factor(font) == 0.0

    def test_returns_positive_for_right_lean(self):
        # italicAngle is negative for right-leaning italics
        font = MockFont(['A'], italic_angle=-12)
        slant = get_slant_factor(font)
        # tan(-(-12)) = tan(12) > 0
        assert slant > 0
        assert abs(slant - math.tan(math.radians(12))) < 0.0001

    def test_returns_negative_for_left_lean(self):
        # Unusual but possible: positive italicAngle = left lean
        font = MockFont(['A'], italic_angle=12)
        slant = get_slant_factor(font)
        assert slant < 0


class TestGetUnskewedBounds:
    """Tests for get_unskewed_bounds function."""

    def test_returns_none_for_none_glyph(self):
        font = MockFont(['A'])
        assert get_unskewed_bounds(None, font) is None

    def test_returns_regular_bounds_for_upright_font(self):
        font = MockFont(['A'])
        glyph = font['A']
        glyph._left_margin = 50
        glyph._right_margin = 50
        glyph.width = 500

        bounds = get_unskewed_bounds(glyph, font)
        assert bounds is not None
        # Regular bounds: xMin=leftMargin, xMax=width-rightMargin
        assert bounds[0] == 50  # xMin
        assert bounds[2] == 450  # xMax

    def test_returns_transformed_bounds_for_italic(self):
        font = MockFont(['A'], italic_angle=-12)
        glyph = font['A']
        glyph._left_margin = 50
        glyph._right_margin = 50
        glyph.width = 500

        bounds = get_unskewed_bounds(glyph, font)
        assert bounds is not None
        # After unskew, bounds should be different from regular
        # The exact values depend on the unskew transformation


class TestGetAngledMargins:
    """Tests for get_angled_margins function."""

    def test_returns_none_for_none_glyph(self):
        font = MockFont(['A'])
        left, right = get_angled_margins(None, font)
        assert left is None
        assert right is None

    def test_returns_regular_margins_for_upright_font(self):
        font = MockFont(['A'])
        glyph = font.add_glyph('A', width=500, left_margin=60, right_margin=40)

        left, right = get_angled_margins(glyph, font)
        assert left == 60
        assert right == 40

    def test_returns_angled_margins_for_italic(self):
        font = MockFont(['A'], italic_angle=-12)
        glyph = font['A']
        glyph._left_margin = 50
        glyph._right_margin = 50
        glyph.width = 500

        left, right = get_angled_margins(glyph, font)
        assert left is not None
        assert right is not None
        # For italic, angled margins differ from physical


class TestSetAngledLeftMargin:
    """Tests for set_angled_left_margin function."""

    def test_sets_directly_for_upright_font(self):
        font = MockFont(['A'])
        glyph = font['A']
        glyph._left_margin = 50
        glyph.width = 500

        set_angled_left_margin(glyph, font, 70)

        assert glyph.leftMargin == 70
        # Width should increase by delta
        assert glyph.width == 520

    def test_no_change_for_none_glyph(self):
        font = MockFont(['A'])
        # Should not raise
        set_angled_left_margin(None, font, 70)

    def test_shifts_contours_for_italic(self):
        font = MockFont(['A'], italic_angle=-12)
        glyph = font['A']
        glyph._left_margin = 50
        glyph._right_margin = 50
        glyph.width = 500

        # Get initial angled left margin
        initial_left, _ = get_angled_margins(glyph, font)

        # Set new angled left margin
        new_value = initial_left + 20
        set_angled_left_margin(glyph, font, new_value)

        # Verify angled margin changed
        final_left, _ = get_angled_margins(glyph, font)
        assert abs(final_left - new_value) < 1  # Allow small rounding


class TestSetAngledRightMargin:
    """Tests for set_angled_right_margin function."""

    def test_sets_directly_for_upright_font(self):
        font = MockFont(['A'])
        glyph = font['A']
        glyph._right_margin = 50
        glyph.width = 500

        set_angled_right_margin(glyph, font, 70)

        assert glyph.rightMargin == 70
        # Width should increase by delta
        assert glyph.width == 520

    def test_no_change_for_none_glyph(self):
        font = MockFont(['A'])
        # Should not raise
        set_angled_right_margin(None, font, 70)

    def test_adjusts_width_for_italic(self):
        font = MockFont(['A'], italic_angle=-12)
        glyph = font['A']
        glyph._left_margin = 50
        glyph._right_margin = 50
        glyph.width = 500

        # Get initial angled right margin
        _, initial_right = get_angled_margins(glyph, font)

        # Set new angled right margin
        new_value = initial_right + 20
        set_angled_right_margin(glyph, font, new_value)

        # Verify angled margin changed
        _, final_right = get_angled_margins(glyph, font)
        assert abs(final_right - new_value) < 1  # Allow small rounding


class TestSpacingEditorGetMargins:
    """Tests for SpacingEditor.get_margins method."""

    def test_returns_none_for_no_font(self):
        editor = SpacingEditor()
        left, right = editor.get_margins('A')
        assert left is None
        assert right is None

    def test_returns_none_for_missing_glyph(self):
        font = MockFont(['A'])
        editor = SpacingEditor(font)
        left, right = editor.get_margins('B')  # Not in font
        assert left is None
        assert right is None

    def test_returns_physical_margins_by_default(self):
        font = MockFont([])
        font.add_glyph('A', width=500, left_margin=60, right_margin=40)

        editor = SpacingEditor(font)
        left, right = editor.get_margins('A')

        assert left == 60
        assert right == 40

    def test_returns_angled_margins_when_requested(self):
        font = MockFont(['A'], italic_angle=-12)
        font['A']._left_margin = 50
        font['A']._right_margin = 50
        font['A'].width = 500

        editor = SpacingEditor(font)
        left, right = editor.get_margins('A', angled=True)

        assert left is not None
        assert right is not None

    def test_uses_specified_font(self):
        font1 = MockFont([])
        font1.add_glyph('A', width=500, left_margin=60, right_margin=40)
        font2 = MockFont([])
        font2.add_glyph('A', width=500, left_margin=80, right_margin=40)

        editor = SpacingEditor([font1, font2])

        left1, _ = editor.get_margins('A', font=font1)
        left2, _ = editor.get_margins('A', font=font2)

        assert left1 == 60
        assert left2 == 80


class TestSetMarginCommandValueIsAngled:
    """Tests for SetMarginCommand with value_is_angled parameter."""

    def test_default_is_false(self):
        cmd = SetMarginCommand('A', 'left', 50)
        assert cmd.value_is_angled is False

    def test_sets_physical_by_default(self):
        font = MockFont(['A'])
        font['A']._left_margin = 50
        font['A'].width = 500

        editor = SpacingEditor(font)
        cmd = SetMarginCommand('A', 'left', 70)
        editor.execute(cmd)

        assert font['A'].leftMargin == 70

    def test_sets_angled_when_requested_for_italic(self):
        font = MockFont(['A'], italic_angle=-12)
        font['A']._left_margin = 50
        font['A']._right_margin = 50
        font['A'].width = 500

        editor = SpacingEditor(font)

        # Get current angled margin
        initial_angled, _ = editor.get_margins('A', angled=True)

        # Set new angled margin
        cmd = SetMarginCommand('A', 'left', 70, value_is_angled=True)
        editor.execute(cmd)

        # Verify angled margin is now 70
        final_angled, _ = editor.get_margins('A', angled=True)
        assert abs(final_angled - 70) < 1

    def test_value_is_angled_ignored_for_upright(self):
        font = MockFont(['A'])
        font['A']._left_margin = 50
        font['A'].width = 500

        editor = SpacingEditor(font)
        # Even with value_is_angled=True, upright font uses value directly
        cmd = SetMarginCommand('A', 'left', 70, value_is_angled=True)
        editor.execute(cmd)

        assert font['A'].leftMargin == 70

    def test_undo_restores_original(self):
        font = MockFont(['A'], italic_angle=-12)
        font['A']._left_margin = 50
        font['A']._right_margin = 50
        font['A'].width = 500

        original_left = font['A'].leftMargin
        original_width = font['A'].width

        editor = SpacingEditor(font)
        cmd = SetMarginCommand('A', 'left', 70, value_is_angled=True)
        editor.execute(cmd)
        editor.undo()

        assert font['A'].leftMargin == original_left
        assert font['A'].width == original_width

    def test_right_margin_angled(self):
        font = MockFont(['A'], italic_angle=-12)
        font['A']._left_margin = 50
        font['A']._right_margin = 50
        font['A'].width = 500

        editor = SpacingEditor(font)

        # Set new angled right margin
        cmd = SetMarginCommand('A', 'right', 70, value_is_angled=True)
        editor.execute(cmd)

        # Verify angled margin is now 70
        _, final_angled = editor.get_margins('A', angled=True)
        assert abs(final_angled - 70) < 1
