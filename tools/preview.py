#!/usr/bin/env python3
"""Generate the README's SVG from an actual simulation frame (stdlib only)."""

from html import escape
from pathlib import Path
import math
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cells import (
    CELL_RADIUS,
    NEUTROPHIL_RADIUS,
    BACTERIUM_PADDING,
    DIVISION_STAGES,
    MICROBE_KINDS,
    Bacterium,
    Cell,
    Frame,
    Hypha,
    Ink,
    Phage,
    PALETTES,
    State,
    World,
    draw_bacterium,
    draw_cell,
    draw_hyphae,
    render,
)


def xterm_hex(index):
    if index >= 232:
        gray = 8 + (index - 232) * 10
        return f"#{gray:02x}{gray:02x}{gray:02x}"
    levels = [0, 95, 135, 175, 215, 255]
    index -= 16
    r, g, b = levels[index // 36], levels[index // 6 % 6], levels[index % 6]
    return f"#{r:02x}{g:02x}{b:02x}"


def atlas(path, title, panels):
    panel_width = max(frame.width for _, frame in panels) * 9 + 32
    panel_height = max(frame.height for _, frame in panels) * 18 + 64
    width, height = panel_width * 4, math.ceil(len(panels) / 4) * panel_height + 48
    colors = {ink: xterm_hex(p[0]) for ink, p in zip(Ink, PALETTES["slide"])}
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        f"<title>{escape(title)}</title>",
        f'<rect width="{width}" height="{height}" rx="12" fill="#10171d"/>',
        '<g font-family="DejaVu Sans Mono,monospace" font-size="14" xml:space="preserve">',
        f'<text x="20" y="28" fill="#d0d0d0">{escape(title)}</text>',
    ]
    for index, (label, frame) in enumerate(panels):
        ox, oy = index % 4 * panel_width + 16, index // 4 * panel_height + 90
        lines.append(
            f'<text x="{ox}" y="{oy - 26}" fill="#b8c5d0" font-size="12">{escape(label)}</text>'
        )
        for y, row in enumerate(frame.pixels):
            for x, p in enumerate(row):
                if p.char != " ":
                    weight = ' font-weight="bold"' if p.bold else ""
                    lines.append(
                        f'<text x="{ox + x * 9}" y="{oy + y * 18}" '
                        f'fill="{colors[p.ink]}"{weight}>{escape(p.char)}</text>'
                    )
    lines.append("</g></svg>")
    path.write_text("\n".join(lines) + "\n")
    print(path)


def lifecycle_previews(directory):
    panels = []
    resting = Frame(48, 24)
    draw_cell(resting, Cell(0, 24, 24, CELL_RADIUS, 0, 0), 0, True)
    panels.append(("Resting nucleus", resting))
    elapsed = 0
    for label, duration in DIVISION_STAGES:
        at = elapsed + duration * (0.9 if label in ("envelope breakdown", "telophase") else 0.65)
        cell = Cell(0, 24, 24, CELL_RADIUS, 0, 0, state=State.DIVIDE, elapsed=at)
        frame = Frame(48, 24)
        draw_cell(frame, cell, at, True)
        panels.append((label.capitalize(), frame))
        elapsed += duration
    atlas(directory / "mitosis.svg", "Mitosis / a 50-second division sequence", panels)
    world = World(100, 40, 7)
    world.cells = [Cell(0, 42, 40, CELL_RADIUS, 0, 0)]
    world.bacteria = {
        99: Bacterium(99, 42 + CELL_RADIUS + BACTERIUM_PADDING, 40, 0, 0, "coccus", 9999, 9999)
    }
    world.red_cells, world.debris = [], []
    world.phages.clear()
    world.replenish_at = math.inf
    panels = []
    for at, label in [
        (0.05, "Contact"),
        (1, "Adhesion"),
        (3, "Pseudopods extend"),
        (5, "Cup surrounds microbe"),
        (6.9, "Cup seals"),
        (7.5, "Sealed phagosome"),
        (9, "Transport inward"),
        (11, "Digestion"),
    ]:
        while world.time < at:
            world.update()
        frame = render(world, True)
        cell = world.cells[0]
        left, top = round(cell.x) - 18, round(cell.y / 2) - 12
        crop = Frame(48, 24)
        for y in range(crop.height):
            for x in range(crop.width):
                if 0 <= top + y < frame.height and 0 <= left + x < frame.width:
                    crop.pixels[y][x] = frame.pixels[top + y][left + x]
        panels.append((label, crop))
    atlas(directory / "ingestion.svg", "Ingestion / hold, surround, seal, internalize", panels)


