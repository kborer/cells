"""Built-in presentation styles over the shared simulation.

Styles are trusted Python code, explicitly registered here, not loaded from
arbitrary command-line module paths. Rendering must not mutate the world.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Protocol

from .frame import Frame
from .render import render
from .world import World


@dataclass(frozen=True)
class RenderOptions:
    """Resolved output capabilities, not requests from the command line.

    The session resolves Unicode and background-tint support; snapshots use
    the ASCII, glyph-only defaults. Styles must honor these fallbacks.
    """

    unicode: bool = False
    fill: bool = False


class PresentationStyle(Protocol):
    """Read a world and return a fresh, terminal-sized frame.

    No updates, RNG consumption, input handling, terminal writes, or UI overlays.
    Any future caches must be bounded and independent of simulation state.
    """

    name: str

    def render(self, world: World, options: RenderOptions) -> Frame: ...


@dataclass(frozen=True)
class ClassicStyle:
    """The original glyph presentation, including optional body tints."""

    name: str = "classic"

    def render(self, world: World, options: RenderOptions) -> Frame:
        return render(world, unicode=options.unicode, fill=options.fill)


STYLES: Mapping[str, PresentationStyle] = MappingProxyType({"classic": ClassicStyle()})
DEFAULT_STYLE = "classic"


def get_style(name: str = DEFAULT_STYLE) -> PresentationStyle:
    """Resolve a built-in style; unknown names raise ValueError."""
    try:
        return STYLES[name]
    except KeyError:
        raise ValueError(f"Unknown presentation style: {name}") from None
