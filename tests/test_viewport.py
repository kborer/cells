"""Optical scale is presentation state; input and biology stay in world units."""

from contextlib import redirect_stdout
import io
import math
import pickle
import unittest

from terminal_cells import Bacterium, Phage, World
from terminal_cells.capabilities import RenderCapabilities
from terminal_cells.cli import main
from terminal_cells.frame import Ink
from terminal_cells.geometry import hit_test, nuclear_bodies
from terminal_cells.interaction import Interaction
from terminal_cells.scenes import make_scene
from terminal_cells.style_checks import check_style
from terminal_cells.styles import RenderOptions, STYLES
from terminal_cells.viewport import Camera, CURRENT, Grid, MAGNIFICATIONS, projection


CAPS = RenderCapabilities(unicode=True, colors=256, backgrounds=True, blocks=True, color_pairs=256)
OPTIONS = RenderOptions.resolve(CAPS, fill=True)


def specimen():
    world = World(100, 40, 42, rare_events=False, complement=False)
    world.cells.clear()
    world.red_cells.clear()
    world.debris.clear()
    world.phages.clear()
    world.hyphae.clear()
    world.nutrients.clear()
    world.bacteria = {0: Bacterium(0, 50, 40, 0, 0, "rod", math.inf, math.inf)}
    return world


class ViewportTests(unittest.TestCase):
    def test_normal_projection_preserves_all_style_frames(self):
        world = make_scene("ingestion", at=6.9)
        for style in STYLES.values():
            frame = Camera(100, 40).render(style, world, OPTIONS)
            self.assertEqual(frame.pixels, style.render(world, OPTIONS).pixels)

    def test_each_style_is_pure_deterministic_and_viewport_sized_at_every_scale(self):
        world = make_scene("complement", at=12)
        before = pickle.dumps(world)
        for style in STYLES.values():
            for name in MAGNIFICATIONS:
                for caps in (CAPS, RenderCapabilities()):
                    with self.subTest(style=style.name, magnification=name, colors=caps.colors):
                        camera = Camera(80, 24, name, 45, 26)
                        check_style(
                            style, world, RenderOptions.resolve(caps, fill=True), camera=camera
                        )
        self.assertEqual(pickle.dumps(world), before)

    def test_detail_draws_new_anatomy_and_overview_uses_small_silhouettes(self):
        world = specimen()
        style = STYLES["classic"]
        widths, dna = [], []
        for name in MAGNIFICATIONS:
            frame = Camera(80, 24, name, 50, 40).render(style, world, RenderOptions())
            xs = [x for row in frame.pixels for x, p in enumerate(row) if p.char != " "]
            widths.append(max(xs) - min(xs) + 1)
            dna.append(sum(p.ink is Ink.MICROBIAL_DNA for row in frame.pixels for p in row))
        self.assertLessEqual(widths[0], 2)
        self.assertLess(widths[0], widths[1])
        self.assertGreater(widths[2], widths[1] * 2)
        self.assertGreater(dna[2], dna[1])

    def test_inspect_lyse_and_toolbar_use_the_projected_location(self):
        for name in MAGNIFICATIONS:
            world = specimen()
            camera = Camera(80, 24, name, 50, 40)
            interaction = Interaction(0, 0, camera=camera)
            interaction.click(world, 40, 12, 0)
            self.assertIs(interaction.selected.obj, world.bacteria[0])
            interaction.tool = 1
            interaction.click(world, 40, 23, 0)
            self.assertIn(0, world.bacteria, "toolbar must never lyse")
            interaction.click(world, 40, 12, 0)
            self.assertNotIn(0, world.bacteria)

    def test_feed_and_stir_use_inverse_projection(self):
        world = specimen()
        world.bacteria.clear()
        camera = Camera(80, 24, "detail", 50, 40)
        interaction = Interaction(0, 0, camera=camera, tool=2)
        interaction.click(world, 49, 15, 0)
        expected = camera.grid(world).world(49, 15)
        self.assertAlmostEqual(world.nutrients[-1].x, expected[0])
        self.assertAlmostEqual(world.nutrients[-1].y, expected[1])
        interaction.tool = 3
        interaction.click(world, 49, 15, 0)
        self.assertEqual((world.lab.stirs[-1].x, world.lab.stirs[-1].y), expected)

    def test_phage_selection_handles_subpixel_world_positions_at_detail_scale(self):
        world = specimen()
        world.bacteria.clear()
        obj = Phage(7, 50.25, 40.4)
        world.phages = {7: obj}
        camera = Camera(80, 24, "detail", 50, 40)
        interaction = Interaction(0, 0, camera=camera)
        interaction.click(world, *camera.grid(world).point(obj.x, obj.y), 0)
        self.assertIs(interaction.selected.obj, obj)

    def test_projection_context_restores_on_exception_and_frames_keep_their_grid(self):
        original = CURRENT.get()

        class Broken:
            def render(self, world, options):
                raise RuntimeError("drawing failed")

        with self.assertRaises(RuntimeError):
            Camera(40, 20, "detail").render(Broken(), specimen(), OPTIONS)
        self.assertIs(CURRENT.get(), original)
        grid = Grid(scale=3, left=10, top=20)
        with projection(grid):
            frame = STYLES["classic"].render(specimen(), RenderOptions())
        frame.point(12, 24, "*", Ink.TEXT)
        col, row = grid.point(12, 24)
        self.assertEqual(frame.pixels[row][col].char, "*")
        self.assertIs(CURRENT.get(), original)

    def test_nuclear_foreground_keeps_priority_over_captured_cargo_at_every_scale(self):
        world = make_scene("overlap")
        owner = world.cells[0]
        for name in MAGNIFICATIONS:
            camera = Camera(100, 40, name, owner.x, owner.y)
            grid = camera.grid(world)
            with projection(grid):
                x, y, _, _ = next(nuclear_bodies(owner))
            target = hit_test(world, *grid.point(x, y), grid=grid)
            self.assertIsNotNone(target)
            self.assertIs(target.obj, owner)

    def test_pan_is_bounded_and_does_not_mutate_simulation(self):
        world = specimen()
        before = pickle.dumps(world)
        camera = Camera(80, 24, "detail")
        for _ in range(100):
            camera.pan(world, -1, 1)
        grid = camera.grid(world)
        self.assertGreaterEqual(grid.left, 0)
        self.assertLessEqual(grid.world(80, 24)[1], world.height + 1e-9)
        self.assertEqual(pickle.dumps(world), before)

    def test_snapshot_modes_are_ascii_and_keep_requested_terminal_dimensions(self):
        for name in MAGNIFICATIONS:
            stream = io.StringIO()
            with redirect_stdout(stream):
                result = main(
                    [
                        "--snapshot",
                        "--size",
                        "60x20",
                        "--at",
                        "0",
                        "--seed",
                        "42",
                        "--magnification",
                        name,
                    ]
                )
            self.assertEqual(result, 0)
            lines = stream.getvalue().splitlines()
            self.assertEqual(len(lines), 20)
            self.assertTrue(all(len(line) == 60 for line in lines))
            self.assertTrue(stream.getvalue().isascii())

    def test_invalid_projection_parameters_are_rejected(self):
        for value in (0, -1, math.inf, math.nan):
            with self.assertRaises(ValueError):
                Grid(scale=value)
