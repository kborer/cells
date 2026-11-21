#!/usr/bin/env python3
"""Generate an audit sheet for every semantic ink and colored theme."""

from html import escape
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from terminal_cells import Ink, PALETTES  # noqa: E402
from terminal_cells.render import FILL_INKS  # noqa: E402
from preview import xterm_hex


def main():
    width, row_height = 1020, 25
    height = 90 + len(Ink) * row_height
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<title>cells palette audit: all semantic inks</title>",
        '<rect width="1020" height="100%" fill="#10171d"/>',
        '<g font-family="DejaVu Sans Mono,monospace" font-size="14">',
    ]
    for col, theme in enumerate(("slide", "amber", "light")):
        left = col * 340
        bg, fg = ("#ffffff", "#101010") if theme == "light" else ("#10171d", "#eeeeee")
        lines += [
            f'<rect x="{left}" width="340" height="{height}" fill="{bg}"/>',
            f'<text x="{left + 16}" y="30" fill="{fg}">{theme}: extended / basic index</text>',
        ]
        for index, ink in enumerate(Ink):
            extended, basic = PALETTES[theme][index]
            y = 65 + index * row_height
            color = xterm_hex(extended)
            # Background tints are swatches only; their own color would hide the label.
            label = fg if ink in FILL_INKS else color
            lines += [
                f'<rect x="{left + 16}" y="{y - 13}" width="20" height="16" fill="{color}"/>',
                f'<text x="{left + 46}" y="{y}" fill="{label}">{escape(ink.name)} {extended}/{basic}</text>',
            ]
    lines += ["</g></svg>"]
    path = Path(__file__).resolve().parents[1] / "docs/colors.svg"
    path.write_text("\n".join(lines) + "\n")
    print(path)


if __name__ == "__main__":
    main()
