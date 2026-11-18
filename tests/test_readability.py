"""Regression checks for recognizable silhouettes and quiet compact views."""

import math
import unittest

from terminal_cells import (
    Bacterium,
    Cell,
    Drifter,
    Frame,
    Ink,
    World,
    draw_bacterium,
    draw_cell,
    render,
)
from terminal_cells.render import contour_pixels


class ReadabilityTests(unittest.TestCase):
    def test_background_depth_is_stable_and_ascii_without_changing_particles(self):
        world = World(80, 24, 42, rare_events=False)
        world.cells.clear()
        world.red_cells.clear()
        world.bacteria.clear()
        world.phages.clear()
        world.hyphae.clear()
        world.nutrients.clear()
        world.debris = [Drifter(10, 10, 0, 0.6), Drifter(20, 10, 0, 1.1)]
        before, rng = repr(world.debris), world.rng.getstate()
        for unicode in (False, True):
            frame = render(world, unicode)
            self.assertEqual(frame.pixels[5][10].ink, Ink.BACKGROUND_FAR)
            self.assertEqual(frame.pixels[5][20].ink, Ink.BACKGROUND_NEAR)
            self.assertEqual(frame.pixels[5][10].char, ".")
            self.assertEqual(frame.pixels[5][20].char, "·" if unicode else ":")
            self.assertEqual(frame.pixels[5][21].char, " ")
            if not unicode:
                self.assertTrue(frame.plain().isascii())
        self.assertEqual(repr(world.debris), before)
        self.assertEqual(world.rng.getstate(), rng)

    def test_cell_interior_occludes_both_background_depth_layers(self):
        world = World(80, 24, 42, rare_events=False)
        world.cells = [Cell(0, 40, 24, 12, 0, 0)]
        world.debris = [Drifter(46, 24, 0, 0.6), Drifter(47, 24, 0, 1.1)]
        for unicode in (False, True):
            frame = render(world, unicode)
            for x in (46, 47):
                self.assertNotIn(frame.pixels[12][x].ink, (Ink.BACKGROUND_FAR, Ink.BACKGROUND_NEAR))

    def test_lines_are_one_character_wide_in_every_octant(self):
        for dx, dy in (
            (8, 4),
            (4, 8),
            (-8, 4),
            (-4, 8),
            (8, -4),
            (4, -8),
            (-8, -4),
            (-4, -8),
            (0, 0),
        ):
            with self.subTest(delta=(dx, dy)):
                frame = Frame(30, 30)
                frame.line(15, 30, 15 + dx, 30 + 2 * dy, Ink.MEMBRANE)
                points = {
                    (x, y)
                    for y, row in enumerate(frame.pixels)
                    for x, p in enumerate(row)
                    if p.char != " "
                }
                self.assertEqual(len(points), max(abs(dx), abs(dy)) + 1)
                self.assertIn((15, 15), points)
                self.assertIn((15 + dx, 15 + dy), points)

    def test_small_closed_contours_keep_their_enclosed_silhouette(self):
        for radius in (1.35, 2.3, 5, 16):
            with self.subTest(radius=radius):
                path = contour_pixels(
                    [
                        (
                            20 + math.cos(i * math.tau / 128) * radius,
                            30 + math.sin(i * math.tau / 128) * radius,
                            i * math.tau / 128,
                        )
                        for i in range(129)
                    ]
                )
                points = {(x, y) for x, y, _ in path}
                self.assertGreaterEqual(len(points), 6)
                self.assertNotIn((20, 15), points)
                for (x, y, _), (xx, yy, _) in zip(path, path[1:]):
                    self.assertLessEqual(max(abs(x - xx), abs(y - yy)), 1)
                self.assertEqual(path[0][:2], path[-1][:2])

    def test_compact_view_quiets_anatomy_without_changing_nucleus_or_world(self):
        cell = Cell(0, 40, 34, 16, 0, 0)
        small, large = Frame(100, 32), Frame(120, 40)
        before = repr(cell)
        draw_cell(small, cell, 0, False)
        draw_cell(large, cell, 0, False)

        def count(frame, inks):
            return sum(p.char != " " and p.ink in inks for row in frame.pixels for p in row)

        self.assertLess(
            count(small, (Ink.RETICULUM, Ink.MITOCHONDRION)),
            count(large, (Ink.RETICULUM, Ink.MITOCHONDRION)),
        )
        for ink in (Ink.RETICULUM, Ink.MITOCHONDRION):
            self.assertGreater(count(small, (ink,)), 2)
        self.assertEqual(
            count(small, (Ink.NUCLEUS, Ink.NUCLEOLUS)), count(large, (Ink.NUCLEUS, Ink.NUCLEOLUS))
        )
        self.assertEqual(repr(cell), before)

    def test_coccal_colony_keeps_multiple_visible_beads(self):
        frame = Frame(40, 24)
        microbe = Bacterium(0, 20, 24, 0, 0, "colony", math.inf, math.inf)
        draw_bacterium(frame, microbe, False)
        self.assertGreater(
            sum(p.char != " " and p.ink is Ink.COLONY for row in frame.pixels for p in row), 15
        )

    def test_immune_cells_steer_apart_before_membranes_touch(self):
        world = World(160, 60, 42, rare_events=False)
        world.cells = [
            Cell(0, 50, 50, 10, 0, 0, cooldown=999),
            Cell(1, 72, 50, 10, 0, math.pi, cooldown=999),
        ]
        world.bacteria.clear()
        world.current = lambda x, y: (0, 0)
        before = world.cells[1].x - world.cells[0].x
        for cell in world.cells:
            world._update_cell(cell, 0.1)
        self.assertGreater(world.cells[1].x - world.cells[0].x, before)


if __name__ == "__main__":
    unittest.main()
