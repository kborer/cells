"""Footprint-aware growth, placement, and soft clearances."""

import math
import unittest

from terminal_cells import Bacterium, World
from terminal_cells.catalog import MICROBE_KINDS
from terminal_cells.crowding import Neighbors, area, budget, occupied, place, tail_fraction


def organism(ident, x=20, y=20, kind="rod"):
    return Bacterium(ident, x, y, 0, 1, kind, math.inf, 0)


class CrowdingTests(unittest.TestCase):
    def test_population_profile_accounts_for_shapes_and_growing_chains(self):
        world = World(200, 60, 42)
        capacities = []
        for kind in ("coccus", "spirochete"):
            world.microbe_weights = [1 if k == kind else 0 for k in MICROBE_KINDS]
            capacities.append(world._limits()[1])
        self.assertGreater(capacities[0], capacities[1])
        self.assertGreater(area("bacillus", units=5), area("bacillus", units=2))
        self.assertGreater(area("yeast", bud=1), area("yeast", bud=0))

    def test_growth_waits_for_footprint_room_and_resumes_after_cleanup(self):
        world = World(80, 24, 42, rare_events=False)
        world.cells.clear()
        world.bacteria = {i: organism(i, kind="bacillus") for i in range(18)}
        parent = world.bacteria[0]
        parent.units = 5
        before = len(world.bacteria)
        self.assertGreater(occupied(world), budget(world))
        world._reproduce_microbe(parent, 1, 100)
        self.assertEqual(len(world.bacteria), before)
        world.bacteria = {0: parent}
        world._reproduce_microbe(parent, 1, 100)
        self.assertEqual(len(world.bacteria), 2)

    def test_soft_spacing_is_bounded_and_does_not_move_claimed_prey(self):
        world = World(80, 24, 42, rare_events=False)
        world.bacteria = {0: organism(0), 1: organism(1)}
        index = Neighbors(world)
        a, b = (index.drift(obj) for obj in world.bacteria.values())
        self.assertLess(a[0], 0)
        self.assertGreater(b[0], 0)
        self.assertLessEqual(math.hypot(*a), 1)
        world.bacteria[0].owner = 7
        self.assertEqual(index.drift(world.bacteria[0]), (0, 0))

    def test_seeded_placement_finds_a_gap_without_mutating_other_entities(self):
        world = World(80, 24, 42, rare_events=False)
        world.cells.clear()
        world.red_cells.clear()
        world.events.active = None
        left, right = organism(0, kind="spirochete"), organism(1)
        world.bacteria = {0: left, 1: right}
        before = repr(left)
        place(world, right)
        self.assertEqual(repr(left), before)
        self.assertGreater(math.hypot(right.x - left.x, right.y - left.y), 10)

    def test_tight_footprint_budget_can_rotate_unique_species_without_teleporting(self):
        world = World(80, 24, 42, rare_events=False, complement=False)
        world.cells.clear()
        world.red_cells.clear()
        world.bacteria = {
            i: organism(i, kind=k)
            for i, k in enumerate(("rod", "spirochete", "bacillus", "colony"))
        }
        for obj in world.bacteria.values():
            obj.swelling = 3
        world.time, world.replenish_at = 100, 0
        world.fungal_arrival_at = world.large_arrival_at = math.inf
        world.next_id = 4
        world._update_arrivals()
        self.assertEqual(len(world.bacteria), 4)
        self.assertEqual(sum(b.leaving for b in world.bacteria.values()), 1)
        self.assertEqual(world.arrivals, 0)

    def test_tail_shortening_depends_on_direction_and_remains_pure(self):
        world = World(80, 24, 42, rare_events=False)
        host, neighbor = organism(0, 30), organism(1, 23)
        world.bacteria = {0: host, 1: neighbor}
        before, rng = repr(world.bacteria), world.rng.getstate()
        self.assertLess(tail_fraction(world, host), 1)
        self.assertEqual(repr(world.bacteria), before)
        self.assertEqual(world.rng.getstate(), rng)
        neighbor.x = 37
        self.assertEqual(tail_fraction(world, host), 1)
