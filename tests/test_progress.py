"""Regression checks for lifecycle progress, beyond finite population counts."""

import math
import unittest

from terminal_cells import Bacterium, Cell, State, STEP, World
from terminal_cells.models import Entry
from tools.endurance import Progress


class ProgressTests(unittest.TestCase):
    def world(self):
        world = World(80, 24, 42, rare_events=False, complement=False)
        for name in ("cells", "red_cells", "debris", "hyphae", "nutrients", "bacteria", "phages"):
            getattr(world, name).clear()
        return world

    def test_clear_body_inside_can_finish_before_a_blocked_staging_point(self):
        world = self.world()
        host = Bacterium(0, 6, 10, 0, 2, "rod", math.inf, math.inf, entry=Entry(0, 14, 20, 10))
        world.cells = [Cell(1, 25, 10, 5, 0, 0)]
        world._advance_entry(host, STEP)
        self.assertIsNone(host.entry)
        self.assertEqual((host.x, host.y), (6, 10))
        self.assertEqual(world.entry_completions, 1)

    def test_blocked_route_recovers_without_jumping_visible_positions(self):
        world = self.world()
        host = Bacterium(0, -10, 24, 0, 2, "rod", math.inf, math.inf, entry=Entry(0, 22, 12, 24))
        world.cells = [Cell(1, 5, 24, 14, 0, 0)]
        world.bacteria = {0: host}
        moved = False
        for _ in range(5400):
            before = host.x, host.y
            retries = world.entry_retries
            world.time += STEP
            world._advance_entry(host, STEP)
            if world.entry_retries == retries:
                self.assertLessEqual(math.dist(before, (host.x, host.y)), 2 * STEP + 1e-7)
            moved |= math.dist(before, (host.x, host.y)) > 0
            if host.entry is None:
                break
        self.assertTrue(moved)
        self.assertIsNone(
            host.entry, "an obstructed staging point must not freeze arrivals forever"
        )
        self.assertFalse(world.is_blocked(host.x, host.y, world._entry_padding(host)))

    def test_duplicate_immune_cell_leaves_to_make_room_for_missing_kind(self):
        world = self.world()
        world.cells = [Cell(0, 25, 24, 8, 0, 0), Cell(1, 60, 24, 8, 0, 0)]
        world.time = 200
        world.large_arrival_at = world.replenish_at = 0
        world.fungal_arrival_at = math.inf
        world._update_arrivals()
        departing = [c for c in world.cells if c.entry and c.entry.exiting]
        self.assertEqual(len(departing), 1)
        self.assertTrue(all(c.kind == "macrophage" for c in world.cells))
        for _ in range(3600):
            world.time += STEP
            world._update_cell(departing[0], STEP)
            if departing[0] not in world.cells:
                break
        self.assertEqual(len(world.cells), 1)
        world.large_arrival_at = world.replenish_at = 0
        world._update_arrivals()
        self.assertEqual({c.kind for c in world.cells}, {"macrophage", "neutrophil"})
        self.assertLessEqual(len(world.cells), world._limits()[0])
        replacement = next(c for c in world.cells if c.kind == "neutrophil")
        self.assertIsNotNone(replacement.entry)
        self.assertTrue(
            replacement.x < 0
            or replacement.x > world.width
            or replacement.y < 0
            or replacement.y > world.height
        )

    def test_overdue_replacement_reservation_prevents_another_division(self):
        world = self.world()
        cell = Cell(0, 40, 24, 8, 0, 0, divide_at=0)
        world.cells = [cell]
        world.time = 200
        world._update_cell(cell, STEP)
        self.assertIsNot(cell.state, State.DIVIDE)

    def test_resize_preserves_departure_direction_and_eventual_exit(self):
        for angle in (0, math.pi / 2, math.pi, -math.pi / 2):
            with self.subTest(angle=angle):
                world = self.world()
                cell = Cell(
                    0,
                    40,
                    24,
                    8,
                    0,
                    angle,
                    entry=Entry(angle, 1, 0, 0, age=10, exiting=True, retry=False),
                )
                world.cells = [cell]
                world.resize(100, 40)
                world.red_cells.clear()
                self.assertEqual(cell.entry.angle, angle)
                self.assertEqual(cell.entry.age, 10)
                for _ in range(2400):
                    before = cell.x, cell.y
                    world._update_cell(cell, STEP)
                    self.assertLessEqual(math.dist(before, (cell.x, cell.y)), 2.6 * STEP + 1e-7)
                    if cell not in world.cells:
                        break
                self.assertNotIn(cell, world.cells)

    def test_endurance_detects_stalled_entries_and_lost_immune_diversity(self):
        world = self.world()
        progress = Progress(world)
        host = Bacterium(
            0, -10, 24, 0, 2, "rod", math.inf, math.inf, entry=Entry(0, 22, 12, 24, age=181)
        )
        world.bacteria = {0: host}
        with self.assertRaisesRegex(AssertionError, "Stalled edge crossing"):
            progress.observe(world)
        host.entry = None
        world.time = 601
        with self.assertRaisesRegex(AssertionError, "diversity did not recover"):
            progress.observe(world)

    def test_endurance_distinguishes_an_eligible_stalled_bud_from_capacity_pause(self):
        world = self.world()
        world.density = 0.25
        host = Bacterium(0, 20, 20, 0, 0, "yeast", math.inf, 0, bud=0.1)
        world.bacteria = {0: host}
        progress = Progress(world)
        progress.observe(world)
        world.time = 31
        with self.assertRaisesRegex(AssertionError, "Eligible bud stopped growing"):
            progress.observe(world)
        # Being held by the footprint budget is a legitimate pause.
        world.bacteria.update(
            {i: Bacterium(i, 50, 20, 0, 0, "yeast", math.inf, 0) for i in (1, 2, 3)}
        )
        progress.observe(world)
