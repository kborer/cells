"""Compact phages retain orientation, close contact, and visible lifecycles."""

import math
import unittest
from unittest.mock import patch

from terminal_cells import Bacterium, Cell, Frame, Ink, Phage, World, STEP, draw_phage
from terminal_cells.models import (
    CELL_RADIUS,
    NEUTROPHIL_RADIUS,
    PHAGE_PADDING,
    Infection,
    phage_contact_distance,
    phage_geometry,
)
from terminal_cells.render import draw_infection


class ScaleTests(unittest.TestCase):
    def empty_world(self):
        world = World(160, 60, 42)
        world.cells.clear()
        world.red_cells.clear()
        world.debris.clear()
        world.bacteria.clear()
        world.phages.clear()
        return world

    def test_macrophages_grow_without_enlarging_neutrophils(self):
        world = self.empty_world()
        world._add_cell(0, 2, "macrophage")
        world._add_cell(1, 2, "neutrophil")
        macrophage, neutrophil = world.cells
        self.assertAlmostEqual(CELL_RADIUS / NEUTROPHIL_RADIUS, 16.5 / 14)
        self.assertTrue(15.5 <= macrophage.radius <= 17.5)
        self.assertTrue(13 <= neutrophil.radius <= 15)
        world.resize(200, 70)
        self.assertEqual(macrophage.radius, CELL_RADIUS)
        self.assertEqual(neutrophil.radius, NEUTROPHIL_RADIUS)
        world.resize(40, 12)
        for cell in world.cells:
            self.assertLessEqual(cell.radius, min(world.width * 0.18, world.height * 0.25))

    def test_directional_sprites_remain_one_or_two_characters(self):
        for unicode in (False, True):
            for angle, expected in (
                (0, "-<"),
                (math.pi, ">-"),
                (-math.pi / 2, "ᛘ" if unicode else "Y"),
                (math.pi / 2, "ᛦ" if unicode else "Y"),
            ):
                for x in (20, 20.3, 20.8):
                    frame = Frame(45, 20)
                    draw_phage(frame, Phage(0, x, 20, angle=angle), unicode)
                    pixels = [p for row in frame.pixels for p in row if p.char != " "]
                    self.assertEqual("".join(p.char for p in pixels), expected)
                    self.assertTrue(all(p.ink is Ink.PHAGE for p in pixels))
                    if not unicode:
                        self.assertTrue(frame.plain().isascii())

    def test_empty_shell_is_dim_and_contraction_still_changes_geometry(self):
        phage = Phage(0, 20, 20, angle=0)
        sizes = []
        for contraction in (0, 0.5, 1):
            head, tip = phage_geometry(phage, contraction)
            sizes.append(math.dist(head, tip))
            self.assertLessEqual(math.dist(head, (phage.x, phage.y)), PHAGE_PADDING)
            frame = Frame(40, 20)
            draw_phage(frame, phage, True, contraction, empty=True)
            self.assertTrue(
                all(
                    p.ink is Ink.MUTED and not p.bold
                    for row in frame.pixels
                    for p in row
                    if p.char != " "
                )
            )
        self.assertEqual(sizes, sorted(sizes, reverse=True))
        self.assertGreater(sizes[0], sizes[-1])

    def test_phage_waits_for_contact_with_the_near_side_of_a_long_host(self):
        world = self.empty_world()
        host = Bacterium(0, 60, 40, 0, 0, "spirochete", 999, 999)
        world.bacteria = {0: host}
        contact = phage_contact_distance(host, math.pi / 2)
        self.assertAlmostEqual(contact, 1.7 + PHAGE_PADDING)
        self.assertAlmostEqual(phage_contact_distance(host, 0), 7 + PHAGE_PADDING)
        phage = Phage(0, 60, 40 + contact + 0.1)
        world.phages = {0: phage}
        with patch.object(world.rng, "random", return_value=0) as roll:
            world._update_phages(STEP)
            self.assertFalse(roll.called, "nearby empty space must not count as a collision")
            phage.y -= 0.2
            world._update_phages(STEP)
            self.assertEqual(roll.call_count, 1)
        self.assertIsNotNone(host.infection)
        self.assertFalse(world.phages)

    def test_compact_phage_can_rest_close_to_a_membrane(self):
        world = self.empty_world()
        cell = Cell(0, 40, 40, 12, 0, 0)
        world.cells = [cell]
        x = cell.x + cell.outline(0, world.time) + PHAGE_PADDING + 0.1
        phage = Phage(0, x, 40)
        world.phages = {0: phage}
        world._resolve_obstacles()
        self.assertAlmostEqual(phage.x, x)
        self.assertAlmostEqual(phage.y, 40)

    def test_orientation_does_not_propel_free_phages_in_still_fluid(self):
        world = self.empty_world()
        world.current = lambda x, y: (0, 0)
        host = Bacterium(0, 60, 40, 0, 0, "rod", 999, 999)
        phage = Phage(0, 60, 32, angle=0)
        world.bacteria = {0: host}
        world.phages = {0: phage}
        world._update_phages(STEP)
        self.assertEqual((phage.x, phage.y), (60, 32))
        self.assertAlmostEqual(phage.angle, math.pi / 2)

    def test_compact_lifecycle_still_shows_injection_replication_and_assembly(self):
        for age, ink in ((5, Ink.VIRAL_DNA), (10, Ink.VIRAL_DNA), (18, Ink.PHAGE)):
            host = Bacterium(0, 30, 20, 0, 0, "rod", 999, 999, infection=Infection(age))
            frame = Frame(60, 20)
            draw_infection(frame, host, True, lambda along, across: (30 + along, 20 + across))
            self.assertTrue(
                any(p.ink is ink and p.char != " " for row in frame.pixels for p in row)
            )
            if age == 18:
                self.assertTrue(any(p.char in "ᛘᛦ" for row in frame.pixels for p in row))
