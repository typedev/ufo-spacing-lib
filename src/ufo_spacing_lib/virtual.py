"""
Virtual Font Module.

Provides VirtualFont class for preview/simulation of font changes
without modifying the actual font data.

The VirtualFont wraps native Python data structures (dicts) for kerning
and groups while maintaining a reference to a source font for glyph access.
This allows previewing kerning/group changes with live glyph data.

Example:
    >>> from ufo_spacing_lib import VirtualFont, FontContext, AdjustKerningCommand
    >>>
    >>> # Create virtual font from existing font
    >>> virtual = VirtualFont.from_font(font)
    >>>
    >>> # Make changes - only affects virtual.kerning/groups
    >>> context = FontContext.from_single_font(virtual)
    >>> cmd = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
    >>> editor.execute(cmd, context)
    >>>
    >>> # Original font unchanged, changes in virtual.kerning
    >>> print(virtual.kerning[('A', 'V')])  # Modified value
    >>> print(font.kerning[('A', 'V')])     # Original value

    >>> # Apply changes to real font when ready
    >>> virtual.apply_to(font)
"""

from __future__ import annotations

from typing import Any


class VirtualKerning(dict):
    """
    Dict subclass for kerning that mimics font.kerning interface.

    Extends dict with remove() method for RoboFont compatibility.
    """

    def remove(self, pair: tuple[str, str]):
        """Remove a kerning pair if it exists."""
        if pair in self:
            del self[pair]


class VirtualGroups(dict):
    """
    Dict subclass for groups that mimics font.groups interface.

    Extends dict with remove() method for RoboFont compatibility.
    """

    def remove(self, group_name: str):
        """Remove a group if it exists."""
        if group_name in self:
            del self[group_name]


