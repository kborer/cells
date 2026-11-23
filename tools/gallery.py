#!/usr/bin/env python3
"""Compare registered presentation styles on staged, reproducible specimens."""

import argparse
from html import escape
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from terminal_cells.capabilities import RenderCapabilities  # noqa: E402
from terminal_cells.frame import Ink, PALETTES  # noqa: E402
from terminal_cells.scenes import SCENES, make_scene  # noqa: E402
from terminal_cells.styles import STYLES, RenderOptions, get_style  # noqa: E402
from terminal_cells.style_checks import check_style  # noqa: E402
from tools.preview import xterm_hex  # noqa: E402


def svg(panels, theme):
    """An SVG with actual background tints, suitable for comparing --fill too."""
    width = max(frame.width for _, frame in panels) * 9 + 32
    height = sum(frame.height * 18 + 48 for _, frame in panels) + 16
    background = "#ffffff" if theme == "light" else "#10171d"
    colors = {ink: xterm_hex(value[0]) for ink, value in zip(Ink, PALETTES[theme])}
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        "<title>Cells presentation comparison</title>",
        f'<rect width="100%" height="100%" fill="{background}"/>',
        '<g font-family="DejaVu Sans Mono,monospace" font-size="14" xml:space="preserve">',
    ]
    offset = 16
    for label, frame in panels:
        text = "#222222" if theme == "light" else "#dddddd"
        lines.append(f'<text x="16" y="{offset + 16}" fill="{text}">{escape(label)}</text>')
        offset += 36
        for y, row in enumerate(frame.pixels):
            for x, pixel in enumerate(row):
                px, py = 16 + x * 9, offset + y * 18
                if pixel.bg is not None:
                    lines.append(
                        f'<rect x="{px}" y="{py - 14}" width="9" height="18" fill="{colors[pixel.bg]}"/>'
                    )
                if pixel.char != " ":
                    bold = ' font-weight="bold"' if pixel.bold else ""
                    lines.append(
                        f'<text x="{px}" y="{py}" fill="{colors[pixel.ink]}"{bold}>{escape(pixel.char)}</text>'
                    )
        offset += frame.height * 18 + 12
    return "\n".join(lines + ["</g></svg>", ""])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", choices=SCENES, default="division")
    parser.add_argument(
        "--style",
        choices=tuple(STYLES),
        action="append",
        help="repeat to compare; defaults to all styles",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--at", type=float, help="simulated seconds, 0..60; defaults to scene sample times"
    )
    parser.add_argument("--ascii", action="store_true")
    parser.add_argument("--fill", action="store_true")
    parser.add_argument("--theme", choices=PALETTES, default="slide")
    parser.add_argument(
        "--output", type=Path, help=".svg or plain .txt output; default prints plain text"
    )
    args = parser.parse_args(argv)
    if args.output and args.output.suffix not in (".svg", ".txt"):
        parser.error("--output must end in .svg or .txt")
    plain = args.output is None or args.output.suffix == ".txt"
    caps = RenderCapabilities(
        unicode=not (args.ascii or plain),
        colors=0 if plain or args.theme == "mono" else 256,
        backgrounds=not plain and args.theme != "mono",
        blocks=not (args.ascii or plain),
        color_pairs=256 if not plain and args.theme != "mono" else 0,
        theme=args.theme,
    )
    options = RenderOptions.resolve(caps, fill=args.fill)
    panels = []
    for at in SCENES[args.scene].times if args.at is None else (args.at,):
        for name in args.style or STYLES:
            try:
                world = make_scene(args.scene, seed=args.seed, at=at)
            except ValueError as error:
                parser.error(str(error))
            frame = check_style(get_style(name), world, options)
            label = f"{args.scene} / {name} / seed {args.seed} / {world.time:.3f}s / {frame.width}x{frame.height}"
            panels.append((label, frame))
    content = (
        "\n\n".join(label + "\n" + frame.plain() for label, frame in panels) + "\n"
        if plain
        else svg(panels, args.theme)
    )
    if args.output:
        args.output.write_text(content)
    else:
        print(content, end="")


if __name__ == "__main__":
    main()