def viral_previews(directory):
    world = World(80, 40, 42)
    world.cells.clear()
    world.red_cells.clear()
    world.debris.clear()
    host = Bacterium(0, 28, 40, 0, 0, "rod", 9999, 9999)
    world.bacteria = {0: host}
    phage = Phage(0, 35.5, 40)
    world.phages = {0: phage}
    world.next_phage_id = 1
    world.current = lambda x, y: (0, 0)
    world.replenish_at = world.phage_replenish_at = math.inf

    def crop():
        frame = render(world, True)
        result = Frame(48, 24)
        for y in range(result.height):
            for x in range(result.width):
                result.pixels[y][x] = frame.pixels[y + 8][x + 4]
        return result

    panels = [("Encounter", crop())]
    world._infect(host, phage)
    for at, label in [
        (2, "Attachment"),
        (5, "Genome injection"),
        (10, "Genome replication"),
        (18, "Phage assembly"),
        (22.5, "Wall breakdown"),
        (24.3, "Lysis / release"),
        (28, "Settled progeny"),
    ]:
        while world.time + 0.001 < at:
            world.update()
        panels.append((label, crop()))
    atlas(
        directory / "phages.svg",
        "Bacteriophages / attachment, replication, assembly, lysis",
        panels,
    )


def diversity_preview(directory):
    labels = {
        "rod": "Short rod / waving flagellum",
        "coccus": "Single coccus",
        "spiral": "Short spiral",
        "bacillus": "Chain-forming bacilli",
        "spirochete": "Spirochete / whole-body corkscrew",
        "vibrio": "Vibrio / curved rod",
        "colony": "Coccal colony",
        "yeast": "Yeast / daughter bud",
        "trypanosome": "Trypanosome / undulating membrane",
    }
    panels = []
    for kind in MICROBE_KINDS:
        frame = Frame(48, 24)
        microbe = Bacterium(0, 24, 24, 0.15, 0, kind, 9999, 9999, bud=0.8 if kind == "yeast" else 0)
        draw_bacterium(frame, microbe, True, 0.5)
        panels.append((labels[kind], frame))
    for kind in ("macrophage", "neutrophil"):
        frame = Frame(48, 24)
        radius = NEUTROPHIL_RADIUS if kind == "neutrophil" else CELL_RADIUS
        draw_cell(frame, Cell(0, 24, 24, radius, 0.2, 0.3, kind=kind), 0.5, True)
        panels.append((kind.capitalize(), frame))
    world = World(48, 24, 1)
    world.cells.clear()
    world.red_cells.clear()
    world.hyphae = [
        Hypha(
            [
                (5, 33),
                (12, 29),
                (18, 24),
                (24, 21),
                (30, 17),
                (23, 29),
                (29, 33),
                (36, 35),
                (35, 14),
            ],
            [(0, 1), (1, 2), (2, 3), (3, 4), (2, 5), (5, 6), (6, 7), (4, 8)],
            [(7, 0.2), (8, -0.4)],
            9999,
        )
    ]
    frame = Frame(48, 24)
    draw_hyphae(frame, world, True)
    panels.append(("Fungal hypha / branching septate filament", frame))
    atlas(directory / "diversity.svg", "Slide inhabitants / silhouettes and anatomy", panels)


def fallback_preview(directory):
    """Each slide inhabitant drawn twice with the same state: ASCII first, Unicode second."""
    labels = {
        "rod": "Short rod / waving flagellum",
        "coccus": "Single coccus",
        "spiral": "Short spiral",
        "bacillus": "Chain-forming bacilli",
        "spirochete": "Spirochete / whole-body corkscrew",
        "vibrio": "Vibrio / curved rod",
        "colony": "Coccal colony",
        "yeast": "Yeast / daughter bud",
        "trypanosome": "Trypanosome / undulating membrane",
    }
    panels = []
    for kind in MICROBE_KINDS:
        for mode, label in ((False, "ASCII"), (True, "Unicode")):
            frame = Frame(48, 24)
            microbe = Bacterium(
                0, 24, 24, 0.15, 0, kind, 9999, 9999, bud=0.8 if kind == "yeast" else 0
            )
            draw_bacterium(frame, microbe, mode, 0.5)
            panels.append((f"{labels[kind]} ({label})", frame))
    for kind in ("macrophage", "neutrophil"):
        radius = NEUTROPHIL_RADIUS if kind == "neutrophil" else CELL_RADIUS
        for mode, label in ((False, "ASCII"), (True, "Unicode")):
            frame = Frame(48, 24)
            draw_cell(frame, Cell(0, 24, 24, radius, 0.2, 0.3, kind=kind), 0.5, mode)
            panels.append((f"{kind.capitalize()} ({label})", frame))
    world = World(48, 24, 1)
    world.cells.clear()
    world.red_cells.clear()
    world.hyphae = [
        Hypha(
            [
                (5, 33),
                (12, 29),
                (18, 24),
                (24, 21),
                (30, 17),
                (23, 29),
                (29, 33),
                (36, 35),
                (35, 14),
            ],
            [(0, 1), (1, 2), (2, 3), (3, 4), (2, 5), (5, 6), (6, 7), (4, 8)],
            [(7, 0.2), (8, -0.4)],
            9999,
        )
    ]
    for mode, label in ((False, "ASCII"), (True, "Unicode")):
        frame = Frame(48, 24)
        draw_hyphae(frame, world, mode)
        panels.append((f"Fungal hypha ({label})", frame))
    atlas(directory / "fallback.svg", "Slide inhabitants / ASCII fallback beside Unicode", panels)


