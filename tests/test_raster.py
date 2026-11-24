"""Whole-field rendering, color budget, anatomy, and limited-terminal behavior."""

from contextlib import redirect_stdout
import io
import unittest

from terminal_cells.capabilities import RenderCapabilities
from terminal_cells.cli import TerminalRenderer, parser, main
from terminal_cells.frame import Frame, Ink
from terminal_cells.raster import COLORS, Field, nuclei, tile
from terminal_cells.render import render, help_lines
from terminal_cells.scenes import SCENES, make_scene
from terminal_cells.styles import get_style, RenderOptions, STYLES
from test_terminal import FakeCurses, Screen


CAPS = RenderCapabilities(unicode=True, colors=256, backgrounds=True, blocks=True, color_pairs=256)
OPTIONS = RenderOptions.resolve(CAPS, fill=True)


class RasterTests(unittest.TestCase):
    def test_names_and_classic_default_are_unambiguous(self):
        self.assertEqual(tuple(STYLES), ("classic", "stained", "raster"))
        self.assertEqual(parser().parse_args([]).style, "classic")
        self.assertEqual(get_style().name, "classic")
        self.assertNotIn("microscopy", STYLES)
        self.assertTrue(get_style("stained").default_fill)

    def test_entire_scene_including_microbes_and_slide_is_rasterized(self):
        world = make_scene("crowding")
        field = get_style("raster").render(world, OPTIONS)
        self.assertNotEqual(field.pixels, get_style("stained").render(world, OPTIONS).pixels)
        pixels = [p for row in field.pixels for p in row]
        self.assertTrue(all(p.color in COLORS and p.background in COLORS for p in pixels))
        self.assertTrue(any(p.ink is Ink.BACTERIA for p in pixels))
        self.assertTrue(any(p.ink is Ink.RED for p in pixels))
        self.assertTrue(any(p.ink is Ink.NUCLEUS for p in pixels))
        self.assertTrue(any(p.color == p.background == COLORS[0] for p in pixels))
        self.assertFalse(any(p.char in "/\\|_-" for p in pixels))
        self.assertGreater(len({(p.color, p.background) for p in pixels}), 10)

    def test_fallbacks_match_classic_drawing_and_plain_snapshots(self):
        world = make_scene("blood-smear")
        for caps in (
            RenderCapabilities(),
            RenderCapabilities(unicode=True),
            RenderCapabilities(unicode=True, colors=8, blocks=True, color_pairs=64),
            RenderCapabilities(colors=256, backgrounds=True, color_pairs=256),
            RenderCapabilities(unicode=True, colors=256, backgrounds=True, color_pairs=256),
        ):
            options = RenderOptions.resolve(caps, fill=True)
            with self.subTest(caps=caps):
                self.assertEqual(
                    get_style("raster").render(world, options).pixels,
                    render(world, options.unicode, options.fill).pixels,
                )
        output = []
        for name in ("classic", "raster"):
            stream = io.StringIO()
            with redirect_stdout(stream):
                main(["--style", name, "--snapshot", "--seed", "42", "--at", "0"])
            output.append(stream.getvalue())
        self.assertEqual(*output)
        self.assertTrue(output[1].isascii())

    def test_all_raster_frames_and_semantic_ui_fit_the_curses_pair_budget(self):
        backend = FakeCurses()
        renderer = TerminalRenderer(Screen(), "slide", "always", backend, fill=True)
        for name in SCENES:
            for at in SCENES[name].times:
                frame = get_style("raster").render(make_scene(name, at=at), OPTIONS)
                frame.text(0, 0, "? help", Ink.TEXT)
                renderer.draw(frame)
        self.assertTrue(renderer.fill)
        self.assertLessEqual(max(p[0] for p in backend.pairs), len(Ink) + len(COLORS) ** 2)
        self.assertLess(max(p[0] for p in backend.pairs), 256)
        self.assertLessEqual(len(renderer._pairs), 196)

    def test_pair_failure_disables_raster_and_forces_a_complete_repaint(self):
        class Refusing(FakeCurses):
            def init_pair(self, number, *args):
                if number > len(Ink):
                    raise self.error()
                super().init_pair(number, *args)

        renderer = TerminalRenderer(Screen(), "slide", "always", Refusing(), fill=True)
        world = make_scene("overlap")
        renderer.draw(get_style("raster").render(world, OPTIONS))
        self.assertFalse(renderer.fill)
        self.assertIsNone(renderer.previous)
        next_frame = get_style("raster").render(
            world, RenderOptions.resolve(renderer.capabilities(True), fill=True)
        )
        self.assertTrue(
            all(p.color is None and p.background is None for row in next_frame.pixels for p in row)
        )

    def test_indexed_color_changes_redraw_and_ui_clears_indexed_tiles(self):
        renderer = TerminalRenderer(Screen(), "slide", "always", FakeCurses(), fill=True)
        before = Frame(3, 1, True)
        before.indexed(0, 0, "▀", 175, 255, Ink.RED)
        renderer.draw(before)
        renderer.screen.writes.clear()
        changed = Frame(3, 1, True)
        changed.indexed(0, 0, "▀", 217, 255, Ink.RED)
        renderer.draw(changed)
        self.assertEqual([write[:3] for write in renderer.screen.writes], [(0, 0, "▀")])
        changed.text(0, 0, "?")
        self.assertIsNone(changed.pixels[0][0].color)
        self.assertIsNone(changed.pixels[0][0].background)
        with self.assertRaises(ValueError):
            changed.indexed(0, 0, " ", 256, 0)
        with self.assertRaises(ValueError):
            Frame(1, 1).indexed(0, 0, " ", 0, 0)

    def test_division_dissolves_nuclei_and_reforms_two_bodies(self):
        count = []
        for at in (0, 11.99, 22, 46):
            world = make_scene("division", at=at)
            field = Field(100, 40)
            nuclei(field, world.cells[0])
            count.append(sum(role == Ink.NUCLEUS.value for role in field.roles))
        self.assertGreater(count[0], 0)
        self.assertLess(count[1], count[0])
        self.assertEqual(count[2], 0)
        self.assertGreater(count[3], count[0])

    def test_genetic_activity_and_assembly_keep_their_lifecycle_marks(self):
        for name, at, roles in (
            ("division", 22, {Ink.SPINDLE, Ink.DNA}),
            ("infection", 18, {Ink.PHAGE, Ink.VIRAL_DNA}),
            ("infection", 24.3, {Ink.LYSIS}),
        ):
            frame = get_style("raster").render(make_scene(name, at=at), OPTIONS)
            seen = {p.ink for row in frame.pixels for p in row}
            self.assertTrue(roles <= seen, (name, at, seen))

    def test_tool_rupture_paints_fragments_and_rare_events_remain_pure(self):
        from terminal_cells.geometry import Target
        from terminal_cells.style_checks import check_style

        world = make_scene("overlap")
        world.lab.lyse(world, Target("cell", world.cells[0]), 50, 40)
        world.update()
        frame = check_style(get_style("raster"), world, OPTIONS)
        self.assertTrue(any(p.ink in (Ink.LYSIS, Ink.NUCLEUS) for row in frame.pixels for p in row))
        from terminal_cells import World

        for kind in ("net", "rotifer", "pipette"):
            specimen = World(120, 40, 42)
            if kind == "net":
                specimen.cells[0].kind = "neutrophil"
            self.assertTrue(specimen.events.start(specimen, kind))
            for age in (3, 8):
                specimen.events.active.age = age
                check_style(get_style("raster"), specimen, OPTIONS)

    def test_high_contrast_nuclear_sample_survives_color_quantization(self):
        glyph, foreground, background = tile((9, 9, 9, 9, 9, 9, 5, 8))
        self.assertNotEqual(glyph, " ")
        self.assertEqual(foreground, COLORS[8])
        self.assertIn(background, COLORS)
        labels = help_lines(legend=get_style("raster").legend)
        self.assertTrue(any("green" in label for label in labels))
        self.assertFalse(any("Rod bacterium: gold" in label for label in labels))
