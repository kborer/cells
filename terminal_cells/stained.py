"""Experimental stained-specimen presentation using the shared simulation.

Quarter-cell coverage and anchored stain, with classic anatomy and effects
composited above it. The world and all drawing randomness remain untouched.
"""

from collections import Counter
import math

from .frame import FILL_INKS, Ink, PALETTES
from .geometry import nuclear_bodies
from .models import disc_axes, nucleus_radii
from .render import render as classic_render

# Bits are upper-left, upper-right, lower-left, lower-right. A full tile uses
# its background tint; partial tiles combine foreground/background colors.
BLOCKS = (" ", "▘", "▝", "▀", "▖", "▌", "▞", "▛", "▗", "▚", "▐", "▜", "▄", "▙", "▟", " ")
SAMPLES = ((-0.25, -0.5), (0.25, -0.5), (-0.25, 0.5), (0.25, 0.5))
QUIET = frozenset((Ink.MEMBRANE, Ink.NEUTROPHIL, Ink.RED, Ink.RED_DIM, Ink.CYTOPLASM))


def palette(theme):
    """Keep species/effect hues; adjust only cytoplasm and stain backgrounds."""
    result = list(PALETTES[theme])
    if theme != "mono":
        light = theme == "light"
        stains = {
            Ink.FILL_CYTOPLASM: 152 if light else 23,
            Ink.FILL_NEUTROPHIL: 195 if light else 24,
            Ink.FILL_NUCLEUS: 189 if light else 54,
            Ink.FILL_RED: 217 if light else 88,
            Ink.FILL_RED_PALE: 224 if light else 131,
            Ink.CYTOPLASM: 153 if light else 30,
        }
        for ink, color in stains.items():
            result[ink.value - 1] = color, result[ink.value - 1][1]
    return result


def grain(x, y, ident):
    """Fixed local-space granules, independent of frame count and the world's RNG."""
    value = (round(x * 2) * 0x1F123BB5 ^ round(y * 2) * 0x5F356495 ^ ident * 0x45D9F3B) & 0xFFFFFFFF
    value ^= value >> 16
    value = value * 0x45D9F3B & 0xFFFFFFFF
    return (value ^ (value >> 16)) % 47


def tile(samples):
    """Quantize four semantic stain samples to a two-color block character."""
    counts = Counter(samples)
    if len(counts) == 1:
        ink = samples[0]
        return (
            (" ", Ink.TEXT, ink)
            if ink in FILL_INKS
            else ("█" if ink is not None else " ", ink or Ink.DEBRIS, None)
        )
    # Keep the slide transparent along silhouettes. With >2 stains, majority
    # colors win; a transparent minority still stays on the slide.
    ordered = counts.most_common()
    if None in counts:
        foreground = next(ink for ink, _ in ordered if ink is not None)
        background = None
        mask = sum(1 << index for index, ink in enumerate(samples) if ink is not None)
    else:
        # Keep backgrounds inside the backend's finite tint-pair budget.
        background = next((ink for ink, _ in ordered if ink in FILL_INKS), None)
        foreground = next(ink for ink, _ in ordered if ink != background)
        mask = sum(1 << index for index, ink in enumerate(samples) if ink != background)
    return BLOCKS[mask], foreground, background


def render(world, options):
    capabilities = options.capabilities
    if (
        not options.fill
        or capabilities is None
        or capabilities.colors < 256
        or not capabilities.blocks
    ):
        return classic_render(world, options.unicode, options.fill)
    frame = classic_render(world, options.unicode, fill=True)
    grid = frame.grid
    stains = {}  # Per-frame, bounded by the viewport; never retained by the style.

    def paint(x, y, rx, ry, sample):
        left, right = (
            max(0, math.floor(grid.column(x - rx) - 1)),
            min(frame.width, math.ceil(grid.column(x + rx) + 1)),
        )
        top, bottom = (
            max(0, math.floor(grid.row(y - ry) - 1)),
            min(frame.height, math.ceil(grid.row(y + ry) + 1)),
        )
        for row in range(top, bottom):
            for col in range(left, right):
                values = stains.get((col, row))
                for index, (ox, oy) in enumerate(SAMPLES):
                    wx, wy = grid.world(col, row)
                    ink = sample(wx + ox / grid.scale - x, wy + oy / grid.scale - y)
                    if ink is not None:
                        if values is None:
                            values = [None] * 4
                            stains[col, row] = values
                        values[index] = ink

    for disc in world.red_cells:
        a, b = disc_axes(disc)

        def red(dx, dy):
            distance = (dx / a) ** 2 + (dy / b) ** 2
            return None if distance > 1 else Ink.FILL_RED_PALE if distance < 0.27 else Ink.FILL_RED

        paint(disc.x, disc.y, a, b, red)

    for cell in sorted(world.cells, key=lambda c: c.radius):
        event = world.events.active
        if event is not None and event.kind == "net" and event.source == cell.id and event.age >= 2:
            continue  # Keep the canonical fading source and DNA-trap animation.
        tint = Ink.FILL_NEUTROPHIL if cell.kind == "neutrophil" else Ink.FILL_CYTOPLASM

        def cytoplasm(dx, dy):
            if math.hypot(dx, dy) > cell.outline(math.atan2(dy, dx), world.time):
                return None
            return Ink.CYTOPLASM if grain(dx, dy, cell.id) < 1 else tint

        extent = cell.extent()
        paint(cell.x, cell.y, extent, extent, cytoplasm)
        # Intact nuclear bodies use the same anchor/extent as selection. During
        # mitosis the classic staged chromosomes, envelopes and spindle remain.
        for nx, ny, radius, _ in nuclear_bodies(cell):
            cx, cy = grid.snap(nx, ny)
            rx, ry = nucleus_radii(radius)
            rx, ry = (
                max(2, round(rx * grid.scale)) / grid.scale,
                max(1, round(ry * grid.scale / grid.aspect)) * grid.aspect / grid.scale,
            )

            def nuclear(dx, dy):
                if (dx / rx) ** 2 + (dy / ry) ** 2 > 1.12:
                    return None
                return Ink.NUCLEUS if grain(dx, dy, cell.id + 101) < 4 else Ink.FILL_NUCLEUS

            paint(cx, cy, rx + 1, ry + 1, nuclear)

    for (col, row), samples in stains.items():
        pixel = frame.pixels[row][col]
        if pixel.ink in QUIET or pixel.char == " ":
            char, ink, bg = tile(samples)
            frame.put(col, row, char, ink, bg=bg)
        elif pixel.ink is Ink.NUCLEUS:
            # Mitosis remains untouched; ordinary envelopes become stained edges,
            # while local chromatin marks and the nucleolus remain recognizable.
            if pixel.char not in ("~", "x", "X") and any(s is Ink.FILL_NUCLEUS for s in samples):
                char, ink, bg = tile(samples)
                frame.put(col, row, char, ink, bg=bg)
        elif pixel.char != " ":
            # Keep organelles, cargo, flagella and transient effects in front.
            # Their canonical backgrounds already express capture ownership.
            continue
    # Round an outline can land just beyond the high-resolution silhouette.
    # Clear only those quiet outline marks; never free microbes or effects.
    for row, pixels in enumerate(frame.pixels):
        for col, pixel in enumerate(pixels):
            if pixel.ink in (Ink.MEMBRANE, Ink.NEUTROPHIL, Ink.RED) and (col, row) not in stains:
                # A NET source is deliberately still shown by classic drawing.
                event = world.events.active
                if event is None or event.kind != "net":
                    frame.put(col, row, " ", Ink.DEBRIS, bg=None)
    return frame
