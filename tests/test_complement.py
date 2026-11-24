"""Selective membrane attack must coexist with ownership and phage lifecycles."""

import math
import pickle
import unittest

from terminal_cells import Bacterium, Cell, Infection, State, World
from terminal_cells.capabilities import RenderCapabilities
from terminal_cells.frame import Ink
from terminal_cells.scenes import make_scene
from terminal_cells.styles import RenderOptions, STYLES


def specimen():
    world = World(100, 40, 42, rare_events=False)
    world.cells.clear()
    world.bacteria.clear()
    world.phages.clear()
    world.complement.next_at = math.inf
    return world


def bacterium(ident, sensitive=False, kind="rod"):
    return Bacterium(
        ident, 30, 30 + ident * 10, 0, 0, kind, math.inf, math.inf, complement_sensitive=sensitive
    )


class ComplementTests(unittest.TestCase):
    def test_identical_shapes_can_have_different_susceptibility_without_phage_progeny(self):
        world = specimen()
        world.bacteria = {0: bacterium(0, True), 1: bacterium(1, False)}
        for obj in world.bacteria.values():
            self.assertTrue(world.complement.bind(world, obj))
        world.complement.update(world, 18)
        self.assertNotIn(0, world.bacteria)
        self.assertIn(1, world.bacteria)
        self.assertFalse(world.phages)
        self.assertEqual(world.complement.lysed, 1)
        self.assertEqual(world.lysed, 0)
        self.assertEqual(world.bursts[-1].cause, "complement")
        world.complement.update(world, 14)
        self.assertIsNone(world.bacteria[1].complement)

    def test_binding_is_bounded_and_excludes_nonbacterial_and_owned_hosts(self):
        world = specimen()
        for ident in range(12):
            obj = bacterium(ident)
            world.bacteria[ident] = obj
            world.complement.bind(world, obj)
        self.assertEqual(sum(b.complement is not None for b in world.bacteria.values()), 8)
        for kind in ("yeast", "trypanosome"):
            self.assertFalse(world.complement.bind(world, bacterium(30, kind=kind)))
        owned = bacterium(40)
        owned.owner = 0
        self.assertFalse(world.complement.bind(world, owned))

    def test_sealed_capture_suppresses_attack_but_pursuit_is_released_on_lysis(self):
        for state in (State.APPROACH, State.ENCLOSE):
            world = specimen()
            obj = bacterium(0, True)
            world.bacteria = {0: obj}
            world.complement.bind(world, obj)
            cell = Cell(2, 50, 30, 10, 0, 0, state=state, target=0)
            obj.owner = cell.id
            world.cells = [cell]
            world.complement.update(world, 19)
            if state is State.ENCLOSE:
                self.assertIn(0, world.bacteria)
                self.assertEqual(obj.complement.age, 0)
            else:
                self.assertNotIn(0, world.bacteria)
                self.assertIsNone(cell.target)
                self.assertIs(cell.state, State.WANDER)

    def test_phage_infection_takes_precedence_over_complement_attack(self):
        world = specimen()
        obj = bacterium(0, True)
        world.bacteria = {0: obj}
        world.complement.bind(world, obj)
        obj.infection = Infection()
        world.complement.update(world, 20)
        self.assertIn(0, world.bacteria)
        self.assertIsNone(obj.complement)
        self.assertEqual(world.complement.lysed, 0)

    def test_coating_increases_recognition_without_becoming_a_new_particle(self):
        world = specimen()
        cell = Cell(0, 20, 40, 7, 0, 0, cooldown=0)
        close, coated = bacterium(0), bacterium(1)
        close.x, close.y = 45, 40
        coated.x, coated.y = 55, 40
        world.bacteria = {0: close, 1: coated}
        world.cells = [cell]
        world.complement.bind(world, coated)
        coated.complement.age = 6
        world._update_cell(cell, 0)
        self.assertEqual(cell.target, coated.id)
        self.assertEqual(len(world.bacteria), 2)

    def test_all_styles_show_surface_marks_without_mutating_the_model(self):
        world = make_scene("complement", at=12)
        before = pickle.dumps(world)
        caps = RenderCapabilities(
            unicode=True, colors=256, backgrounds=True, blocks=True, color_pairs=256
        )
        for style in STYLES.values():
            frame = style.render(world, RenderOptions.resolve(caps, fill=True))
            self.assertTrue(any(p.ink is Ink.COMPLEMENT for row in frame.pixels for p in row))
        self.assertEqual(pickle.dumps(world), before)

    def test_ambient_activity_respects_scene_and_disable_switch(self):
        for scene, enabled in (("mixed", False), ("microbial", True)):
            world = World(100, 40, 42, scene=scene, complement=enabled)
            world.time = 100
            world.complement.update(world, 1)
            self.assertEqual(world.complement.bindings, 0)
