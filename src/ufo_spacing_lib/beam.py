"""
Beam Measurement.

Margins measured along a horizontal line at a height ("beam"), as Glyphs.app
does for metrics keys with ``@height`` (``=d@200+5``).

The outline is drawn (components resolved through the glyph source) and
crossed with the line at ``y``. In an italic font the measurement follows
the slant:

- left = first crossing - y * slant
- right = width - (last crossing - y * slant)
- slant = -tan(italicAngle), 0 for upright

Correct rather than fast: every segment is intersected exactly, curves with
fontTools. Needs fontTools.
"""

from __future__ import annotations

import math
from functools import cache
from typing import Any


def slant_for_angle(italic_angle: float | None) -> float:
    """Slant factor for an italicAngle: -tan(angle), 0 for upright."""
    if not italic_angle:
        return 0.0
    return -math.tan(math.radians(italic_angle))


@cache
def _crossing_pen_class() -> type:
    """The pen class, built on first use so fontTools stays optional."""
    from fontTools.misc.bezierTools import curveLineIntersections
    from fontTools.pens.basePen import BasePen

    class _CrossingPen(BasePen):
        """Collects the x coordinates where the outline crosses y = height."""

        def __init__(self, glyph_set: Any, height: float):
            super().__init__(glyph_set)
            self.height = height
            self.xs: list[float] = []
            self._start: tuple[float, float] | None = None

        def _moveTo(self, pt):
            self._start = pt

        def _lineTo(self, pt):
            self._line(self._getCurrentPoint(), pt)

        def _curveToOne(self, pt1, pt2, pt3):
            self._cubic(self._getCurrentPoint(), pt1, pt2, pt3)

        def _qCurveToOne(self, pt1, pt2):
            # Exact quadratic -> cubic elevation
            pt0 = self._getCurrentPoint()
            c1 = (pt0[0] + 2 / 3 * (pt1[0] - pt0[0]), pt0[1] + 2 / 3 * (pt1[1] - pt0[1]))
            c2 = (pt2[0] + 2 / 3 * (pt1[0] - pt2[0]), pt2[1] + 2 / 3 * (pt1[1] - pt2[1]))
            self._cubic(pt0, c1, c2, pt2)

        def _closePath(self):
            current = self._getCurrentPoint()
            if self._start is not None and current != self._start:
                self._line(current, self._start)
            self._start = None

        def _endPath(self):
            self._start = None

        def _line(self, p0, p1):
            y = self.height
            (x0, y0), (x1, y1) = p0, p1
            if y0 == y1:
                if y0 == y:
                    self.xs.extend((x0, x1))
                return
            if min(y0, y1) <= y <= max(y0, y1):
                t = (y - y0) / (y1 - y0)
                self.xs.append(x0 + t * (x1 - x0))

        def _cubic(self, p0, p1, p2, p3):
            y = self.height
            ys = (p0[1], p1[1], p2[1], p3[1])
            if y < min(ys) or y > max(ys):
                return
            for p in (p0, p3):
                if p[1] == y:
                    self.xs.append(p[0])
            xs = (p0[0], p1[0], p2[0], p3[0])
            line = ((min(xs) - 1, y), (max(xs) + 1, y))
            for hit in curveLineIntersections((p0, p1, p2, p3), line):
                self.xs.append(hit.pt[0])

    return _CrossingPen


def beam_crossings(glyph: Any, height: float, source: Any) -> list[float]:
    """Sorted x coordinates where the drawn outline crosses y = height."""
    pen = _crossing_pen_class()(source, height)
    glyph.draw(pen)
    return sorted(pen.xs)


def beam_margins(
    glyph: Any, height: float, source: Any, slant: float = 0.0
) -> tuple[float | None, float | None]:
    """
    Left and right margins of a glyph measured at a height.

    Args:
        glyph: Glyph with ``draw(pen)`` and ``width``.
        height: The y of the beam.
        source: Glyph source used to resolve components.
        slant: -tan(italicAngle); 0 for upright.

    Returns:
        ``(left, right)``, or ``(None, None)`` when the beam misses the
        outline.
    """
    xs = beam_crossings(glyph, height, source)
    if not xs:
        return None, None
    offset = height * slant
    left = xs[0] - offset
    right = glyph.width - (xs[-1] - offset)
    return float(left), float(right)
