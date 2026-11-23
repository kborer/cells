"""The experimental style must preserve anatomy, effects, and terminal fallbacks."""

from contextlib import redirect_stdout
import io
import unittest

from terminal_cells.capabilities import RenderCapabilities
from terminal_cells.cli import TerminalRenderer, main
from terminal_cells.frame import FILL_INKS, Ink, PALETTES
from terminal_cells.microscopy import BLOCKS, tile
from terminal_cells.models import Drifter
from terminal_cells.render import render
from terminal_cells.scenes import make_scene, SCENES
from terminal_cells.styles import get_style, RenderOptions
from test_terminal import FakeCurses, Screen


CAPS = RenderCapabilities(unicode=True, colors=256, backgrounds=True, blocks=True, color_pairs=256)
OPTIONS = RenderOptions.resolve(CAPS, fill=True)


class MicroscopyTests(unittest.TestCase):
    def test_opt_in_style_uses_blocks_and_does_not_change_classic_default(self):
        self.assertEqual(get_style().name, "classic")
        self.assertFalse(get_style().default_fill)
        style = get_style("microscopy")
        self.assertTrue(style.default_fill)
        world = make_scene("ingestion", at=9)
        frame = style.render(world, OPTIONS)
        self.assertNotEqual(frame.pixels, render(world, True, True).pixels)
        self.assertTrue(any(p.char in BLOCKS[1:15] for row in frame.pixels for p in row))
        self.assertTrue(all(p.bg is None or p.bg in FILL_INKS for row in frame.pixels for p in row))

    def test_fallbacks_preserve_classic_frames(self):
        world = make_scene("overlap")
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
                    get_style("microscopy").render(world, options).pixels,
                    render(world, options.unicode, options.fill).pixels,
                )
        outputs = []
        for style in ("classic", "microscopy"):
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(
                    main(["--style", style, "--snapshot", "--at", "0", "--seed", "42"]), 0
                )
            outputs.append(output.getvalue())
        self.assertEqual(*outputs)
        self.assertTrue(outputs[1].isascii())

    def test_lifecycle_foreground_glyphs_are_preserved(self):
        protected = {
            Ink.MITOCHONDRION,
            Ink.RETICULUM,
            Ink.NUCLEOLUS,
            Ink.DNA,
            Ink.SPINDLE,
            Ink.CAPTURE,
            Ink.VESICLE,
            Ink.PHAGE,
            Ink.VIRAL_DNA,
            Ink.LYSIS,
            Ink.BACTERIA,
            Ink.COCCUS,
            Ink.SPIRAL,
            Ink.BACILLUS,
            Ink.SPIROCHETE,
            Ink.VIBRIO,
            Ink.COLONY,
            Ink.YEAST,
            Ink.TRYPANOSOME,
        }
        seen = set()
        for scene in ("division", "ingestion", "infection"):
            for at in SCENES[scene].times:
                world = make_scene(scene, at=at)
                classic = render(world, True, True)
                stained = get_style("microscopy").render(world, OPTIONS)
                for y, row in enumerate(classic.pixels):
                    for x, pixel in enumerate(row):
                        if pixel.char != " " and pixel.ink in protected:
                            with self.subTest(scene=scene, at=at, ink=pixel.ink):
                                self.assertEqual(stained.pixels[y][x], pixel)
                            seen.add(pixel.ink)
        self.assertTrue({Ink.NUCLEOLUS, Ink.DNA, Ink.SPINDLE, Ink.VIRAL_DNA, Ink.LYSIS} <= seen)

    def test_red_cells_have_pale_centers_and_keep_clear_space_between_bodies(self):
        world = make_scene("infection")
        world.bacteria.clear()
        world.red_cells = [Drifter(30, 40, 0, 6), Drifter(60, 40, 0, 6)]
        frame = get_style("microscopy").render(world, OPTIONS)
        self.assertIs(frame.pixels[20][30].bg, Ink.FILL_RED_PALE)
        self.assertTrue(any(p.bg is Ink.FILL_RED for row in frame.pixels for p in row))
        self.assertTrue(
            all(
                frame.pixels[y][45].char == " " and frame.pixels[y][45].bg is None
                for y in range(frame.height)
            )
        )

    def test_stain_palette_is_applied_by_the_backend_without_changing_species_hues(self):
        style = get_style("microscopy")
        for theme in PALETTES:
            palette = style.palette(theme)
            self.assertEqual(len(palette), len(Ink))
            for ink in set(Ink) - set(FILL_INKS) - {Ink.CYTOPLASM}:
                self.assertEqual(palette[ink.value - 1], PALETTES[theme][ink.value - 1])
            if theme != "mono":
                self.assertNotEqual(palette, PALETTES[theme])
        backend = FakeCurses()
        renderer = TerminalRenderer(
            Screen(), "light", "always", backend, fill=True, palette=style.palette("light")
        )
        self.assertIn(
            (Ink.FILL_RED.value, style.palette("light")[Ink.FILL_RED.value - 1][0], -1),
            backend.pairs,
        )
        self.assertTrue(renderer.fill)
        renderer.draw(style.render(make_scene("crowding"), OPTIONS))
        self.assertLessEqual(max(pair[0] for pair in backend.pairs), 255)
        self.assertTrue(renderer.fill)

    def test_quarter_tile_coverage_and_tint_budget(self):
        for mask in range(1, 15):
            samples = [Ink.FILL_CYTOPLASM if mask & (1 << i) else None for i in range(4)]
            char, foreground, background = tile(samples)
            self.assertEqual(char, BLOCKS[mask])
            self.assertIs(foreground, Ink.FILL_CYTOPLASM)
            self.assertIsNone(background)
        for samples in (
            [Ink.NUCLEUS] * 4,
            [Ink.FILL_NUCLEUS, Ink.NUCLEUS, Ink.FILL_CYTOPLASM, Ink.CYTOPLASM],
        ):
            _, _, background = tile(samples)
            self.assertTrue(background is None or background in FILL_INKS)
