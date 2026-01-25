"""
Mock Objects for Testing.

This module provides mock implementations of font objects that can be
used for testing without depending on RoboFont or other font editors.

Classes:
    MockKerning: Dict-like kerning storage
    MockGroups: Dict-like groups storage
    MockComponent: Mock glyph component
    MockGlyph: Mock glyph with margins and components
    MockFont: Complete mock font implementation

Example:
    >>> font = MockFont(['A', 'Aacute', 'V'])
    >>> font.kerning[('A', 'V')] = -50
    >>> font.groups['public.kern1.A'] = ('A', 'Aacute')
"""



class MockKerning(dict):
    """
    Mock kerning dictionary that behaves like RoboFont's kerning.

    Extends dict with a remove() method for compatibility.

    Example:
        >>> kerning = MockKerning()
        >>> kerning[('A', 'V')] = -50
        >>> kerning.remove(('A', 'V'))
    """

    def remove(self, pair: tuple[str, str]):
        """
        Remove a kerning pair.

        Args:
            pair: The (left, right) pair to remove.
        """
        if pair in self:
            del self[pair]


class MockGroups(dict):
    """
    Mock groups dictionary that behaves like RoboFont's groups.

    Extends dict with a remove() method for compatibility.

    Example:
        >>> groups = MockGroups()
        >>> groups['public.kern1.A'] = ('A', 'Aacute')
        >>> groups.remove('public.kern1.A')
    """

    def remove(self, group_name: str):
        """
        Remove a group.

        Args:
            group_name: Name of the group to remove.
        """
        if group_name in self:
            del self[group_name]


class MockComponent:
    """
    Mock glyph component.

    Simulates a component reference in a composite glyph.

    Attributes:
        baseGlyph: Name of the base glyph this component references.
        offset: (x, y) offset of the component.
        transformation: 6-tuple transformation matrix (defcon-compatible).
    """

    def __init__(
        self,
        base_glyph: str,
        transformation: tuple[float, float, float, float, float, float] = (
            1, 0, 0, 1, 0, 0
        ),
    ):
        """
        Initialize a mock component.

        Args:
            base_glyph: Name of the base glyph.
            transformation: 6-tuple (xx, xy, yx, yy, dx, dy).
        """
        self.baseGlyph = base_glyph
        self.transformation = transformation

    @property
    def offset(self) -> tuple[int, int]:
        """Get offset from transformation matrix."""
        return (int(self.transformation[4]), int(self.transformation[5]))

    @offset.setter
    def offset(self, value: tuple[int, int]):
        """Set offset in transformation matrix."""
        t = self.transformation
        self.transformation = (t[0], t[1], t[2], t[3], value[0], value[1])

    def moveBy(self, delta: tuple[int, int]):
        """
        Move the component by a delta.

        Args:
            delta: (dx, dy) to add to offset.
        """
        t = self.transformation
        self.transformation = (
            t[0], t[1], t[2], t[3],
            t[4] + delta[0],
            t[5] + delta[1],
        )


class MockContour:
    """
    Mock glyph contour.

    Simulates a contour for testing moveBy operations.

    Attributes:
        points: List of (x, y) points.
    """

    def __init__(self, points: list[tuple[float, float]] | None = None):
        """
        Initialize mock contour.

        Args:
            points: List of (x, y) coordinate tuples.
        """
        self.points = points or []

    def moveBy(self, delta: tuple[float, float]):
        """
        Move all points by delta.

        Args:
            delta: (dx, dy) movement.
        """
        dx, dy = delta
        self.points = [(x + dx, y + dy) for x, y in self.points]


class MockAnchor:
    """
    Mock glyph anchor.

    Attributes:
        x: X coordinate.
        y: Y coordinate.
        name: Anchor name.
    """

    def __init__(self, x: float, y: float, name: str = "top"):
        self.x = x
        self.y = y
        self.name = name


class MockGuideline:
    """
    Mock glyph guideline.

    Attributes:
        x: X coordinate (or None for horizontal).
        y: Y coordinate (or None for vertical).
    """

    def __init__(self, x: float | None = None, y: float | None = None):
        self.x = x
        self.y = y


