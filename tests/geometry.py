"""
Geometric mock glyphs for planner tests.

Unlike `mocks.MockGlyph`, which simulates margins, these glyphs have real
outlines: margins and bounds are computed from contour points and from
components drawn through their full transformation, resolved in the glyph
source. A source has no `lib` and no `getReverseComponentMapping` unless
asked, which proves the planner needs neither.
"""

from __future__ import annotations

from typing import Any

Transformation = tuple[float, float, float, float, float, float]


def _apply(t: Transformation, x: float, y: float) -> tuple[float, float]:
    xx, xy, yx, yy, dx, dy = t
    return (xx * x + yx * y + dx, xy * x + yy * y + dy)


class GContour:
    def __init__(self, points: list[tuple[float, float]]):
        self.points = list(points)

    def moveBy(self, delta: tuple[float, float]) -> None:
        dx, dy = delta
        self.points = [(x + dx, y + dy) for x, y in self.points]


class GComponent:
    def __init__(self, base: str, transformation: Transformation):
        self.baseGlyph = base
        self.transformation = tuple(float(v) for v in transformation)

    @property
    def offset(self) -> tuple[float, float]:
        return (self.transformation[4], self.transformation[5])

    def moveBy(self, delta: tuple[float, float]) -> None:
        t = self.transformation
        self.transformation = (t[0], t[1], t[2], t[3], t[4] + delta[0], t[5] + delta[1])


class GAnchor:
    def __init__(self, name: str, x: float, y: float):
        self.name = name
        self.x = x
        self.y = y


class GGuideline:
    def __init__(self, x: float | None, y: float | None):
        self.x = x
        self.y = y


class GGlyph:
    def __init__(self, source: GSource, name: str, width: float = 0):
        self._source = source
        self.name = name
        self.width = width
        self.contours: list[GContour] = []
        self.components: list[GComponent] = []
        self.anchors: list[GAnchor] = []
        self.guidelines: list[GGuideline] = []
        self.lib: dict[str, Any] = {}
        self.changed_count = 0

    # -- building ------------------------------------------------------------

    def rect(self, x0: float, y0: float, x1: float, y1: float) -> GGlyph:
        self.contours.append(GContour([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]))
        return self

    def component(
        self,
        base: str,
        offset: tuple[float, float] = (0, 0),
        matrix: tuple[float, float, float, float] = (1, 0, 0, 1),
    ) -> GGlyph:
        self.components.append(GComponent(base, (*matrix, *offset)))
        return self

    def anchor(self, name: str, x: float, y: float) -> GGlyph:
        self.anchors.append(GAnchor(name, x, y))
        return self

    # -- geometry ------------------------------------------------------------

    def points(self, _depth: int = 0) -> list[tuple[float, float]]:
        """Every outline point as drawn, components resolved."""
        if _depth > 50:
            raise RecursionError(self.name)
        result = [p for contour in self.contours for p in contour.points]
        for component in self.components:
            if component.baseGlyph not in self._source:
                continue
            base = self._source[component.baseGlyph]
            result.extend(
                _apply(component.transformation, x, y)
                for x, y in base.points(_depth + 1)
            )
        return result

    @property
    def bounds(self) -> tuple[float, float, float, float] | None:
        pts = self.points()
        if not pts:
            return None
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (min(xs), min(ys), max(xs), max(ys))

    @property
    def leftMargin(self) -> float | None:
        b = self.bounds
        return None if b is None else b[0]

    @leftMargin.setter
    def leftMargin(self, value: float) -> None:
        b = self.bounds
        if b is None:
            return
        d = value - b[0]
        self.moveBy((d, 0))
        self.width += d

    @property
    def rightMargin(self) -> float | None:
        b = self.bounds
        return None if b is None else self.width - b[2]

    @rightMargin.setter
    def rightMargin(self, value: float) -> None:
        b = self.bounds
        if b is None:
            return
        self.width = b[2] + value

    def moveBy(self, delta: tuple[float, float]) -> None:
        dx, dy = delta
        for contour in self.contours:
            contour.moveBy(delta)
        for component in self.components:
            component.moveBy(delta)
        for anchor in self.anchors:
            anchor.x += dx
            anchor.y += dy
        for guideline in self.guidelines:
            if guideline.x is not None:
                guideline.x += dx

    def changed(self) -> None:
        self.changed_count += 1

    def draw(self, pen: Any) -> None:
        for contour in self.contours:
            pen.moveTo(contour.points[0])
            for p in contour.points[1:]:
                pen.lineTo(p)
            pen.closePath()
        for component in self.components:
            pen.addComponent(component.baseGlyph, component.transformation)

    # -- comparison ----------------------------------------------------------

    def drawing(self) -> list[tuple[float, float]]:
        """Rounded drawn points, for pixel-for-pixel comparisons."""
        return sorted((round(x, 6), round(y, 6)) for x, y in self.points())


class GSource:
    """A glyph source: `name in source`, `source[name]`, iteration, keys()."""

    def __init__(self, with_reverse_mapping: bool = False):
        self._glyphs: dict[str, GGlyph] = {}
        if with_reverse_mapping:
            self.getReverseComponentMapping = self._reverse_mapping

    def new(self, name: str, width: float = 0) -> GGlyph:
        glyph = GGlyph(self, name, width)
        self._glyphs[name] = glyph
        return glyph

    def __contains__(self, name: object) -> bool:
        return name in self._glyphs

    def __getitem__(self, name: str) -> GGlyph:
        return self._glyphs[name]

    def __iter__(self):
        return iter(self._glyphs.values())

    def keys(self) -> list[str]:
        return list(self._glyphs)

    def _reverse_mapping(self) -> dict[str, set[str]]:
        result: dict[str, set[str]] = {}
        for glyph in self._glyphs.values():
            for component in glyph.components:
                result.setdefault(component.baseGlyph, set()).add(glyph.name)
        return result

    def state(self) -> dict[str, Any]:
        """Full snapshot of every glyph, for exact undo comparisons."""
        return {
            name: (
                round(g.width, 9),
                [[(round(x, 9), round(y, 9)) for x, y in c.points] for c in g.contours],
                [(c.baseGlyph, tuple(round(v, 9) for v in c.transformation))
                 for c in g.components],
                [(a.name, round(a.x, 9), round(a.y, 9)) for a in g.anchors],
            )
            for name, g in self._glyphs.items()
        }


def accent_font() -> GSource:
    """A, acute, Aacute (A + acute), Aring/Aringacute nest, H, DZ."""
    s = GSource()
    s.new("A", 600).rect(50, 0, 550, 700)
    s.new("acute", 0).rect(-50, 750, 50, 850)
    s.new("ring", 0).rect(-60, 720, 60, 880)
    s.new("H", 700).rect(80, 0, 620, 700)
    s.new("D", 650).rect(90, 0, 600, 700)
    s.new("Z", 600).rect(40, 0, 560, 700)
    s.new("Aacute", 600).component("A").component("acute", (300, 0)).anchor(
        "top", 300, 900
    )
    s.new("Aring", 600).component("A").component("ring", (300, 0))
    s.new("Aringacute", 600).component("Aring").component("acute", (300, 200))
    s.new("DZ", 1250).component("D").component("Z", (650, 0))
    return s
