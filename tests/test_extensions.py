"""Contributor contracts exercised against every registered style and staged scene."""

from dataclasses import replace
import io
import importlib
import math
import pickle
from contextlib import redirect_stderr
from unittest.mock import patch
import unittest
import xml.etree.ElementTree as ET

from terminal_cells.capabilities import RenderCapabilities
from terminal_cells.catalog import MICROBES, MICROBE_KINDS, BACTERIAL_KINDS, PHAGE_HOST_KINDS
from terminal_cells.frame import Frame, Ink
from terminal_cells.geometry import cell_contains, hit_test, nuclear_contains
from terminal_cells.models import Bacterium, State, microbe_axes
from terminal_cells.render import BACTERIA_INKS, draw_nucleus
from terminal_cells.scenes import SCENES, make_scene
from terminal_cells.style_checks import check_style, check_world_retention
from terminal_cells.styles import CacheInfo, ClassicStyle, RenderOptions, STYLES
from tools.gallery import main as gallery_main, svg


PROFILES = (
    RenderCapabilities(),
    RenderCapabilities(unicode=True),
    RenderCapabilities(colors=8, color_pairs=64),
    RenderCapabilities(unicode=True, colors=256, blocks=True, color_pairs=256),
    RenderCapabilities(unicode=True, colors=256, backgrounds=True, blocks=True, color_pairs=256),
    RenderCapabilities(colors=256, backgrounds=True, color_pairs=256),
)