def ecology_preview(directory):
    def empty():
        world = World(48, 24, 5)
        world.cells.clear()
        world.red_cells.clear()
        world.debris.clear()
        world.bacteria.clear()
        world.phages.clear()
        world.hyphae.clear()
        world.nutrients.clear()
        world.nutrient_at = world.replenish_at = world.phage_replenish_at = math.inf
        world.current = lambda x, y: (0, 0)
        return world

    world = empty()
    world._add_nutrient(30, 24, 6)
    world.nutrients[0].age = 12
    world.bacteria = {
        i: Bacterium(i, 12, y, 0, 2, kind, math.inf, math.inf)
        for i, y, kind in ((0, 16, "rod"), (1, 30, "vibrio"), (2, 37, "spirochete"))
    }
    panels = [("A nutrient patch appears", render(world, True))]
    for _ in range(300):
        world.update()
    panels.append(("Bacteria gather and feed", render(world, True)))
    world = empty()
    world.hyphae = [
        Hypha(
            [(8, 36), (16, 32), (24, 26), (32, 22), (38, 17), (33, 33), (40, 36)],
            [(0, 1), (1, 2), (2, 3), (3, 4), (2, 5), (5, 6)],
            [(4, -0.5), (6, 0.2)],
            math.inf,
        )
    ]
    world.bacteria = {
        1: Bacterium(1, 10, 36, -0.3, 2, "rod", math.inf, math.inf),
        2: Bacterium(2, 20, 29, -0.3, 2, "vibrio", math.inf, math.inf),
    }
    for _ in range(150):
        world.update()
    panels.append(("Swimmers follow fungal branches", render(world, True)))
    world = empty()
    world.cells = [Cell(0, 15, 24, 11, 0, 0, cooldown=999)]
    world.bacteria = {1: Bacterium(1, 34, 24, 0, 2.5, "vibrio", math.inf, math.inf)}
    for _ in range(24):
        world.update()
    panels.append(("A brief escape burst near an immune cell", render(world, True)))
    atlas(
        directory / "ecology.svg", "Local interactions / food, fungal highways, and escape", panels
    )


def main():
    world = World(120, 36, seed=42)
    for _ in range(180):
        world.update()
    frame = render(world, unicode=True)
    colors = {ink: xterm_hex(palette[0]) for ink, palette in zip(Ink, PALETTES["slide"])}
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="712" viewBox="0 0 1120 712">',
        "<title>cells: macrophages engulfing bacteria in a living terminal microscope slide</title>",
        '<rect width="1120" height="712" rx="12" fill="#10171d"/>',
        '<g font-family="DejaVu Sans Mono,monospace" font-size="14" xml:space="preserve">',
    ]
    for y, row in enumerate(frame.pixels):
        for x, pixel in enumerate(row):
            if pixel.char == " ":
                continue
            weight = ' font-weight="bold"' if pixel.bold else ""
            lines.append(
                f'<text x="{20 + x * 9}" y="{30 + y * 18}" '
                f'fill="{colors[pixel.ink]}"{weight}>{escape(pixel.char)}</text>'
            )
    lines.extend(
        [
            '<text x="20" y="690" fill="#808b95" font-size="12">'
            "cells  /  seed 42  /  6 seconds    ·    ? help    Space pause    q quit</text>",
            "</g></svg>",
        ]
    )
    output = Path(__file__).resolve().parents[1] / "docs" / "preview.svg"
    output.parent.mkdir(exist_ok=True)
    output.write_text("\n".join(lines) + "\n")
    print(output)
    lifecycle_previews(output.parent)
    viral_previews(output.parent)
    diversity_preview(output.parent)
    fallback_preview(output.parent)
    ecology_preview(output.parent)


if __name__ == "__main__":
    main()
