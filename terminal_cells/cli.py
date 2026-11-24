"""Command-line interface and interactive terminal session."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import math
import platform
import shutil
import os
import random
import signal
import sys
import time
from .models import STEP, State, division_stage, viral_stage
from .world import World
from .interaction import Interaction, enable_mouse, restore_mouse, read_click
from .frame import FILL_INKS, Frame, Ink, PALETTES
from .render import HELP_INKS, help_lines, overlay
from .capabilities import RenderCapabilities
from .styles import DEFAULT_STYLE, STYLES, RenderOptions, get_style
from .viewport import Camera, MAGNIFICATIONS
from . import __version__


def load_curses():
    """Keep plain-text commands usable on Python builds without curses."""
    return importlib.import_module("curses")


def use_color(policy: str) -> bool:
    return policy == "always" or (policy == "auto" and not os.environ.get("NO_COLOR"))


def use_unicode(policy: str, encoding: str | None) -> bool:
    return policy == "always" or (policy == "auto" and "UTF" in (encoding or "").upper())


def advance_frame(world: World, accumulator: float, *, events: bool = True) -> float:
    """Bound catch-up work; overloaded terminals slow simulated time, not input."""
    accumulator = min(accumulator, STEP * 12)
    for _ in range(6):
        if accumulator < STEP:
            break
        world.update(events=events)
        accumulator -= STEP
    return accumulator


class TerminalRenderer:
    def __init__(
        self,
        screen,
        theme: str,
        color: str = "auto",
        backend=None,
        fill: bool = False,
        palette=None,
    ):
        self.curses = backend if backend is not None else load_curses()
        self.color = color
        self.theme = theme
        self.palette = tuple(palette if palette is not None else PALETTES[theme])
        self.screen = screen
        self.previous: Frame | None = None
        self.attributes: dict[Ink, int] = {ink: 0 for ink in Ink}
        # Background tints need 256 colors and spare color pairs for each
        # (glyph ink, tint) combination; otherwise bodies stay glyph-only.
        self.fill = False
        self._palette: list[int] = []
        self._pairs: dict[tuple[Ink, Ink] | tuple[int, int], int] = {}
        self._colors(theme)
        if fill and self._palette and theme != "mono":
            # Reserve a pair for every (glyph ink, tint) combination up front, so
            # tinting never runs out of pairs halfway through a slide. This stays
            # below 256, which also fits the 8-bit pair field of A_COLOR.
            needed = len(Ink) + len(Ink) * len(FILL_INKS)
            pairs = getattr(self.curses, "COLOR_PAIRS", 0)
            self.fill = self.curses.COLORS >= 256 and pairs > needed

    def capabilities(self, unicode: bool = False) -> RenderCapabilities:
        """Resolve current output support; fill may have failed since last frame."""
        colors = 0
        if self._palette and self.theme != "mono":
            colors = 256 if self.curses.COLORS >= 256 else 8
        return RenderCapabilities(
            unicode=unicode,
            colors=colors,
            backgrounds=self.fill,
            blocks=unicode,
            color_pairs=getattr(self.curses, "COLOR_PAIRS", 0) if colors else 0,
            theme=self.theme,
        )

    def _colors(self, theme: str) -> None:
        curses = self.curses
        if not curses.has_colors() or not use_color(self.color):
            return
        curses.start_color()
        background = curses.COLOR_WHITE if theme == "light" else curses.COLOR_BLACK
        try:
            curses.use_default_colors()
            background = -1
        except curses.error:
            pass
        for ink, (extended, basic) in zip(Ink, self.palette):
            try:
                curses.init_pair(ink.value, extended if curses.COLORS >= 256 else basic, background)
                self.attributes[ink] = curses.color_pair(ink.value)
            except curses.error:
                pass
        self._palette = [extended for extended, _ in self.palette]

    def _attribute(self, ink: Ink, bg: Ink | None) -> int:
        if bg is None or not self.fill:
            return self.attributes[ink]
        key = ink, bg
        if key not in self._pairs:
            number = len(Ink) + 1 + len(self._pairs)
            try:
                self.curses.init_pair(
                    number, self._palette[ink.value - 1], self._palette[bg.value - 1]
                )
            except self.curses.error:
                # Tinted frames replace some textures with spaces, so a missing
                # pair would erase them. Fall back to glyph-only frames and repaint.
                self.fill = False
                return self.attributes[ink]
            self._pairs[key] = self.curses.color_pair(number)
        return self._pairs[key]

    def _indexed_attribute(self, pixel) -> int:
        if not self.fill:
            return self.attributes[pixel.ink]
        key = pixel.color, pixel.background
        if key not in self._pairs:
            number = len(Ink) + 1 + len(self._pairs)
            try:
                if number >= min(256, self.curses.COLOR_PAIRS):
                    raise self.curses.error()
                self.curses.init_pair(number, pixel.color, pixel.background)
            except self.curses.error:
                self.fill = False
                return self.attributes[pixel.ink]
            self._pairs[key] = self.curses.color_pair(number)
        return self._pairs[key]

    def draw(self, frame: Frame) -> None:
        curses = self.curses
        previous = self.previous
        if previous is None or (previous.width, previous.height) != (frame.width, frame.height):
            self.screen.erase()
            previous = None
        for y, row in enumerate(frame.pixels):
            x = 0
            while x < frame.width:
                pixel = row[x]
                if previous and previous.pixels[y][x] == pixel:
                    x += 1
                    continue
                # Group adjacent changed characters with the same attributes.
                start = x
                chars = []
                style = pixel.ink, pixel.bold, pixel.bg, pixel.color, pixel.background
                while x < frame.width:
                    current = row[x]
                    if (
                        current.ink,
                        current.bold,
                        current.bg,
                        current.color,
                        current.background,
                    ) != style:
                        break
                    if previous and previous.pixels[y][x] == current:
                        break
                    chars.append(current.char)
                    x += 1
                attributes = (
                    self._indexed_attribute(pixel)
                    if pixel.color is not None
                    else self._attribute(pixel.ink, pixel.bg)
                ) | (curses.A_BOLD if pixel.bold else 0)
                try:
                    self.screen.addstr(y, start, "".join(chars), attributes)
                except curses.error:
                    # Writing the bottom-right character and resize races can
                    # report ERR even after curses has successfully drawn it.
                    pass
        self.screen.noutrefresh()
        curses.doupdate()
        # A frame drawn after fill was switched off is repainted in full next time.
        self.previous = frame if self.fill or not frame.fill else None


def run(screen, args: argparse.Namespace) -> None:
    curses = load_curses()
    available, old_mask, old_interval = False, None, None
    if args.interactive:
        available, old_mask, old_interval = enable_mouse(curses)
    try:
        _session(screen, args, available)
    finally:
        if args.interactive:
            restore_mouse(curses, old_mask, old_interval)


def _session(screen, args: argparse.Namespace, mouse: bool) -> None:
    curses = load_curses()
    screen.keypad(True)
    screen.nodelay(True)
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    rows, columns = screen.getmaxyx()
    camera = Camera(columns, rows, args.magnification)
    world = World(
        *camera.simulation_size(),
        args.seed,
        args.density,
        scene=args.scene,
        rare_events=not args.no_events,
        microscope_events=not args.calm,
        complement=not args.no_complement,
    )
    camera.focus(world)
    interaction = (
        Interaction(columns // 2, rows // 2, mouse=mouse, camera=camera)
        if args.interactive
        else None
    )
    style = get_style(args.style)
    fill_requested = args.fill or style.default_fill
    renderer = TerminalRenderer(
        screen, args.theme, args.color, fill=fill_requested, palette=style.palette(args.theme)
    )
    unicode = use_unicode(args.unicode, screen.encoding)
    paused, help_visible, stats = False, False, args.stats
    help_offset = 0
    help_content = help_lines(args.interactive, legend=style.legend)
    help_inks = HELP_INKS | (dict(style.legend) if style.legend is not None else {})
    notice, notice_until = "", 0.0
    counters = (
        world.engulfed,
        world.divisions,
        world.infections,
        world.lysed,
        world.arrivals,
        world.complement.bindings,
        world.complement.lysed,
    )
    speed = args.speed
    last = time.monotonic()
    accumulator = 0.0
    started = last
    while True:
        tick = time.monotonic()
        if args.duration is not None and tick - started >= args.duration:
            return
        dimensions = screen.getmaxyx()
        if dimensions != (rows, columns):
            rows, columns = dimensions
            camera.columns, camera.rows = columns, rows
            world.resize(*camera.simulation_size())
            camera.x = camera.y = None
        help_limit = max(0, len(help_content[2:]) - max(1, rows - 7))
        help_offset = min(help_offset, help_limit)
        # Drain queued input so rapid key presses remain responsive.
        for _ in range(64):
            key = screen.getch()
            if key == -1:
                break
            if key == curses.KEY_RESIZE:
                renderer.previous = None
                continue
            if args.screensaver or key in (ord("q"), ord("Q"), 27):
                return
            if interaction is not None and key == getattr(curses, "KEY_MOUSE", -999):
                click = read_click(curses)
                if click and not help_visible and columns >= 32 and rows >= 12:
                    interaction.click(world, *click, tick)
                continue
            if key == ord(" "):
                paused = not paused
            elif key in (ord("+"), ord("=")):
                speed = min(8.0, speed * 1.25)
            elif key in (ord("-"), ord("_")):
                speed = max(0.125, speed / 1.25)
            elif key in (ord("r"), ord("R")):
                seed = (world.seed + 1) % (2**64)
                world = World(
                    *camera.simulation_size(),
                    seed,
                    args.density,
                    scene=args.scene,
                    rare_events=not args.no_events,
                    microscope_events=not args.calm,
                    complement=not args.no_complement,
                )
                accumulator = 0
                camera.x = camera.y = None
                camera.focus(world)
                if interaction is not None:
                    interaction = Interaction(columns // 2, rows // 2, mouse=mouse, camera=camera)
            elif key == ord("?"):
                help_visible = not help_visible
            elif help_visible and key in (ord("j"), curses.KEY_DOWN, curses.KEY_NPAGE):
                help_offset = min(help_limit, help_offset + 1)
            elif help_visible and key in (ord("k"), curses.KEY_UP, curses.KEY_PPAGE):
                help_offset = max(0, help_offset - 1)
            elif key in (ord("s"), ord("S")):
                stats = not stats
            elif not help_visible and key in (ord("H"), ord("J"), ord("K"), ord("L")):
                dx, dy = {ord("H"): (-1, 0), ord("J"): (0, 1), ord("K"): (0, -1), ord("L"): (1, 0)}[
                    key
                ]
                camera.pan(world, dx, dy)
                renderer.previous = None
            elif key == 12:  # Ctrl-L
                renderer.previous = None
            elif interaction is not None and not help_visible and columns >= 32 and rows >= 12:
                interaction.key(world, key, curses, tick)
        wall_elapsed = max(0, tick - last)
        elapsed = min(0.25, wall_elapsed)
        last = tick
        too_small = columns < 32 or rows < 12
        if not paused and not help_visible and not too_small:
            accumulator += elapsed * speed
            accumulator = advance_frame(world, accumulator, events=False)
            world.advance_events(wall_elapsed)
        current = (
            world.engulfed,
            world.divisions,
            world.infections,
            world.lysed,
            world.arrivals,
            world.complement.bindings,
            world.complement.lysed,
        )
        if current != counters:
            events = [
                label
                for label, before, after in zip(
                    (
                        "Engulfment: sealed vesicle moves inward",
                        "Cell division completed",
                        "Phage infection: viral replication begins",
                        "Lysis: new phages released",
                        "New arrival from the slide edge",
                        "Complement: surface coating aids immune recognition",
                        "Complement membrane attack: bacterial lysis",
                    ),
                    counters,
                    current,
                )
                if after > before
            ]
            if events:
                notice, notice_until = events[-1], tick + 5
            counters = current
        if args.observe:
            phases = [division_stage(c.elapsed)[0] for c in world.cells if c.state is State.DIVIDE]
            phases += [
                viral_stage(b.infection.age)[0] for b in world.bacteria.values() if b.infection
            ]
            if phases:
                notice, notice_until = " / ".join(dict.fromkeys(phases)), tick + 1
        if args.observe and world.events.caption:
            notice, notice_until = world.events.caption, tick + 1
        frame = camera.render(
            style, world, RenderOptions.resolve(renderer.capabilities(unicode), fill=fill_requested)
        )
        if too_small:
            overlay(frame, ["cells", "Enlarge to at least 32 x 12.", "q to quit"])
        elif help_visible:
            lines = [help_content[0], "j/k or arrows scroll; ? closes", ""] + help_content[
                2 + help_offset :
            ]
            overlay(frame, lines, [help_inks.get(line, Ink.TEXT) for line in lines])
        else:
            if stats:
                frame.text(
                    1,
                    0,
                    f"seed {world.seed}  {speed:.2g}x  cells {len(world.cells)}  "
                    f"microbes {len(world.bacteria)}  phages {len(world.phages)}"[: columns - 2],
                )
                frame.text(
                    1,
                    1,
                    f"engulfed {world.engulfed}  divisions {world.divisions}  "
                    f"infections {world.infections}  lysed {world.lysed}  arrivals {world.arrivals}  rare {sum(world.events.counts.values())}"[
                        : columns - 2
                    ],
                    Ink.MUTED,
                )
                frame.text(
                    1,
                    rows - 1,
                    "? help   Space pause   +/- speed   r new slide   s hide",
                    Ink.MUTED,
                )
                phases = [
                    f"cell {c.id}: {division_stage(c.elapsed)[0]}"
                    for c in world.cells
                    if c.state is State.DIVIDE
                ]
                phases += [
                    f"bacterium {b.id}: {viral_stage(b.infection.age)[0]}"
                    for b in world.bacteria.values()
                    if b.infection is not None
                ]
                feeding = sum(b.fed_until > world.time for b in world.bacteria.values())
                riding = sum(b.rail is not None for b in world.bacteria.values())
                escaping = sum(b.escape_until > world.time for b in world.bacteria.values())
                if world.events.caption:
                    phases.insert(0, world.events.caption)
                if feeding or riding or escaping:
                    phases.insert(
                        0, f"feeding {feeding} / on hyphae {riding} / escaping {escaping}"
                    )
                if phases:
                    frame.text(
                        1,
                        rows - 2,
                        "  |  ".join(phases)[: columns - 2],
                        Ink.SPINDLE,
                    )
            if args.observe and tick < notice_until:
                frame.text(
                    1,
                    max(0, rows - 3),
                    notice[: max(0, columns - 2)],
                    Ink.TEXT,
                )
            if paused:
                frame.text(max(0, columns // 2 - 4), rows - 1, " paused ", Ink.TEXT)
            if interaction is not None:
                interaction.draw(frame, world, tick, paused)
        renderer.draw(frame)
        # Input is checked at least 15 times/second, even at low requested FPS.
        remaining = max(0, 1 / args.fps - (time.monotonic() - tick))
        while remaining > 0:
            if args.duration is not None and time.monotonic() - started >= args.duration:
                return
            delay = min(remaining, 1 / 30)
            time.sleep(delay)
            remaining -= delay
            key = screen.getch()
            if key != -1:
                # Return the consumed key to the queue for the next frame.
                curses.ungetch(key)
                break


def positive_number(value: str) -> float:
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a number") from None
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be a finite number greater than zero")
    return number


def bounded(low: float, high: float):
    def parse(value: str) -> float:
        try:
            number = float(value)
        except ValueError:
            raise argparse.ArgumentTypeError("must be a number") from None
        if not math.isfinite(number) or not low <= number <= high:
            raise argparse.ArgumentTypeError(f"must be between {low:g} and {high:g}")
        return number

    return parse


class HelpFormatter(argparse.ArgumentDefaultsHelpFormatter):
    def _get_help_string(self, action):
        if action.default is None or action.nargs == 0:
            return action.help
        return super()._get_help_string(action)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="A living microscope slide: drifting cells, swimming microbes, and engulfment.",
        epilog="Keys: q/Esc quit, Space pause, +/- speed, r new slide, s statistics, ? help.",
        formatter_class=HelpFormatter,
    )
    scene = result.add_argument_group("simulation")
    scene.add_argument(
        "--seed", type=int, help="repeat a slide within the same program version (normally random)"
    )
    scene.add_argument(
        "--scene", choices=("mixed", "blood", "microbial"), default="mixed", help="community preset"
    )
    scene.add_argument(
        "--density",
        type=bounded(0.25, 3),
        default=1.0,
        metavar="0.25..3",
        help="population multiplier",
    )
    scene.add_argument(
        "--speed",
        type=bounded(0.125, 8),
        metavar="0.125..8",
        help="simulation speed (normally 1; calm: 0.5)",
    )
    display = result.add_argument_group("display")
    display.add_argument(
        "--fps",
        type=bounded(1, 60),
        metavar="1..60",
        help="maximum frame rate (normally 30; calm: 10)",
    )
    display.add_argument(
        "--calm",
        action="store_true",
        help="slower motion, lower FPS, and no micropipette; explicit speed/fps win",
    )
    display.add_argument(
        "--style",
        choices=tuple(STYLES),
        default=DEFAULT_STYLE,
        help="presentation style; stained and raster are experimental",
    )
    display.add_argument(
        "--magnification",
        choices=tuple(MAGNIFICATIONS),
        default="normal",
        help="overview, normal scale, or bacterial detail; H/J/K/L pan the view",
    )
    display.add_argument(
        "--theme",
        choices=PALETTES,
        default="slide",
        help="color palette; light suits white backgrounds",
    )
    display.add_argument(
        "--color",
        choices=("auto", "always", "never"),
        default="auto",
        help="auto respects nonempty NO_COLOR; always overrides it",
    )
    display.add_argument(
        "--fill",
        action="store_true",
        help="tint cell bodies behind their glyphs (256-color terminals)",
    )
    chars = display.add_mutually_exclusive_group()
    chars.add_argument(
        "--unicode",
        choices=("auto", "always", "never"),
        default="auto",
        help="auto uses Unicode for UTF encodings",
    )
    chars.add_argument(
        "--ascii",
        dest="unicode",
        action="store_const",
        const="never",
        help="alias for --unicode never",
    )
    display.add_argument(
        "--stats", action="store_true", help="show population and lifecycle statistics at startup"
    )
    display.add_argument(
        "--observe", action="store_true", help="caption lifecycle stages and recent events"
    )
    display.add_argument(
        "--no-complement", action="store_true", help="disable dissolved complement activity"
    )
    display.add_argument(
        "--no-events", action="store_true", help="disable rare visitors and microscope events"
    )
    mode = display.add_mutually_exclusive_group()
    mode.add_argument("--screensaver", action="store_true", help="exit on any key")
    mode.add_argument(
        "--interactive",
        action="store_true",
        help="enable microscope tools; mouse or keyboard targeting",
    )
    display.add_argument(
        "--duration",
        type=positive_number,
        metavar="SECONDS",
        help="exit after this many wall-clock seconds (normally unlimited)",
    )
    output = result.add_argument_group("plain-text output")
    output.add_argument(
        "--snapshot",
        action="store_true",
        help="print one ASCII frame without terminal escapes and exit",
    )
    output.add_argument(
        "--size", default="80x24", metavar="COLSxROWS", help="snapshot dimensions, up to 500x200"
    )
    output.add_argument(
        "--at",
        type=bounded(0, 3600),
        default=12.0,
        metavar="SECONDS",
        help="simulation time for snapshot",
    )
    output.add_argument(
        "--diagnostics",
        action="store_true",
        help="print terminal capability information as JSON and exit",
    )
    result.add_argument("--version", action="version", version=f"cells {__version__}")
    return result


def diagnostics(args) -> dict:
    size = shutil.get_terminal_size((80, 24))
    try:
        available = importlib.util.find_spec("curses") is not None
    except (ImportError, ValueError):
        available = False
    return {
        "version": __version__,
        "python": platform.python_version(),
        "platform": sys.platform,
        "term": os.environ.get("TERM", ""),
        "encoding": sys.stdout.encoding,
        "stdin_tty": sys.stdin.isatty(),
        "stdout_tty": sys.stdout.isatty(),
        "columns": size.columns,
        "rows": size.lines,
        "curses_available": available,
        "rare_events": not args.no_events,
        "microscope_events": not args.no_events and not args.calm,
        "interactive_requested": args.interactive,
        "color_requested": use_color(args.color),
        "fill_requested": args.fill or get_style(args.style).default_fill,
        "style": args.style,
        "magnification": args.magnification,
        "complement_requested": not args.no_complement,
        "unicode_requested": use_unicode(args.unicode, sys.stdout.encoding),
        "note": "Capabilities are requested settings; actual colors depend on terminal support.",
    }


def main(argv: list[str] | None = None) -> int:
    cli = parser()
    args = cli.parse_args(argv)
    if args.interactive and args.snapshot:
        cli.error("--interactive requires an interactive terminal, not --snapshot")
    args.speed = args.speed if args.speed is not None else (0.5 if args.calm else 1.0)
    args.fps = args.fps if args.fps is not None else (10.0 if args.calm else 30.0)
    if args.diagnostics:
        print(json.dumps(diagnostics(args), indent=2))
        return 0
    if args.seed is None:
        args.seed = random.SystemRandom().randrange(2**32)
    if args.snapshot:
        try:
            columns, rows = (int(part) for part in args.size.lower().split("x"))
            if not (1 <= columns <= 500 and 1 <= rows <= 200):
                raise ValueError
        except ValueError:
            cli.error("--size must be COLSxROWS, from 1x1 through 500x200")
        camera = Camera(columns, rows, args.magnification)
        world = World(
            *camera.simulation_size(),
            args.seed,
            args.density,
            scene=args.scene,
            rare_events=not args.no_events,
            microscope_events=not args.calm,
            complement=not args.no_complement,
        )
        for _ in range(round(args.at / STEP)):
            world.update()
        camera.focus(world)
        print(
            camera.render(
                get_style(args.style), world, RenderOptions.resolve(RenderCapabilities())
            ).plain()
        )
        return 0
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        cli.error("interactive mode needs a terminal; use --snapshot for plain-text output")
    if os.environ.get("TERM", "dumb") in ("", "dumb"):
        cli.error("set TERM to your terminal type, or use --snapshot")
    try:
        curses = load_curses()
    except ImportError:
        print(
            "cells: interactive mode requires Python curses support; install your platform's curses package or use --snapshot",
            file=sys.stderr,
        )
        return 2
    old_handler = signal.getsignal(signal.SIGTERM)

    # Raise through curses.wrapper so SIGTERM also restores the terminal.
    def terminate(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, terminate)
    try:
        curses.wrapper(run, args)
    except KeyboardInterrupt:
        return 0
    except curses.error as error:
        print(f"cells: terminal error: {error}", file=sys.stderr)
        return 1
    finally:
        signal.signal(signal.SIGTERM, old_handler)
    return 0