class ExtensionTests(unittest.TestCase):
    def test_registered_styles_meet_contract_across_scene_samples_and_fallbacks(self):
        for name, scene in SCENES.items():
            for at in scene.times:
                world = make_scene(name, at=at)
                for style in STYLES.values():
                    for caps in PROFILES:
                        with self.subTest(scene=name, at=at, style=style.name, caps=caps):
                            check_style(style, world, RenderOptions.resolve(caps, fill=True))
        for style in STYLES.values():
            for size in ((1, 1), (32, 12), (160, 50)):
                world = make_scene("crowding")
                world.resize(*size)
                check_style(style, world, RenderOptions.resolve(RenderCapabilities()))
            check_world_retention(style, lambda: make_scene("overlap"), RenderOptions())

    def test_contract_rejects_mutation_bad_fallbacks_and_unbounded_caches(self):
        class Mutating(ClassicStyle):
            def render(self, world, options):
                world.rng.random()
                return super().render(world, options)

        class UnicodeOnly(ClassicStyle):
            def render(self, world, options):
                frame = super().render(world, options)
                frame.text(0, 0, "▀")
                return frame

        class Unbounded(ClassicStyle):
            def cache_info(self):
                return {"sprites": CacheInfo(10, 0)}

        for style, message in (
            (Mutating(), "world"),
            (UnicodeOnly(), "ASCII"),
            (Unbounded(), "Unbounded"),
        ):
            with (
                self.subTest(style=type(style).__name__),
                self.assertRaisesRegex(AssertionError, message),
            ):
                check_style(style, make_scene("overlap"), RenderOptions())

    def test_contract_rejects_unavailable_block_shapes(self):
        class BlocksOnly(ClassicStyle):
            def render(self, world, options):
                frame = super().render(world, options)
                frame.text(0, 0, "▀")
                return frame

        with self.assertRaisesRegex(AssertionError, "block-glyph"):
            check_style(
                BlocksOnly(),
                make_scene("overlap"),
                RenderOptions.resolve(RenderCapabilities(unicode=True)),
            )

    def test_world_retention_check_rejects_a_leaking_style(self):
        class Leaking:
            def render(self, world, options):
                self.world = world
                return Frame(100, 40)

        with self.assertRaisesRegex(AssertionError, "retained"):
            check_world_retention(Leaking(), lambda: make_scene("overlap"), RenderOptions())

    def test_capabilities_negotiate_plain_basic_and_filled_output(self):
        for caps in PROFILES:
            result = RenderOptions.resolve(caps, fill=True)
            self.assertEqual(result.unicode, caps.unicode)
            self.assertEqual(result.fill, caps.backgrounds)
            self.assertIs(result.capabilities, caps)
        for kwargs in (
            {"colors": 24},
            {"blocks": True},
            {"backgrounds": True},
            {"color_pairs": -1},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                RenderCapabilities(**kwargs)
        with self.assertRaises(ValueError):
            RenderOptions(True, False, RenderCapabilities())
        with self.assertRaises(ValueError):
            RenderOptions(False, True, RenderCapabilities())

    def test_catalog_is_keyed_immutable_and_complete_for_classic_art(self):
        self.assertEqual(set(MICROBES), set(BACTERIA_INKS))
        self.assertEqual(tuple(MICROBES), MICROBE_KINDS)
        self.assertEqual(BACTERIAL_KINDS, frozenset(k for k, v in MICROBES.items() if v.bacterial))
        self.assertEqual(
            PHAGE_HOST_KINDS, frozenset(k for k, v in MICROBES.items() if v.phage_host)
        )
        self.assertLessEqual(PHAGE_HOST_KINDS, BACTERIAL_KINDS)
        with self.assertRaises(TypeError):
            MICROBES["new"] = MICROBES["rod"]
        for kind, spec in MICROBES.items():
            with self.subTest(kind=kind):
                self.assertTrue(spec.label)
                self.assertGreaterEqual(spec.speed, 0)
                self.assertIn(spec.reproduction, ("fission", "budding", "segmented"))
                self.assertIn(spec.split_axis, (0, 1))
                if spec.reproduction == "budding":
                    self.assertGreater(spec.bud_seconds, 0)
                for units in (1, 3, 5):
                    microbe = Bacterium(
                        0, 0, 0, 0, 0, kind, math.inf, math.inf, units=units, bud=0.5
                    )
                    self.assertTrue(all(a > 0 for a in microbe_axes(microbe)))
        bacillus = Bacterium(0, 0, 0, 0, 0, "bacillus", math.inf, math.inf)
        self.assertEqual(microbe_axes(bacillus), (2.4 + (bacillus.units - 1) * 1.7, 1.7))

    def test_geometry_queries_are_pure_and_selection_never_calls_a_renderer(self):
        world = make_scene("overlap")
        before = pickle.dumps(world)
        original_cells = world.cells
        cell = world.cells[0]
        self.assertTrue(cell_contains(cell, cell.x, cell.y, world.time))
        self.assertTrue(world.is_blocked(cell.x, cell.y))
        self.assertFalse(world.is_blocked(cell.x, cell.y, exempt=cell.id))
        self.assertEqual(list(world.obstacles(50, 40)), list(world._obstacles(50, 40, 0)))
        for cell in (cell, replace(cell, kind="neutrophil")):
            world.cells = [cell]
            frame = Frame(100, 40)
            draw_nucleus(frame, cell, False)
            # Python 3.10 mock.patch follows package attributes, where the
            # compatibility export named "render" shadows the render module.
            with patch.object(
                importlib.import_module("terminal_cells.render"),
                "render",
                side_effect=AssertionError("rendering during selection"),
            ):
                for row, pixels in enumerate(frame.pixels):
                    for col, pixel in enumerate(pixels):
                        if pixel.ink in (Ink.NUCLEUS, Ink.NUCLEOLUS):
                            self.assertTrue(nuclear_contains(cell, col, row))
                            self.assertIs(hit_test(world, col, row).obj, cell)
        world.cells = original_cells
        # Compare an independent query pass to catch geometry/RNG mutation.
        snapshot = pickle.dumps(world)
        list(world.obstacles(45, 40))
        hit_test(world, 50, 20)
        self.assertEqual(snapshot, pickle.dumps(world))
        self.assertEqual(before, pickle.dumps(world))

    def test_scene_fixtures_reproduce_and_reach_the_advertised_events(self):
        for name in SCENES:
            a, b = make_scene(name, at=3), make_scene(name, at=3)
            self.assertEqual(pickle.dumps(a), pickle.dumps(b))
        self.assertEqual(make_scene("division", at=51).divisions, 1)
        self.assertGreater(make_scene("ingestion", at=12).engulfed, 0)
        self.assertGreater(make_scene("infection", at=24.3).lysed, 0)
        self.assertEqual(make_scene("overlap").cells[0].state, State.ENCLOSE)
        for at in (-1, math.nan, math.inf, 61):
            with self.assertRaises(ValueError):
                make_scene("division", at=at)
        with self.assertRaises(ValueError):
            make_scene("missing")

    def test_gallery_svg_includes_backgrounds_and_rejects_invalid_times(self):
        frame = Frame(2, 1, fill=True)
        frame.put(0, 0, "<", Ink.TEXT, bg=Ink.FILL_RED)
        root = ET.fromstring(svg([("one & two", frame)], "light"))
        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
        self.assertIn('width="9" height="18"', svg([("test", frame)], "light"))
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            gallery_main(["--at", "nan"])
