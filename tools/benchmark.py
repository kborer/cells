#!/usr/bin/env python3
"""Report update and render latency; measurements exclude terminal output."""

from pathlib import Path
import argparse
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from terminal_cells import World  # noqa: E402


from terminal_cells.capabilities import RenderCapabilities  # noqa: E402
from terminal_cells.styles import STYLES, RenderOptions, get_style  # noqa: E402
from terminal_cells.viewport import Camera, MAGNIFICATIONS  # noqa: E402


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--samples", type=int, default=100)
    cli.add_argument("--style", choices=tuple(STYLES), default="classic")
    cli.add_argument("--magnification", choices=tuple(MAGNIFICATIONS), default="normal")
    cli.add_argument("--ascii", action="store_true")
    cli.add_argument("--fill", action="store_true")
    args = cli.parse_args()
    if args.samples < 2:
        cli.error("--samples must be at least 2")
    style = get_style(args.style)
    caps = RenderCapabilities(
        unicode=not args.ascii, colors=256, backgrounds=True, blocks=not args.ascii, color_pairs=256
    )
    options = RenderOptions.resolve(caps, fill=args.fill or style.default_fill)
    print(
        f"style {style.name}; magnification {args.magnification}; Unicode {options.unicode}; fill {options.fill}"
    )
    for width, height in ((80, 24), (120, 40), (200, 60)):
        camera = Camera(width, height, args.magnification)
        world = World(*camera.simulation_size(), 42)
        for _ in range(1800):
            world.update()
        camera.focus(world)
        results = []
        for operation in (world.update, lambda: camera.render(style, world, options)):
            timings = []
            for _ in range(args.samples):
                start = time.perf_counter()
                operation()
                timings.append((time.perf_counter() - start) * 1000)
            results.append(
                f"{statistics.median(timings):.2f}/{sorted(timings)[int(0.95 * (len(timings) - 1))]:.2f} ms"
            )
        print(f"{width}x{height}: update p50/p95 {results[0]}; render p50/p95 {results[1]}")


if __name__ == "__main__":
    main()
