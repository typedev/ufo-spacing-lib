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
    """

    def __init__(self, base_glyph: str, offset: tuple[int, int] = (0, 0)):
        """
        Initialize a mock component.

        Args:
            base_glyph: Name of the base glyph.
            offset: Initial (x, y) offset.
        """
        self.baseGlyph = base_glyph
        self.offset = offset

    def moveBy(self, delta: tuple[int, int]):
        """
        Move the component by a delta.

        Args:
            delta: (dx, dy) to add to offset.
        """
        self.offset = (
            self.offset[0] + delta[0],
            self.offset[1] + delta[1]
        )


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
        self.width = width
        self._left_margin = left_margin
        self._right_margin = right_margin
        self.components: list[MockComponent] = []
        self._changed = False

    @property
    def leftMargin(self) -> int | None:
        """Get left margin."""
        return self._left_margin

    @leftMargin.setter
    def leftMargin(self, value: int | None):
        """Set left margin, adjusting width accordingly."""
        if self._left_margin is not None and value is not None:
            delta = value - self._left_margin
            self.width += delta
        self._left_margin = value

    @property
    def rightMargin(self) -> int | None:
        """Get right margin."""
        return self._right_margin

    @rightMargin.setter
    def rightMargin(self, value: int | None):
        """Set right margin, adjusting width accordingly."""
        if self._right_margin is not None and value is not None:
            delta = value - self._right_margin
            self.width += delta
        self._right_margin = value

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


class MockFont:
    """
    Mock font object that simulates RoboFont font behavior.

    Provides all the interfaces needed for kerning and margins
    operations without depending on any font editor.

    Attributes:
        groups: MockGroups dictionary.
        kerning: MockKerning dictionary.
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
        create_glyphs: bool = True
    ):
        """
        Initialize a mock font.

        Args:
            glyph_names: List of glyph names to include.
            create_glyphs: If True, create MockGlyph objects for each name.
        """
        self.groups = MockGroups()
        self.kerning = MockKerning()
        self.glyphOrder = glyph_names or []
        self._glyphs: dict[str, MockGlyph] = {}
        self._reverse_component_map: dict[str, list[str]] = {}

        if create_glyphs and glyph_names:
            for name in glyph_names:
                self._glyphs[name] = MockGlyph(name)

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

