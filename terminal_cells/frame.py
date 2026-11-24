"""Shared terminal frame, semantic colors, and grid drawing primitives.

Presentation styles produce these frames; terminal output consumes them.
This module does not depend on a presentation style or simulation world.
"""

from dataclasses import dataclass
from enum import Enum

from .viewport import CURRENT


class Ink(Enum):
    DEBRIS = 1
    RED = 2
    RED_DIM = 3
    CYTOPLASM = 4
    MEMBRANE = 5
    NUCLEUS = 6
    BACTERIA = 7
    VESICLE = 8
    TEXT = 9
    MUTED = 10
    COCCUS = 11
    SPIRAL = 12
    SPINDLE = 13
    DNA = 14
    CAPTURE = 15
    MITOCHONDRION = 16
    RETICULUM = 17
    NUCLEOLUS = 18
    MICROBIAL_DNA = 19
    PHAGE = 20
    VIRAL_DNA = 21
    LYSIS = 22
    BACILLUS = 23
    SPIROCHETE = 24
    VIBRIO = 25
    COLONY = 26
    YEAST = 27
    TRYPANOSOME = 28
    FUNGUS = 29
    NEUTROPHIL = 30
    NUTRIENT = 31
    ROTIFER = 32
    NET = 33
    GLASS = 34
    BACKGROUND_FAR = 35
    BACKGROUND_NEAR = 36
    # Background tints for filled bodies: glyphs keep their ink and draw on top.
    FILL_CYTOPLASM = 37
    FILL_NEUTROPHIL = 38
    FILL_NUCLEUS = 39
    FILL_RED = 40
    FILL_RED_PALE = 41
    COMPLEMENT = 42


# Entity hues retain their meaning across colored themes. Internal anatomy and
# transient effects may share a family; outside-cell silhouettes have distinct inks.
_DARK = [
    (239, 0),
    (196, 1),
    (88, 1),
    (23, 6),
    (115, 2),
    (141, 5),
    (222, 3),
    (108, 2),
    (252, 7),
    (244, 7),
    (81, 6),
    (213, 5),
    (75, 4),
    (183, 5),
    (231, 7),
    (173, 1),
    (66, 6),
    (225, 7),
    (250, 7),
    (154, 2),
    (121, 2),
    (231, 7),
    (208, 3),
    (165, 5),
    (44, 6),
    (69, 4),
    (180, 3),
    (230, 7),
    (100, 3),
    (153, 4),
    (65, 2),
    (216, 1),
    (189, 5),
    (246, 7),
    (236, 7),
    (240, 7),
    (235, 0),
    (236, 0),
    (53, 0),
    (52, 0),
    (234, 0),
    (159, 6),
]
_LIGHT = [
    (250, 7),
    (160, 1),
    (124, 1),
    (152, 6),
    (29, 2),
    (90, 5),
    (94, 3),
    (28, 2),
    (16, 0),
    (242, 0),
    (25, 6),
    (126, 5),
    (24, 4),
    (55, 5),
    (16, 0),
    (166, 1),
    (30, 6),
    (54, 5),
    (237, 0),
    (64, 2),
    (22, 2),
    (16, 0),
    (166, 3),
    (91, 5),
    (30, 6),
    (20, 4),
    (137, 3),
    (235, 0),
    (58, 3),
    (67, 4),
    (65, 2),
    (167, 1),
    (97, 5),
    (242, 0),
    (249, 0),
    (245, 0),
    (254, 7),
    (255, 7),
    (189, 7),
    (224, 7),
    (255, 7),
    (31, 6),
]
_AMBER = list(_DARK)
_AMBER[Ink.CYTOPLASM.value - 1] = (58, 3)
_AMBER[Ink.TEXT.value - 1] = (230, 7)
_AMBER[Ink.MUTED.value - 1] = (137, 3)
_AMBER[Ink.FILL_CYTOPLASM.value - 1] = (234, 0)
PALETTES = {"slide": _DARK, "amber": _AMBER, "light": _LIGHT, "mono": [(244, 7)] * len(Ink)}
FILL_INKS = (
    Ink.FILL_CYTOPLASM,
    Ink.FILL_NEUTROPHIL,
    Ink.FILL_NUCLEUS,
    Ink.FILL_RED,
    Ink.FILL_RED_PALE,
)


