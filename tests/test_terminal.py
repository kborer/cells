"""Terminal policy, incremental output, headless compatibility, and UI bounds."""

import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from terminal_cells import Frame, Ink, STEP, World
from terminal_cells.cli import TerminalRenderer, advance_frame, main, parser, use_color, use_unicode
from terminal_cells.models import State
from terminal_cells.render import FILL_INKS, KEEP, PALETTES, help_lines, render


class FakeCurses:
    class error(Exception):
        pass

    COLORS = 256
    COLOR_PAIRS = 256
    COLOR_BLACK, COLOR_WHITE, A_BOLD = 0, 7, 256

    def __init__(self, colors=True, defaults=True):
        self.colors, self.defaults = colors, defaults
        self.pairs = []
        self.updates = 0

    def has_colors(self):
        return self.colors

    def start_color(self):
        pass

    def use_default_colors(self):
        if not self.defaults:
            raise self.error()

    def init_pair(self, *args):
        self.pairs.append(args)

    def color_pair(self, number):
        return number << 9

    def doupdate(self):
        self.updates += 1


class Screen:
    def __init__(self, error=None):
        self.writes = []
        self.erases = 0
        self.error = error

    def erase(self):
        self.erases += 1

    def addstr(self, *args):
        self.writes.append(args)
        if self.error:
            raise self.error()

    def noutrefresh(self):
        pass


