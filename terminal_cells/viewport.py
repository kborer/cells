"""Specimen-to-terminal projection, scoped to one pure presentation call.

World units never change with magnification. A frame retains its projection so
later tool overlays use the same coordinates; the context is always restored.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import math
from types import MappingProxyType

from .models import ASPECT


MAGNIFICATIONS = MappingProxyType({"overview": 0.5, "normal": 1.0, "detail": 3.0})


@dataclass(frozen=True)
class Grid:
    scale: float = 1.0
    left: float = 0.0
    top: float = 0.0
    columns: int | None = None
    rows: int | None = None
    aspect: float = ASPECT

    def __post_init__(self):
        if (
            not all(math.isfinite(v) for v in (self.scale, self.left, self.top, self.aspect))
            or self.scale <= 0
            or self.aspect <= 0
        ):
            raise ValueError("Projection must have a finite positive scale and finite origin")

    def column(self, x):
        return (x - self.left) * self.scale

    def row(self, y):
        return (y - self.top) * self.scale / self.aspect

    def point(self, x, y):
        return round(self.column(x)), round(self.row(y))

    def world(self, col, row):
        return col / self.scale + self.left, row * self.aspect / self.scale + self.top

    def snap(self, x, y):
        return self.world(*self.point(x, y))


CURRENT = ContextVar("cells_grid", default=Grid())


@contextmanager
def projection(grid):
    token = CURRENT.set(grid)
    try:
        yield grid
    finally:
        CURRENT.reset(token)


@dataclass
class Camera:
    columns: int
    rows: int
    magnification: str = "normal"
    x: float | None = None
    y: float | None = None

    @property
    def scale(self):
        return MAGNIFICATIONS[self.magnification]

    def simulation_size(self):
        # An overview starts with a wider specimen, rather than empty margins.
        scale = min(1, self.scale)
        return max(1, round(self.columns / scale)), max(1, round(self.rows / scale))

    def focus(self, world):
        """Start a detail view on a bacterium; panning remains under user control."""
        if self.magnification == "detail" and world.bacteria:
            free = [b for b in world.bacteria.values() if b.owner is None and b.entry is None]
            if free:
                obj = min(
                    free, key=lambda b: math.hypot(b.x - world.width / 2, b.y - world.height / 2)
                )
                self.x, self.y = obj.x, obj.y
                self.pan(world, 0, 0)

    def pan(self, world, dx, dy):
        x = self.x if self.x is not None else world.width / 2
        y = self.y if self.y is not None else world.height / 2
        half_x, half_y = self.columns / self.scale / 2, self.rows * ASPECT / self.scale / 2
        self.x = min(max(half_x, x + dx * 4 / self.scale), max(half_x, world.width - half_x))
        self.y = min(max(half_y, y + dy * 8 / self.scale), max(half_y, world.height - half_y))

    def grid(self, world):
        # Normal remains pixel-for-pixel compatible with the original viewport.
        x = self.x if self.x is not None else world.width / 2
        y = self.y if self.y is not None else world.height / 2
        return Grid(
            self.scale,
            x - self.columns / self.scale / 2,
            y - self.rows * ASPECT / self.scale / 2,
            self.columns,
            self.rows,
        )

    def render(self, style, world, options):
        with projection(self.grid(world)):
            return style.render(world, options)