class MockGlyph:
    """
    Mock glyph with margins, width, and components.

    Simulates a glyph object for testing margins operations.

    Attributes:
        name: Glyph name.
        leftMargin: Left sidebearing (None for empty glyphs).
        rightMargin: Right sidebearing (None for empty glyphs).
        width: Total advance width.
        components: List of MockComponent objects.
        contours: List of MockContour objects.
        anchors: List of MockAnchor objects.
        guidelines: List of MockGuideline objects.
    """

    def __init__(
        self,
        name: str,
        width: int = 500,
        left_margin: int | None = 50,
        right_margin: int | None = 50
    ):
        """
        Initialize a mock glyph.

        Args:
            name: Glyph name.
            width: Advance width.
            left_margin: Left sidebearing (None for empty).
            right_margin: Right sidebearing (None for empty).
        """
        self.name = name
        self._width = width
        self._left_margin = left_margin
        self._right_margin = right_margin
        self.components: list[MockComponent] = []
        self.contours: list[MockContour] = []
        self.anchors: list[MockAnchor] = []
        self.guidelines: list[MockGuideline] = []
        self._changed = False
        self._font = None  # Reference to parent font
        self._content_offset_x = 0  # Track horizontal shift of content
        self._desired_right_margin = right_margin  # Track desired right margin
        self._recalc_on_width = False  # Flag for recalc during initial setup
        # Store initial content bounds (xMin, xMax) for accurate margin simulation
        if left_margin is not None and right_margin is not None:
            self._content_xmin = left_margin
            self._content_xmax = width - right_margin
        else:
            self._content_xmin = None
            self._content_xmax = None

    @property
    def width(self) -> int:
        """Get glyph width."""
        return self._width

    @width.setter
    def width(self, value: int):
        """Set glyph width, updating content bounds if needed."""
        self._width = value
        # Recalculate content_xmax only during initial setup sequence
        if self._recalc_on_width and self._content_xmin is not None:
            if self._desired_right_margin is not None:
                self._content_xmax = value - self._desired_right_margin - self._content_offset_x
            self._recalc_on_width = False

    @property
    def leftMargin(self) -> int | None:
        """Get left margin (xMin of content)."""
        if self._content_xmin is None:
            return self._left_margin
        return self._content_xmin + self._content_offset_x

    @leftMargin.setter
    def leftMargin(self, value: int | None):
        """Set left margin by shifting content."""
        if self._content_xmin is None:
            self._left_margin = value
            # Initialize content bounds if setting for first time
            if value is not None and self._right_margin is not None:
                self._content_xmin = value
                self._content_xmax = self._width - self._right_margin
            return
        current = self._content_xmin + self._content_offset_x
        if value is not None:
            delta = value - current
            self._content_offset_x += delta
            self._width += delta

    @property
    def rightMargin(self) -> int | None:
        """Get right margin (width - xMax of content)."""
        if self._content_xmax is None:
            return self._right_margin
        xMax = self._content_xmax + self._content_offset_x
        return self.width - xMax

    @rightMargin.setter
    def rightMargin(self, value: int | None):
        """Set right margin by adjusting width."""
        self._desired_right_margin = value
        self._recalc_on_width = True  # Trigger recalc on next width change
        if self._content_xmax is None:
            if self._right_margin is not None and value is not None:
                delta = value - self._right_margin
                self._width += delta
            self._right_margin = value
            # Initialize content bounds if setting for first time
            if value is not None and self._left_margin is not None:
                self._content_xmin = self._left_margin
                self._content_xmax = self._width - value
            return
        xMax = self._content_xmax + self._content_offset_x
        if value is not None:
            self._width = xMax + value

    def moveBy(self, delta: tuple[int, int]):
        """
        Move the glyph by a delta.

        Args:
            delta: (dx, dy) movement.
        """
        # In a real glyph this would move contours
        pass

    def changed(self):
        """Mark the glyph as changed."""
        self._changed = True

    @property
    def bounds(self) -> tuple[int, int, int, int] | None:
        """
        Get glyph bounding box.

        For pure composites (no own contours), returns None.
        For glyphs with contours, returns bounds based on content box.

        Returns:
            (xMin, yMin, xMax, yMax) or None for empty/composite glyphs.
        """
        # Pure composite - no own bounds (use component bounds)
        if self.components and not getattr(self, '_has_contours_flag', False):
            return None

        if self._content_xmin is None:
            return None

        # Use stored content bounds with offset from moveBy operations
        # This simulates real glyph behavior where bounds come from contours
        xMin = self._content_xmin + self._content_offset_x
        xMax = self._content_xmax + self._content_offset_x
        return (xMin, 0, xMax, 700)

    def set_has_contours(self, value: bool = True):
        """Mark glyph as having its own contours (mixed composite)."""
        self._has_contours_flag = value

    def __iter__(self):
        """Iterate over contours."""
        # Return mock contours that update _content_offset_x when moved
        return iter(self._get_mock_contours())

    def _get_mock_contours(self):
        """Get mock contours that track movement."""
        glyph = self

        class TrackingContour:
            def moveBy(inner_self, delta):
                glyph._content_offset_x += delta[0]

        # Return at least one contour for iteration
        if self._left_margin is not None:
            return [TrackingContour()]
        return []

    def draw(self, pen):
        """
        Draw glyph outline to pen.

        For testing italic margins, this draws a simple rectangle
        based on bounds.

        Args:
            pen: A pen object (e.g., BoundsPen wrapped in TransformPen).
        """
        bounds = self.bounds
        if bounds is None:
            return

        xMin, yMin, xMax, yMax = bounds

        # Draw a simple rectangle
        pen.moveTo((xMin, yMin))
        pen.lineTo((xMin, yMax))
        pen.lineTo((xMax, yMax))
        pen.lineTo((xMax, yMin))
        pen.closePath()

    def addComponent(
        self,
        base_glyph: str,
        transformation: tuple[float, float, float, float, float, float] = (
            1, 0, 0, 1, 0, 0
        ),
    ):
        """
        Add a component to this glyph.

        Args:
            base_glyph: Name of the base glyph.
            transformation: 6-tuple transformation matrix.
        """
        component = MockComponent(base_glyph, transformation)
        self.components.append(component)