class TerminalTests(unittest.TestCase):
    def test_help_hides_inactive_tools_and_separates_interactive_controls(self):
        ambient = help_lines()
        interactive = help_lines(interactive=True)
        self.assertNotIn("Microscope tools", ambient)
        self.assertFalse(any("reticle" in line or "Lyse" in line for line in ambient))
        start = interactive.index("Microscope tools")
        self.assertEqual(interactive[start - 1 : start + 2], ["", "Microscope tools", ""])
        for tool in ("Inspect", "Lyse", "Feed", "Stir"):
            self.assertEqual(sum(tool in line for line in interactive), 1)
        self.assertIn("Tab            select the next entity", interactive)
        self.assertEqual(
            help_lines(), ambient, "building interactive help must not alter ambient help"
        )

    def test_color_policy_and_no_color_convention(self):
        for value, automatic in (("", True), ("1", False)):
            with patch.dict(os.environ, {"NO_COLOR": value}):
                self.assertEqual(use_color("auto"), automatic)
                self.assertTrue(use_color("always"))
                self.assertFalse(use_color("never"))

    def test_basic_colors_and_light_background_fallback(self):
        backend = FakeCurses(defaults=False)
        backend.COLORS = 8
        TerminalRenderer(Screen(), "light", "always", backend)
        self.assertEqual(len(backend.pairs), len(Ink))
        self.assertTrue(
            all(
                0 <= foreground < 8 and background == 7
                for _, foreground, background in backend.pairs
            )
        )
        disabled = FakeCurses(colors=False)
        TerminalRenderer(Screen(), "slide", "always", disabled)
        self.assertFalse(disabled.pairs)

    def test_fill_policy_needs_256_colors_and_a_colored_theme(self):
        def fill(theme="slide", color="always", backend=None):
            backend = backend or FakeCurses()
            return TerminalRenderer(Screen(), theme, color, backend, fill=True).fill

        self.assertTrue(fill())
        self.assertTrue(fill("light") and fill("amber"))
        self.assertFalse(TerminalRenderer(Screen(), "slide", "always", FakeCurses()).fill)
        self.assertFalse(fill("mono"))
        self.assertFalse(fill(color="never"))
        basic = FakeCurses()
        basic.COLORS = 8
        self.assertFalse(fill(backend=basic))
        few_pairs = FakeCurses()
        few_pairs.COLOR_PAIRS = len(Ink) + 2
        self.assertFalse(fill(backend=few_pairs))
        self.assertFalse(parser().parse_args([]).fill)
        self.assertTrue(parser().parse_args(["--fill"]).fill)

    def test_fill_pairs_glyph_ink_with_body_tint(self):
        backend, screen = FakeCurses(), Screen()
        renderer = TerminalRenderer(screen, "slide", "always", backend, fill=True)
        frame = Frame(5, 3, fill=True)
        frame.put(1, 1, " ", Ink.CYTOPLASM, bg=Ink.FILL_CYTOPLASM)
        frame.put(1, 1, "o", Ink.VESICLE)  # a glyph drawn later keeps the tint
        frame.put(2, 1, "o", Ink.VESICLE, bg=None)
        renderer.draw(frame)
        number = len(Ink) + 1
        palette = PALETTES["slide"]
        self.assertEqual(
            backend.pairs[-1],
            (
                number,
                palette[Ink.VESICLE.value - 1][0],
                palette[Ink.FILL_CYTOPLASM.value - 1][0],
            ),
        )
        self.assertIn((1, 1, "o", number << 9), screen.writes)
        self.assertIn((1, 2, "o", Ink.VESICLE.value << 9), screen.writes)
        # A change of tint alone is redrawn; an unchanged frame writes nothing.
        screen.writes.clear()
        renderer.draw(frame)
        self.assertFalse(screen.writes)
        retinted = Frame(5, 3, fill=True)
        retinted.pixels = [list(row) for row in frame.pixels]
        retinted.put(1, 1, "o", Ink.VESICLE, bg=Ink.FILL_NUCLEUS)
        renderer.draw(retinted)
        self.assertEqual([write[:3] for write in screen.writes], [(1, 1, "o")])

    def test_fill_keeps_sprites_tinted_but_clears_captions(self):
        frame = Frame(8, 3, fill=True)
        for col in range(8):
            frame.put(col, 1, " ", Ink.RED_DIM, bg=Ink.FILL_RED)
        frame.text(0, 1, "ab")
        frame.text(4, 1, "-<", Ink.PHAGE, bg=KEEP)
        self.assertEqual([p.bg for p in frame.pixels[1][:2]], [None, None])
        self.assertEqual([p.bg for p in frame.pixels[1][4:6]], [Ink.FILL_RED, Ink.FILL_RED])
        plain = Frame(2, 1)
        plain.put(0, 0, " ", Ink.RED_DIM, bg=Ink.FILL_RED)
        self.assertIsNone(plain.pixels[0][0].bg, "glyph-only frames never carry a tint")

    def test_failed_tint_pair_falls_back_to_glyph_frames(self):
        class Refusing(FakeCurses):
            def init_pair(self, number, *args):
                if number > len(Ink):
                    raise self.error()
                super().init_pair(number, *args)

        backend, screen = Refusing(), Screen()
        renderer = TerminalRenderer(screen, "slide", "always", backend, fill=True)
        frame = Frame(5, 3, fill=True)
        frame.put(1, 1, " ", Ink.NUCLEUS, bg=Ink.FILL_NUCLEUS)
        renderer.draw(frame)
        self.assertFalse(renderer.fill)
        self.assertIsNone(renderer.previous, "the next glyph-only frame must repaint fully")

    def test_fill_frames_tint_bodies_but_keep_outlines_on_the_slide(self):
        world = World(120, 40, 42)
        enclosing = False
        # Includes an engulfment, whose wrapping pseudopods are outer membrane too.
        for at in (4.7, 20):
            while world.time < at:
                world.update(STEP)
            enclosing |= any(cell.state is State.ENCLOSE for cell in world.cells)
            plain, filled = render(world, True), render(world, True, fill=True)
            self.assertTrue(all(p.bg is None for row in plain.pixels for p in row))
            tints = {p.bg for row in filled.pixels for p in row} - {None}
            self.assertTrue(tints <= set(FILL_INKS))
            self.assertTrue(tints & {Ink.FILL_CYTOPLASM, Ink.FILL_NEUTROPHIL})
            for row in filled.pixels:
                for pixel in row:
                    if pixel.ink in (Ink.MEMBRANE, Ink.NEUTROPHIL, Ink.RED):
                        self.assertIsNone(pixel.bg)
        self.assertTrue(enclosing)

    def test_diff_output_resize_and_bottom_right_errors(self):
        backend, screen = FakeCurses(), Screen()
        renderer = TerminalRenderer(screen, "slide", "never", backend)
        frame = Frame(5, 3)
        renderer.draw(frame)
        screen.writes.clear()
        renderer.draw(frame)
        self.assertFalse(screen.writes)
        changed = Frame(5, 3)
        changed.text(1, 1, "xx", Ink.RED, True)
        renderer.draw(changed)
        self.assertEqual(screen.writes, [(1, 1, "xx", backend.A_BOLD)])
        renderer.draw(Frame(6, 4))
        self.assertEqual(screen.erases, 2)
        screen.error = backend.error
        renderer.draw(Frame(1, 1))  # curses ERR must not lose future redraws
        self.assertEqual(renderer.previous.width, 1)

    def test_unicode_selection_and_alias(self):
        self.assertTrue(use_unicode("auto", "UTF-8"))
        self.assertFalse(use_unicode("auto", "ascii"))
        self.assertFalse(use_unicode("never", "UTF-8"))
        self.assertTrue(use_unicode("always", "ascii"))
        self.assertEqual(parser().parse_args(["--ascii"]).unicode, "never")
        self.assertEqual(parser().parse_args([]).unicode, "auto")

    def test_catchup_bounds_preserve_fixed_steps(self):
        world = World(80, 24, 42)
        remaining = advance_frame(world, 100)
        self.assertAlmostEqual(world.time, STEP * 6)
        self.assertAlmostEqual(remaining, STEP * 6)
        advance_frame(world, STEP / 2)
        self.assertAlmostEqual(world.time, STEP * 6)

    def test_calm_defaults_and_explicit_override(self):
        cli = importlib.import_module("terminal_cells.cli")
        with (
            patch.object(cli.sys.stdin, "isatty", return_value=True),
            patch.object(cli.sys.stdout, "isatty", return_value=True),
            patch.dict(os.environ, {"TERM": "xterm"}),
            patch.object(cli, "load_curses") as load,
        ):
            main(["--calm"])
            first = load.return_value.wrapper.call_args.args[1]
            self.assertEqual((first.speed, first.fps), (0.5, 10))
            main(["--calm", "--speed", "2", "--fps", "24"])
            second = load.return_value.wrapper.call_args.args[1]
            self.assertEqual((second.speed, second.fps), (2, 24))

    def test_headless_commands_without_curses(self):
        root = Path(__file__).resolve().parents[1]
        code = """
import importlib.abc, sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *args):
        if fullname in ('curses', '_curses'):
            raise ImportError('curses intentionally unavailable')
sys.meta_path.insert(0, Block())
from terminal_cells.cli import main
raise SystemExit(main(sys.argv[1:]))
"""
        for args in (["--help"], ["--version"], ["--snapshot", "--at", "0"], ["--diagnostics"]):
            result = subprocess.run(
                [sys.executable, "-c", code, *args], cwd=root, capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("\x1b", result.stdout)
        report = json.loads(result.stdout)
        self.assertFalse(report["curses_available"])

    def test_missing_curses_interactive_has_actionable_error(self):
        cli = importlib.import_module("terminal_cells.cli")
        output = io.StringIO()
        with (
            patch.object(cli.sys.stdin, "isatty", return_value=True),
            patch.object(cli.sys.stdout, "isatty", return_value=True),
            patch.dict(os.environ, {"TERM": "xterm"}),
            patch.object(cli, "load_curses", side_effect=ImportError()),
            contextlib.redirect_stderr(output),
        ):
            self.assertEqual(main([]), 2)
        self.assertIn("--snapshot", output.getvalue())

    def test_scene_composition_and_validation(self):
        microbial = World(100, 32, 42, scene="microbial")
        for _ in range(3300):
            microbial.update()
        self.assertFalse(microbial.cells)
        self.assertFalse(microbial.red_cells)
        blood = World(100, 32, 42, scene="blood")
        for _ in range(1600):
            blood.update()
        self.assertFalse(blood.hyphae)
        self.assertTrue(blood.cells)
        with self.assertRaises(ValueError):
            World(80, 24, 1, scene="unknown")
