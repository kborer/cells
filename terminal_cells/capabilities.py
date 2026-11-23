"""Explicit terminal capabilities, independent of curses and presentation styles."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RenderCapabilities:
    """Resolved capabilities for this output, not terminal marketing claims.

    colors is 0 (monochrome), 8, or 256 for the current backend. True color
    needs a future backend/frame extension; COLORTERM alone does not enable it.
    blocks means block glyphs are permitted by the Unicode policy. Font coverage
    cannot be detected reliably, so --ascii always disables them.
    """

    unicode: bool = False
    colors: int = 0
    backgrounds: bool = False
    blocks: bool = False
    color_pairs: int = 0
    theme: str = "slide"

    def __post_init__(self):
        if self.colors not in (0, 8, 256):
            raise ValueError("Supported color depths are 0, 8, and 256")
        if self.color_pairs < 0:
            raise ValueError("color_pairs must be nonnegative")
        if self.blocks and not self.unicode:
            raise ValueError("Block glyphs require Unicode")
        if self.backgrounds and (self.colors < 256 or self.color_pairs == 0):
            raise ValueError("Background tints require 256 colors and available pairs")
