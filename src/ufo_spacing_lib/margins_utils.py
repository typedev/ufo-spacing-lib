"""
Margins Utilities.

This module provides utility functions for working with glyph margins,
including support for italic/angled margins calculation.

For italic fonts, there are two margin concepts:
- Physical margins: stored in UFO (glyph.leftMargin, glyph.rightMargin)
- Angled/visual margins: what the user sees after unskew transformation

Functions:
    - get_slant_factor: Get slant factor from font's italic angle
    - get_unskewed_bounds: Get glyph bounds after removing italic slant
    - get_angled_margins: Get visual margins for italic glyph
    - set_angled_left_margin: Set left margin in angled space
    - set_angled_right_margin: Set right margin in angled space
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


def get_italic_angle(font: Any) -> float | None:
    """
    Get italic angle from font info.

    Args:
        font: Font object with info.italicAngle attribute.

    Returns:
        Italic angle in degrees (negative for right-leaning italics),
        or None if not available.
    """
    if font is None:
        return None
    info = getattr(font, 'info', None)
    if info is None:
        return None
    return getattr(info, 'italicAngle', None)


def get_slant_factor(font: Any) -> float:
    """
    Get slant factor from font's italic angle.

    The slant factor converts Y coordinate to X offset:
    x_offset = y * slant_factor

    For right-leaning italics (negative italicAngle), slant_factor is positive.

    Args:
        font: Font object with info.italicAngle attribute.

    Returns:
        Slant factor, or 0.0 for upright fonts.
    """
    angle = get_italic_angle(font)
    if angle is None or angle == 0:
        return 0.0
    # italicAngle is negative for right-leaning italics (e.g., -12)
    # We need positive slant_factor for standard italic lean
    return -math.tan(math.radians(angle))


def get_unskewed_bounds(
    glyph: Any,
    font: Any,
) -> tuple[float, float, float, float] | None:
    """
    Get glyph bounds after removing italic slant.

    Applies unskew transformation to calculate bounds as if the glyph
    were upright.

    Args:
        glyph: Glyph object with draw() method.
        font: Font object (used as glyphSet for component resolution).

    Returns:
        Tuple of (xMin, yMin, xMax, yMax) in font units, or None if
        bounds cannot be calculated (empty glyph, etc.).
    """
    if glyph is None:
        return None

    slant_factor = get_slant_factor(font)

    # For upright fonts, return regular bounds
    if slant_factor == 0:
        bounds = getattr(glyph, 'bounds', None)
        return bounds

    try:
        from fontTools.misc.transform import Transform
        from fontTools.pens.boundsPen import BoundsPen
        from fontTools.pens.transformPen import TransformPen

        # Unskew transform: x' = x - y * slant_factor
        unskew = Transform(1, 0, -slant_factor, 1, 0, 0)

        # Use font as glyphSet for component resolution
        bounds_pen = BoundsPen(font)
        transform_pen = TransformPen(bounds_pen, unskew)
        glyph.draw(transform_pen)

        return bounds_pen.bounds

    except Exception:
        return None


def get_angled_margins(
    glyph: Any,
    font: Any,
) -> tuple[float | None, float | None]:
    """
    Get angled (visual) margins for a glyph.

    For upright fonts, returns regular margins.
    For italic fonts, calculates margins from unskewed bounds.

    Args:
        glyph: Glyph object with leftMargin, rightMargin, width attributes.
        font: Font object with info.italicAngle.

    Returns:
        Tuple of (left_margin, right_margin). Values may be None for
        empty glyphs.
    """
    if glyph is None:
        return None, None

    slant_factor = get_slant_factor(font)

    # For upright fonts, return regular margins
    if slant_factor == 0:
        return glyph.leftMargin, glyph.rightMargin

    bounds = get_unskewed_bounds(glyph, font)
    if bounds is None:
        return None, None

    xMin, yMin, xMax, yMax = bounds
    glyph_width = getattr(glyph, 'width', 0) or 0

    angled_left = xMin
    angled_right = glyph_width - xMax

    return angled_left, angled_right


def set_angled_left_margin(
    glyph: Any,
    font: Any,
    value: float,
) -> None:
    """
    Set left margin in angled (visual) space.

    For italic glyphs, shifts all contours, components, and anchors
    to achieve the desired angled left margin.

    For upright fonts, sets leftMargin directly.

    Args:
        glyph: Glyph object to modify.
        font: Font object with info.italicAngle.
        value: Desired angled left margin value.
    """
    if glyph is None:
        return

    slant_factor = get_slant_factor(font)

    # For upright fonts, set directly
    if slant_factor == 0:
        glyph.leftMargin = value
        return

    bounds = get_unskewed_bounds(glyph, font)
    if bounds is None:
        # Empty glyph - set width
        glyph.width = value
        return

    current_left = bounds[0]  # xMin after unskew
    delta = value - current_left

    if abs(delta) < 0.001:
        return  # No change needed

    # Shift all contours
    for contour in glyph:
        contour.moveBy((delta, 0))

    # Shift all components
    if hasattr(glyph, 'components'):
        for component in glyph.components:
            x, y = component.offset
            component.offset = (x + delta, y)

    # Shift all anchors
    if hasattr(glyph, 'anchors'):
        for anchor in glyph.anchors:
            anchor.x += delta

    # Shift all guidelines
    if hasattr(glyph, 'guidelines'):
        for guideline in glyph.guidelines:
            if guideline.x is not None:
                guideline.x += delta


def set_angled_right_margin(
    glyph: Any,
    font: Any,
    value: float,
) -> None:
    """
    Set right margin in angled (visual) space.

    Adjusts glyph width to achieve the desired angled right margin.

    For upright fonts, sets rightMargin directly.

    Args:
        glyph: Glyph object to modify.
        font: Font object with info.italicAngle.
        value: Desired angled right margin value.
    """
    if glyph is None:
        return

    slant_factor = get_slant_factor(font)

    # For upright fonts, set directly
    if slant_factor == 0:
        glyph.rightMargin = value
        return

    bounds = get_unskewed_bounds(glyph, font)
    if bounds is None:
        # Empty glyph - set width
        glyph.width = value
        return

    xMax = bounds[2]  # xMax after unskew
    glyph.width = xMax + value
