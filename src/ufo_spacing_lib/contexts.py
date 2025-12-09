"""
Font Context Module.

This module provides the FontContext class which encapsulates all information
needed to perform kerning and margins operations across one or multiple fonts.

The context abstraction allows the same commands to work with:
- Single font operations
- Linked/interpolated font operations (multiple masters)
- Scaled operations (for interpolation-aware adjustments)

Example:
    Single font operation:

    >>> context = FontContext.from_single_font(my_font)
    >>> command.execute(context)

    Multi-font with scaling:

    >>> context = FontContext.from_linked_fonts(
    ...     fonts=[light_font, bold_font],
    ...     primary=light_font,
    ...     scales={light_font: 1.0, bold_font: 1.2}
    ... )
    >>> command.execute(context)  # Applies to both with scaling
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FontContext:
    """
    Context for font operations.

    Encapsulates all information needed to perform kerning or margins
    operations, including support for multi-font (linked/interpolated)
    operations with optional per-font scaling.

    This abstraction allows commands to be font-editor agnostic - the same
    command code works whether operating on a single font or multiple
    linked fonts with different scales.

    Attributes:
        fonts: List of font objects to operate on. All fonts in this list
            will receive the operation when a command is executed.
        primary_font: The main font used for lookups (e.g., resolving
            kerning pairs to groups). If not specified, defaults to the
            first font in the fonts list.
        scales: Optional dictionary mapping fonts to scale factors.
            Used for interpolation-aware operations where different
            masters need proportionally different values.
            Default scale is 1.0 for fonts not in this dict.

    Example:
        Basic single font context:

        >>> ctx = FontContext(fonts=[font], primary_font=font)
        >>> for f in ctx:
        ...     print(f.path)

        Multi-font with scaling:

        >>> ctx = FontContext(
        ...     fonts=[light, regular, bold],
        ...     primary_font=regular,
        ...     scales={light: 0.8, regular: 1.0, bold: 1.3}
        ... )
        >>> ctx.get_scale(bold)  # Returns 1.3

    Note:
        The font objects are not typed explicitly to maintain
        framework independence. Any object with kerning and groups
        dict-like attributes will work.
    """

    fonts: list[Any]
    primary_font: Any = None
    scales: dict[Any, float] = field(default_factory=dict)

    def __post_init__(self):
        """Set primary_font to first font if not specified."""
        if self.primary_font is None and self.fonts:
            self.primary_font = self.fonts[0]

    def __iter__(self) -> Iterator[Any]:
        """
        Iterate over all fonts in the context.

        Yields:
            Font objects in the context.

        Example:
            >>> for font in context:
            ...     font.kerning[pair] = value
        """
        return iter(self.fonts)

    def __len__(self) -> int:
        """
        Return the number of fonts in the context.

        Returns:
            Number of fonts.
        """
        return len(self.fonts)

    def __bool__(self) -> bool:
        """
        Check if context has any fonts.

        Returns:
            True if context contains at least one font.
        """
        return len(self.fonts) > 0

    def get_scale(self, font: Any) -> float:
        """
        Get the scale factor for a specific font.

        Args:
            font: The font object to get scale for.

        Returns:
            Scale factor for the font. Returns 1.0 if font is not
            in the scales dictionary.

        Example:
            >>> context = FontContext(
            ...     fonts=[light, bold],
            ...     scales={bold: 1.5}
            ... )
            >>> context.get_scale(light)  # 1.0 (default)
            >>> context.get_scale(bold)   # 1.5
        """
        return self.scales.get(font, 1.0)

    def scale_value(self, font: Any, value: int) -> int:
        """
        Scale a value for a specific font.

        Applies the font's scale factor to the value and rounds
        to the nearest integer.

        Args:
            font: The font object to scale for.
            value: The base value to scale.

        Returns:
            Scaled and rounded value.

        Example:
            >>> context.scale_value(bold_font, 10)  # Returns 15 if scale is 1.5
        """
        return round(value * self.get_scale(font))

    @classmethod
    def from_single_font(cls, font: Any, scale: float = 1.0) -> FontContext:
        """
        Create a context for a single font operation.

        Convenience factory method for the common case of operating
        on just one font.

        Args:
            font: The font object to operate on.
            scale: Optional scale factor (default 1.0).

        Returns:
            FontContext configured for single font operation.

        Example:
            >>> context = FontContext.from_single_font(current_font)
            >>> editor.execute(command, context)
        """
        scales = {font: scale} if scale != 1.0 else {}
        return cls(fonts=[font], primary_font=font, scales=scales)

    @classmethod
    def from_linked_fonts(
        cls,
        fonts: list[Any],
        primary: Any = None,
        scales: dict[Any, float] | None = None
    ) -> FontContext:
        """
        Create a context for linked/interpolated font operations.

        Use this when an operation should apply to multiple fonts
        simultaneously, such as when editing masters in an
        interpolation family.

        Args:
            fonts: List of font objects to operate on.
            primary: The primary font for lookups. If None, uses
                the first font in the list.
            scales: Optional dictionary of scale factors per font.
                Fonts not in this dict get scale 1.0.

        Returns:
            FontContext configured for multi-font operation.

        Example:
            >>> context = FontContext.from_linked_fonts(
            ...     fonts=[light_master, bold_master],
            ...     primary=light_master,
            ...     scales={light_master: 1.0, bold_master: 1.2}
            ... )
        """
        return cls(
            fonts=fonts,
            primary_font=primary or (fonts[0] if fonts else None),
            scales=scales or {}
        )

    def with_scale(self, font: Any, scale: float) -> FontContext:
        """
        Create a new context with an updated scale for a font.

        This method does not modify the original context.

        Args:
            font: The font to set scale for.
            scale: The new scale value.

        Returns:
            New FontContext with updated scale.

        Example:
            >>> new_ctx = context.with_scale(bold_font, 1.5)
        """
        new_scales = self.scales.copy()
        new_scales[font] = scale
        return FontContext(
            fonts=self.fonts.copy(),
            primary_font=self.primary_font,
            scales=new_scales
        )

