"""Built-in presentation styles over the shared simulation.

Styles are trusted Python code, explicitly registered here, not loaded from
arbitrary command-line module paths. Rendering must not mutate the world.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Protocol

from .frame import Frame, Ink, PALETTES
from .capabilities import RenderCapabilities
from .render import render
from .world import World
from . import stained, raster


@dataclass(frozen=True)
class RenderOptions:
    """Resolved output capabilities, not requests from the command line.

    The session resolves Unicode and background-tint support; snapshots use
    the ASCII, glyph-only defaults. Styles must honor these fallbacks.
    """

    unicode: bool = False
    fill: bool = False
    capabilities: RenderCapabilities | None = None

    @classmethod
    def resolve(cls, capabilities: RenderCapabilities, *, fill: bool = False):
        """Negotiate requested effects against actual output capabilities."""
        return cls(capabilities.unicode, fill and capabilities.backgrounds, capabilities)

    def __post_init__(self):
        if self.capabilities is not None:
            if self.unicode and not self.capabilities.unicode:
                raise ValueError("Unicode is unavailable for this output")
            if self.fill and not self.capabilities.backgrounds:
                raise ValueError("Background tints are unavailable for this output")


class PresentationStyle(Protocol):
    """Read a world and return a fresh, terminal-sized frame.

    No updates, RNG consumption, input handling, terminal writes, or UI overlays.
    Any future caches must be bounded and independent of simulation state.
    """

    name: str
    legend: tuple | None
    default_fill: bool

    def palette(self, theme: str): ...

    def cache_info(self) -> Mapping[str, "CacheInfo"]: ...

    def render(self, world: World, options: RenderOptions) -> Frame: ...


@dataclass(frozen=True)
class CacheInfo:
    """A style reports all retained drawing caches for contract checks."""

    size: int
    limit: int


@dataclass(frozen=True)
class ClassicStyle:
    """The original glyph presentation, including optional body tints."""

    legend: tuple | None = None
    name: str = "classic"
    default_fill: bool = False

    def palette(self, theme: str):
        return PALETTES[theme]

    def cache_info(self) -> Mapping[str, CacheInfo]:
        return {}

    def render(self, world: World, options: RenderOptions) -> Frame:
        return render(world, unicode=options.unicode, fill=options.fill)


@dataclass(frozen=True)
class StainedStyle:
    """Experimental stained bodies and quarter-cell contours."""

    legend: tuple | None = None
    name: str = "stained"
    default_fill: bool = True

    def palette(self, theme: str):
        return stained.palette(theme)

    def cache_info(self) -> Mapping[str, CacheInfo]:
        return {}

    def render(self, world: World, options: RenderOptions) -> Frame:
        return stained.render(world, options)


@dataclass(frozen=True)
class RasterStyle:
    """Shaded, whole-specimen raster with a bounded pigment palette."""

    legend: tuple | None = (
        ("Raster: shaded specimen on a pale slide", Ink.TEXT),
        ("Immune cells: pale gray, purple nuclei", Ink.TEXT),
        ("Red blood cells: pink annulus, pale center", Ink.TEXT),
        ("Microbes and fungal filaments: green; shapes identify kinds", Ink.TEXT),
        ("Phages: small purple heads and gray tails", Ink.TEXT),
        ("Complement: gray surface marks and pores", Ink.TEXT),
        ("Rare visitors and tools share the simulation", Ink.MUTED),
    )
    name: str = "raster"
    default_fill: bool = True

    def palette(self, theme: str):
        return PALETTES[theme]

    def cache_info(self) -> Mapping[str, CacheInfo]:
        info = raster.tile.cache_info()
        return {"tiles": CacheInfo(info.currsize, info.maxsize)}

    def render(self, world: World, options: RenderOptions) -> Frame:
        return raster.render(world, options)


STYLES: Mapping[str, PresentationStyle] = MappingProxyType(
    {
        "classic": ClassicStyle(),
        "stained": StainedStyle(),
        "raster": RasterStyle(),
    }
)
DEFAULT_STYLE = "classic"


def get_style(name: str = DEFAULT_STYLE) -> PresentationStyle:
    """Resolve a built-in style; unknown names raise ValueError."""
    try:
        return STYLES[name]
    except KeyError:
        raise ValueError(f"Unknown presentation style: {name}") from None