@dataclass(frozen=True)
class Pixel:
    char: str = " "
    ink: Ink = Ink.DEBRIS
    bold: bool = False
    # Optional background tint; None keeps the terminal background.
    bg: Ink | None = None
    # Optional xterm-256 colors for bounded-palette raster frames. Semantic ink
    # remains available for inspection, effect classification, and fallbacks.
    color: int | None = None
    background: int | None = None


EMPTY = Pixel()
KEEP = object()


class Frame:
    """A character grid. With ``fill``, bodies also carry background tints.

    Fill mode pairs a background color with a foreground glyph in each cell:
    cell bodies become solid tinted shapes and membranes, organelles, and
    microbes are drawn as glyphs on top, instead of texture characters
    standing in for the interior.
    """

    def __init__(self, columns: int, rows: int, fill: bool = False):
        self.grid = CURRENT.get()
        self.width, self.height = columns, rows
        self.fill = fill
        self.pixels = [[EMPTY for _ in range(columns)] for _ in range(rows)]

    @classmethod
    def from_world(cls, world, fill=False):
        grid = CURRENT.get()
        return cls(
            grid.columns or round(world.width), grid.rows or round(world.height / grid.aspect), fill
        )

    def put(self, x: int, y: int, char: str, ink: Ink, bold: bool = False, bg=KEEP) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            if bg is KEEP:
                # Glyphs drawn over a filled body stay inside it.
                bg = self.pixels[y][x].bg
            self.pixels[y][x] = Pixel(char, ink, bold, bg if self.fill else None)

    def indexed(
        self,
        x: int,
        y: int,
        char: str,
        color: int,
        background: int,
        ink: Ink = Ink.DEBRIS,
        bold: bool = False,
    ) -> None:
        """Paint an indexed-color tile; styles must negotiate 256-color support."""
        if not self.fill:
            raise ValueError("Indexed tiles require background support")
        if not (
            isinstance(color, int)
            and isinstance(background, int)
            and 0 <= color <= 255
            and 0 <= background <= 255
        ):
            raise ValueError("Indexed colors must be integers in 0..255")
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[y][x] = Pixel(char, ink, bold, None, color, background)

    def point(self, x: float, y: float, char: str, ink: Ink, bold: bool = False) -> None:
        self.put(*self.grid.point(x, y), char, ink, bold)

    def text(
        self, x: int, y: int, text: str, ink: Ink = Ink.TEXT, bold: bool = False, bg=None
    ) -> None:
        # Captions default to the plain background so they read over any body.
        for offset, char in enumerate(text):
            self.put(x + offset, y, char, ink, bold, bg)

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        ink: Ink,
        unicode: bool = False,
        bg=KEEP,
    ) -> None:
        dx, dy = x2 - x1, y2 - y1
        if abs(dy) < abs(dx) * 0.45:
            char = "─" if unicode else "-"
        elif abs(dx) < abs(dy) * 0.3:
            char = "│" if unicode else "|"
        else:
            char = "\\" if dx * dy > 0 else "/"
        for col, row in line_pixels(x1, y1, x2, y2, grid=self.grid):
            self.put(col, row, char, ink, bg=bg)

    def plain(self) -> str:
        return "\n".join("".join(p.char for p in row) for row in self.pixels)


def line_pixels(x1: float, y1: float, x2: float, y2: float, *, grid=None):
    # Rasterize in character coordinates: subpixel sampling can thicken
    # diagonal strokes into staircases of adjacent slashes.
    grid = CURRENT.get() if grid is None else grid
    x, y = grid.point(x1, y1)
    end_x, end_y = grid.point(x2, y2)
    width, height = abs(end_x - x), abs(end_y - y)
    sx, sy = 1 if x < end_x else -1, 1 if y < end_y else -1
    error = width - height
    while True:
        yield x, y
        if (x, y) == (end_x, end_y):
            break
        twice = 2 * error
        if twice > -height:
            error -= height
            x += sx
        if twice < width:
            error += width
            y += sy