class VirtualFont:
    """
    Font-like wrapper for preview/simulation with isolated kerning and groups.

    VirtualFont provides the same interface as a real font object, but uses
    isolated copies of kerning and groups data. Changes to kerning/groups
    only affect the virtual data, not the source font.

    Glyph access is delegated to the source font, so glyph shapes, margins,
    and other properties remain live - any changes to the source font's
    glyphs are immediately visible through VirtualFont.

    Attributes:
        kerning: VirtualKerning dict with isolated kerning data.
        groups: VirtualGroups dict with isolated groups data.
        source: Reference to source font (for glyph access), or None.

    Example:
        Creating from existing font:

        >>> virtual = VirtualFont.from_font(font)
        >>> virtual.kerning[('A', 'V')] = -100  # Doesn't affect font
        >>> font.kerning[('A', 'V')]  # Still original value

        Creating with custom data:

        >>> virtual = VirtualFont(
        ...     kerning={('A', 'V'): -50},
        ...     groups={'public.kern1.A': ('A', 'Aacute')},
        ...     source=font
        ... )

        Checking differences:

        >>> diff = virtual.get_kerning_diff()
        >>> for pair, (old, new) in diff.items():
        ...     print(f"{pair}: {old} -> {new}")
    """

    def __init__(
        self,
        kerning: dict[tuple[str, str], int] | None = None,
        groups: dict[str, tuple[str, ...]] | None = None,
        source: Any = None,
    ):
        """
        Initialize a VirtualFont.

        Args:
            kerning: Initial kerning data. If None, empty dict is used.
            groups: Initial groups data. If None, empty dict is used.
            source: Source font for glyph access. If None, glyph access
                will raise KeyError.
        """
        self.kerning = VirtualKerning(kerning or {})
        self.groups = VirtualGroups(groups or {})
        self.source = source

        # Store original data for diff tracking
        self._original_kerning: dict[tuple[str, str], int] = dict(kerning or {})
        self._original_groups: dict[str, tuple[str, ...]] = dict(groups or {})

    def __getitem__(self, glyph_name: str) -> Any:
        """
        Get a glyph by name from the source font.

        Args:
            glyph_name: Name of the glyph.

        Returns:
            Glyph object from source font.

        Raises:
            KeyError: If no source font or glyph doesn't exist.
        """
        if self.source is None:
            raise KeyError(f"No source font, cannot access glyph '{glyph_name}'")
        return self.source[glyph_name]

    def __contains__(self, glyph_name: str) -> bool:
        """Check if glyph exists in source font."""
        if self.source is None:
            return False
        return glyph_name in self.source

    def keys(self) -> list[str]:
        """Get list of glyph names from source font."""
        if self.source is None:
            return []
        return self.source.keys()

    @property
    def glyphOrder(self) -> list[str]:
        """Get glyph order from source font."""
        if self.source is None:
            return []
        return getattr(self.source, 'glyphOrder', self.keys())

    def getReverseComponentMapping(self) -> dict[str, list[str]]:
        """Get reverse component mapping from source font."""
        if self.source is None:
            return {}
        if hasattr(self.source, 'getReverseComponentMapping'):
            return self.source.getReverseComponentMapping()
        return {}

    @classmethod
    def from_font(cls, font: Any, deep_copy: bool = True) -> VirtualFont:
        """
        Create a VirtualFont from an existing font.

        Creates isolated copies of kerning and groups data while
        maintaining a reference to the font for glyph access.

        Args:
            font: Source font to create virtual copy from.
            deep_copy: If True (default), creates deep copies of groups
                tuples. If False, shares tuple references (faster but
                modifying tuples would affect both).

        Returns:
            VirtualFont with copied kerning/groups and reference to font.

        Example:
            >>> virtual = VirtualFont.from_font(font)
            >>> # Modify virtual kerning
            >>> virtual.kerning[('A', 'V')] = -100
            >>> # Original font unchanged
            >>> print(font.kerning.get(('A', 'V')))
        """
        kerning_copy = dict(font.kerning)

        if deep_copy:
            groups_copy = {
                name: tuple(glyphs) for name, glyphs in font.groups.items()
            }
        else:
            groups_copy = dict(font.groups)

        return cls(kerning=kerning_copy, groups=groups_copy, source=font)

    @classmethod
    def empty(cls, source: Any = None) -> VirtualFont:
        """
        Create an empty VirtualFont.

        Args:
            source: Optional source font for glyph access.

        Returns:
            VirtualFont with empty kerning and groups.
        """
        return cls(kerning={}, groups={}, source=source)

    def get_kerning_diff(self) -> dict[tuple[str, str], tuple[int | None, int | None]]:
        """
        Get differences between current and original kerning.

        Returns:
            Dict mapping pairs to (original_value, new_value) tuples.
            Only includes pairs that changed.

        Example:
            >>> diff = virtual.get_kerning_diff()
            >>> for pair, (old, new) in diff.items():
            ...     if old is None:
            ...         print(f"Added: {pair} = {new}")
            ...     elif new is None:
            ...         print(f"Removed: {pair} (was {old})")
            ...     else:
            ...         print(f"Changed: {pair}: {old} -> {new}")
        """
        diff: dict[tuple[str, str], tuple[int | None, int | None]] = {}

        # Check for modified and removed pairs
        for pair, old_value in self._original_kerning.items():
            new_value = self.kerning.get(pair)
            if new_value != old_value:
                diff[pair] = (old_value, new_value)

        # Check for added pairs
        for pair, new_value in self.kerning.items():
            if pair not in self._original_kerning:
                diff[pair] = (None, new_value)

        return diff

    def get_groups_diff(self) -> dict[str, tuple[tuple | None, tuple | None]]:
        """
        Get differences between current and original groups.

        Returns:
            Dict mapping group names to (original_members, new_members) tuples.
            Only includes groups that changed.
        """
        diff: dict[str, tuple[tuple | None, tuple | None]] = {}

        # Check for modified and removed groups
        for name, old_members in self._original_groups.items():
            new_members = self.groups.get(name)
            if new_members != old_members:
                diff[name] = (old_members, new_members)

        # Check for added groups
        for name, new_members in self.groups.items():
            if name not in self._original_groups:
                diff[name] = (None, new_members)

        return diff

    def has_changes(self) -> bool:
        """Check if there are any changes to kerning or groups."""
        return bool(self.get_kerning_diff()) or bool(self.get_groups_diff())

    def apply_to(self, font: Any, kerning: bool = True, groups: bool = True):
        """
        Apply virtual changes to a real font.

        Args:
            font: Target font to apply changes to.
            kerning: If True, apply kerning changes.
            groups: If True, apply groups changes.

        Example:
            >>> virtual = VirtualFont.from_font(font)
            >>> # Make changes to virtual...
            >>> virtual.kerning[('A', 'V')] = -100
            >>> # Apply when ready
            >>> virtual.apply_to(font)
        """
        if kerning:
            kerning_diff = self.get_kerning_diff()
            for pair, (old_value, new_value) in kerning_diff.items():
                if new_value is None:
                    # Pair was removed
                    if pair in font.kerning:
                        del font.kerning[pair]
                else:
                    # Pair was added or modified
                    font.kerning[pair] = new_value

        if groups:
            groups_diff = self.get_groups_diff()
            for name, (old_members, new_members) in groups_diff.items():
                if new_members is None:
                    # Group was removed
                    if name in font.groups:
                        del font.groups[name]
                else:
                    # Group was added or modified
                    font.groups[name] = new_members

    def reset(self):
        """Reset kerning and groups to original state."""
        self.kerning = VirtualKerning(self._original_kerning)
        self.groups = VirtualGroups(self._original_groups)

    def reset_kerning(self):
        """Reset only kerning to original state."""
        self.kerning = VirtualKerning(self._original_kerning)

    def reset_groups(self):
        """Reset only groups to original state."""
        self.groups = VirtualGroups(self._original_groups)

    def __repr__(self) -> str:
        """Return string representation."""
        source_info = type(self.source).__name__ if self.source else "None"
        return (
            f"VirtualFont(kerning={len(self.kerning)} pairs, "
            f"groups={len(self.groups)}, source={source_info})"
        )
