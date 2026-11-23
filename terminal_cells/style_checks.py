"""Reusable, opt-in contributor checks; never run in the animation loop."""

import gc
import pickle
import weakref
import unicodedata

from .frame import Frame, Ink
from .models import ASPECT


def check_style(style, world, options):
    """Assert purity, determinism, sizing, output fallbacks, and bounded caches.

    Raises AssertionError with a useful contract violation; returns the frame for
    additional contributor assertions. Caches must report actual retained entries
    in cache_info(), including functools.lru_cache wrappers when used.
    """
    before = pickle.dumps(world)
    frame = style.render(world, options)
    assert pickle.dumps(world) == before, "Rendering changed the world or its RNG"
    assert isinstance(frame, Frame), "A style must return a shared Frame"
    assert (frame.width, frame.height) == (round(world.width), round(world.height / ASPECT)), (
        "Frame dimensions must match the specimen viewport"
    )
    assert len(frame.pixels) == frame.height, "Frame row count is inconsistent"
    for row in frame.pixels:
        assert len(row) == frame.width, "Frame column count is inconsistent"
        for pixel in row:
            assert len(pixel.char) == 1, "Each pixel must contain one terminal character"
            assert pixel.char.isprintable(), "Control glyph in frame"
            assert not unicodedata.combining(pixel.char), "Combining glyph in frame"
            assert unicodedata.east_asian_width(pixel.char) not in ("W", "F"), "Wide glyph in frame"
            assert isinstance(pixel.ink, Ink), "Foreground must be a semantic Ink"
            assert pixel.bg is None or isinstance(pixel.bg, Ink), (
                "Background must be a semantic Ink"
            )
            if not options.unicode:
                assert pixel.char.isascii(), "Style ignored ASCII fallback"
            if options.capabilities is not None and not options.capabilities.blocks:
                assert pixel.char not in "▀▁▂▃▄▅▆▇█▉▊▋▌▍▎▏▐▔▕▖▗▘▙▚▛▜▝▞▟", (
                    "Style ignored block-glyph fallback"
                )
            if not options.fill:
                assert pixel.bg is None, "Style ignored background fallback"
    saved = pickle.dumps(frame)
    repeated = style.render(world, options)
    assert repeated is not frame, "Return a fresh frame so UI overlays cannot corrupt cached output"
    assert pickle.dumps(frame) == saved, "Rendering mutated an earlier frame"
    assert repeated.pixels == frame.pixels, "Rendering is not deterministic"
    assert pickle.dumps(world) == before, "Repeated rendering changed the world or its RNG"
    for name, cache in style.cache_info().items():
        assert isinstance(cache.size, int) and isinstance(cache.limit, int), (
            f"Invalid cache: {name}"
        )
        assert cache.limit > 0 and 0 <= cache.size <= cache.limit, f"Unbounded cache: {name}"
    return frame


def check_world_retention(style, make_world, options):
    """Assert a style does not keep a strong reference to a completed specimen."""
    world = make_world()
    reference = weakref.ref(world)
    style.render(world, options)
    del world
    gc.collect()
    assert reference() is None, "Style retained a World after rendering"