class MockLib(dict):
    """
    Mock lib dictionary that behaves like RoboFont's font.lib.

    Extends dict for UFO lib storage compatibility.

    Example:
        >>> lib = MockLib()
        >>> lib['com.typedev.spacing.metricsRules'] = {'version': 1, 'rules': {}}
    """

    pass


class MockFontInfo:
    """
    Mock font info object.

    Simulates font.info with italicAngle and other attributes.

    Attributes:
        italicAngle: Italic angle in degrees (negative for right-leaning).
        unitsPerEm: Units per em (default 1000).
    """

    def __init__(self, italic_angle: float | None = None):
        """
        Initialize mock font info.

        Args:
            italic_angle: Italic angle in degrees (negative = right lean).
        """
        self.italicAngle = italic_angle
        self.unitsPerEm = 1000


class MockFont:
    """
    Mock font object that simulates RoboFont font behavior.

    Provides all the interfaces needed for kerning and margins
    operations without depending on any font editor.

    Attributes:
        groups: MockGroups dictionary.
        kerning: MockKerning dictionary.
        lib: MockLib dictionary for UFO lib storage.
        glyphOrder: List of glyph names in order.

    Example:
        >>> font = MockFont(['A', 'Aacute', 'V', 'T'])
        >>> font.kerning[('A', 'V')] = -50
        >>> font.groups['public.kern1.A'] = ('A', 'Aacute')
        >>>
        >>> # Access glyphs
        >>> glyph = font['A']
        >>> glyph.leftMargin = 60
    """

    def __init__(
        self,
        glyph_names: list[str] | None = None,
        create_glyphs: bool = True,
        italic_angle: float | None = None,
    ):
        """
        Initialize a mock font.

        Args:
            glyph_names: List of glyph names to include.
            create_glyphs: If True, create MockGlyph objects for each name.
            italic_angle: Italic angle in degrees (negative = right lean).
        """
        self.groups = MockGroups()
        self.kerning = MockKerning()
        self.lib = MockLib()
        self.info = MockFontInfo(italic_angle)
        self.glyphOrder = glyph_names or []
        self._glyphs: dict[str, MockGlyph] = {}
        self._reverse_component_map: dict[str, list[str]] = {}

        if create_glyphs and glyph_names:
            for name in glyph_names:
                glyph = MockGlyph(name)
                glyph._font = self
                self._glyphs[name] = glyph

    def __contains__(self, glyph_name: str) -> bool:
        """Check if glyph exists in font."""
        return glyph_name in self._glyphs or glyph_name in self.glyphOrder

    def __getitem__(self, glyph_name: str) -> MockGlyph:
        """
        Get a glyph by name.

        Args:
            glyph_name: Name of the glyph.

        Returns:
            MockGlyph object.

        Raises:
            KeyError: If glyph doesn't exist.
        """
        if glyph_name not in self._glyphs:
            if glyph_name in self.glyphOrder:
                self._glyphs[glyph_name] = MockGlyph(glyph_name)
            else:
                raise KeyError(f"Glyph '{glyph_name}' not in font")
        return self._glyphs[glyph_name]

    def keys(self) -> list[str]:
        """Get list of glyph names."""
        return self.glyphOrder.copy()

    def __iter__(self):
        """Iterate over glyphs in font."""
        for name in self.glyphOrder:
            yield self[name]

    def __len__(self) -> int:
        """Return number of glyphs."""
        return len(self.glyphOrder)

    def add_glyph(
        self,
        name: str,
        width: int = 500,
        left_margin: int = 50,
        right_margin: int = 50
    ) -> MockGlyph:
        """
        Add a glyph to the font.

        Args:
            name: Glyph name.
            width: Advance width.
            left_margin: Left sidebearing.
            right_margin: Right sidebearing.

        Returns:
            The created MockGlyph.
        """
        glyph = MockGlyph(name, width, left_margin, right_margin)
        glyph._font = self
        self._glyphs[name] = glyph
        if name not in self.glyphOrder:
            self.glyphOrder.append(name)
        return glyph

    def add_composite(
        self,
        name: str,
        base_glyph: str,
        offset: tuple[int, int] = (0, 0)
    ) -> MockGlyph:
        """
        Add a composite glyph to the font.

        Args:
            name: Name of the composite glyph.
            base_glyph: Name of the base glyph.
            offset: Component offset.

        Returns:
            The created MockGlyph with component.
        """
        if base_glyph in self._glyphs:
            base = self._glyphs[base_glyph]
            glyph = MockGlyph(
                name,
                width=base.width,
                left_margin=base.leftMargin,
                right_margin=base.rightMargin
            )
        else:
            glyph = MockGlyph(name)

        component = MockComponent(base_glyph, offset)
        glyph.components.append(component)

        self._glyphs[name] = glyph
        if name not in self.glyphOrder:
            self.glyphOrder.append(name)

        # Update reverse mapping
        if base_glyph not in self._reverse_component_map:
            self._reverse_component_map[base_glyph] = []
        self._reverse_component_map[base_glyph].append(name)

        return glyph

    def getReverseComponentMapping(self) -> dict[str, list[str]]:
        """
        Get reverse component mapping.

        Returns:
            Dict mapping base glyph names to lists of composite names.
        """
        return self._reverse_component_map.copy()

    def setReverseComponentMapping(self, mapping: dict[str, list[str]]) -> None:
        """
        Set reverse component mapping (for testing).

        Args:
            mapping: Dict mapping base glyph names to lists of composite names.
        """
        self._reverse_component_map = mapping.copy()


def create_test_font() -> MockFont:
    """
    Create a standard test font with common glyphs.

    Returns:
        MockFont with A, Aacute, Agrave, V, T, W glyphs.

    Example:
        >>> font = create_test_font()
        >>> 'A' in font  # True
    """
    return MockFont([
        'A', 'Aacute', 'Agrave', 'Adieresis',
        'V', 'T', 'W', 'Y',
        'a', 'v', 't', 'w',
        'space'
    ])


def create_test_font_with_kerning() -> MockFont:
    """
    Create a test font with pre-configured kerning and groups.

    Returns:
        MockFont with groups and kerning set up.

    Example:
        >>> font = create_test_font_with_kerning()
        >>> font.kerning[('public.kern1.A', 'V')]  # -50
    """
    font = create_test_font()

    # Set up groups
    font.groups['public.kern1.A'] = ('A', 'Aacute', 'Agrave')
    font.groups['public.kern2.V'] = ('V',)

    # Set up kerning
    font.kerning[('public.kern1.A', 'V')] = -50
    font.kerning[('public.kern1.A', 'T')] = -40
    font.kerning[('A', 'W')] = -30  # Exception

    return font

