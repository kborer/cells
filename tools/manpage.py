#!/usr/bin/env python3
"""Generate the checked-in manual from the CLI option definitions."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from terminal_cells import __version__  # noqa: E402
from terminal_cells.cli import parser  # noqa: E402


def escape(text):
    return str(text).replace("\\", r"\e").replace("-", r"\-")


def render(version=None):
    """Return the complete manual without writing files or changing the CLI."""
    version = __version__ if version is None else version
    lines = [
        f'.TH CELLS 1 "" "cells {version}" "User Commands"',
        ".SH NAME",
        "cells \\- a living microscope slide in your terminal",
        ".SH SYNOPSIS",
        ".B cells",
        ".RI [ options ]",
        ".SH DESCRIPTION",
        "Animated immune cells, microbes, fungi, and bacteriophages. Sizes and",
        "timings are illustrative. Requires Python 3.10 or later; interactive",
        "mode requires curses on Linux or macOS (Windows users can use WSL).",
        ".SH OPTIONS",
    ]
    for action in parser()._actions:
        names = ", ".join(escape(option) for option in action.option_strings)
        if action.nargs != 0:
            names += " " + escape(action.metavar or action.dest.upper())
        lines += [".TP", ".B " + names, escape(action.help or "")]
        if action.choices:
            lines += ["Choices: " + ", ".join(escape(c) for c in action.choices) + "."]
    lines += [
        ".SH CONTROLS",
        "q/Escape quits; Space pauses; +/\\- changes speed; r resets the slide;",
        "s toggles statistics; ? toggles help; j/k or arrows scroll help;",
        "H/J/K/L pans the magnified view; Ctrl-L redraws.",
        "Screensaver mode exits on any key except resize.",
        "With interactive mode: 1 Inspect, 2 Lyse, 3 Feed, 4 Stir; left-click or",
        "Enter applies. Arrows/hjkl aim; Tab selects and follows an entity.",
        ".SH ENVIRONMENT",
        ".TP",
        ".B NO_COLOR",
        "A nonempty value disables automatic color. Explicit \\-\\-color always overrides it.",
        ".TP",
        ".B TERM",
        "Must identify the actual terminal for interactive mode.",
        ".SH EXAMPLES",
        ".nf",
        "cells \\-\\-scene microbial \\-\\-calm",
        "cells \\-\\-theme light \\-\\-observe",
        "cells \\-\\-snapshot \\-\\-seed 42 \\-\\-size 100x32 \\-\\-at 30",
        ".fi",
        ".SH NOTES",
        "Snapshots are ASCII without escape codes. Duration is wall time;",
        "snapshot time is simulated time. A seed is reproducible within the",
        "same version, size, and update/resize history. Normal quits, SIGINT,",
        "and SIGTERM restore terminal settings. SIGKILL cannot run cleanup.",
        ".SH EXIT STATUS",
        "0 on success; 1 on terminal failure; 2 for invalid usage or missing curses.",
    ]
    return "\n".join(lines) + "\n"


def main():
    import argparse

    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--check", action="store_true", help="fail if the checked-in manual is stale")
    args = cli.parse_args()
    destination = Path(__file__).resolve().parents[1] / "docs/cells.1"
    content = render()
    if args.check:
        if not destination.is_file() or destination.read_text() != content:
            cli.exit(1, "Manual is stale; run python tools/manpage.py\n")
    else:
        destination.write_text(content)


if __name__ == "__main__":
    main()
