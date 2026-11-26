"""Ambient flow moves suspended matter without detaching anchored structures."""

import copy
import math
import unittest

from terminal_cells import World
from terminal_cells.geometry import Target
from terminal_cells.lab import Fragment, Rupture
from terminal_cells.models import Bacterium, Drifter, Phage, Nutrient, STEP
from terminal_cells.scenes import make_scene


def flowing(x, y):
    return 2, 0


def still(x, y):
    return 0, 0


class FlowTests(unittest.TestCase):
    def test_suspended_entities_and_rupture_debris_share_ambient_flow(self):
        world = World(220, 60, 42, rare_events=False)
        world.cells.clear()
        world.hyphae.clear()
        world.replenish_at = world.large_arrival_at = world.phage_replenish_at = math.inf
        world.nutrient_at = world.fungal_arrival_at = math.inf
        world.current = flowing
        microbe = Bacterium(0, 20, 60, 0, 0, "coccus", math.inf, math.inf)
        red = Drifter(55, 60, 0, 5)
        debris = Drifter(85, 60, 0, 1)
        phage = Phage(0, 115, 60)
        capsid = Phage(-1, 145, 60, lifetime=18)
        piece = Fragment(175, 60, 0, 0, "microbe", "-")
        food = Nutrient(200, 60)
        world.bacteria = {0: microbe}
        world.red_cells, world.debris = [red], [debris]
        world.phages, world.spent_capsids = {0: phage}, [capsid]
        world.nutrients = [food]
        world.lab.ruptures = [Rupture(Target("microbe", microbe), 175, 60, 0, 3, fragments=[piece])]
        objects = [microbe, red, debris, phage, capsid, piece]
        starts = [obj.x for obj in objects]
        for _ in range(30):
            world.update(STEP)
        for obj, start in zip(objects, starts):
            with self.subTest(kind=type(obj).__name__):
                self.assertAlmostEqual(obj.x, start + 2)
        self.assertAlmostEqual(food.x, 200.6)  # Existing slower cloud advection.

    def test_flow_does_not_detach_a_plug_or_advect_tissue(self):
        world = make_scene("platelet-plug", at=14)
        control = copy.deepcopy(world)
        world.current, control.current = flowing, still
        self.assertTrue(any(p.phase == "adhered" for p in world.vessel.platelets))
        for _ in range(30):
            world.update()
            control.update()
        self.assertEqual(world.vessel.endothelium, control.vessel.endothelium)
        self.assertEqual(world.vessel.fibroblasts, control.vessel.fibroblasts)

        def bound(w):
            return [(p.id, p.x, p.y) for p in w.vessel.platelets if p.phase == "adhered"]

        self.assertEqual(bound(world), bound(control))
