import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.check_dist import terminal_modes
from cells import (
    BACTERIA_INKS,
    BACTERIUM_PADDING,
    DEBRIS_PADDING,
    DIVISION_TIME,
    ENCLOSE_TIME,
    PALETTES,
    SEAL_TIME,
    STEP,
    VESICLE_TIME,
    VIRAL_TIME,
    INFECTION_CHANCE,
    MICROBE_KINDS,
    Hypha,
    draw_hyphae,
    PHAGE_PADDING,
    PHAGE_CONTACT,
    Bacterium,
    Cell,
    Drifter,
    Infection,
    Phage,
    bacterial_padding,
    Frame,
    Ink,
    State,
    World,
    draw_bacterium,
    draw_cell,
    render,
    viral_stage,
    draw_capture,
    attachment_pose,
    bacterial_scale,
    phage_geometry,
)


def advance(world, seconds):
    for _ in range(round(seconds / STEP)):
        world.update()


class SimulationTests(unittest.TestCase):
    def test_immune_cells_can_crawl_upstream(self):
        world = World(200, 80, 42, rare_events=False)
        world.bacteria.clear()
        world.current = lambda x, y: (0.6, 0)
        cell = Cell(0, 100, 80, 10, 0, math.pi, cooldown=math.inf)
        world.cells = [cell]
        for _ in range(1800):
            world.time += STEP
            world._update_cell(cell, STEP)
        self.assertLess(cell.x, 90, "upstream crawling must overcome the ordinary slide current")

    def test_wandering_immune_cells_turn_back_from_every_edge(self):
        for x, y, heading, inward in (
            (12.8, 80, math.pi, (1, 0)),
            (187.2, 80, 0, (-1, 0)),
            (100, 12.8, -math.pi / 2, (0, 1)),
            (100, 147.2, math.pi / 2, (0, -1)),
        ):
            with self.subTest(inward=inward):
                world = World(200, 80, 42, rare_events=False)
                world.bacteria.clear()
                world.current = lambda x, y: (0.6, 0.3)
                cell = Cell(0, x, y, 10, 0, heading, cooldown=math.inf)
                world.cells = [cell]
                for _ in range(1800):
                    world.time += STEP
                    world._update_cell(cell, STEP)
                distance = (cell.x - x) * inward[0] + (cell.y - y) * inward[1]
                self.assertGreater(
                    distance, 8, "the cell must leave the boundary, not remain pinned"
                )

    def test_capture_is_visible_and_has_a_digestive_lifetime(self):
        world = World(80, 24, seed=7)
        cell = Cell(0, 40, 24, 7, 0, 0)
        bacterium = Bacterium(99, 48, 24, 0, 0, "rod", 9999, 9999)
        world.cells = [cell]
        world.bacteria = {99: bacterium}
        world.update()
        self.assertEqual(cell.state, State.ENCLOSE)
        self.assertIn(99, world.bacteria)
        advance(world, 5)
        self.assertEqual(cell.state, State.ENCLOSE)
        self.assertIn(99, world.bacteria, "microbe must remain visible during enclosure")
        advance(world, ENCLOSE_TIME - 5 + 0.1)
        self.assertEqual(cell.state, State.DIGEST)
        self.assertNotIn(99, world.bacteria)
        self.assertEqual(world.engulfed, 1)
        self.assertEqual(len(cell.vesicles), 1)
        advance(world, VESICLE_TIME + 0.1)
        self.assertFalse(cell.vesicles, "digested material must not accumulate forever")

    def test_two_cells_cannot_capture_the_same_bacterium(self):
        world = World(80, 24, 1)
        world.cells = [Cell(0, 30, 24, 7, 0, 0), Cell(1, 49, 24, 7, 0, 0)]
        world.bacteria = {4: Bacterium(4, 40, 24, 0, 0, "rod", 9999, 9999)}
        world.update()
        claims = [c for c in world.cells if c.target == 4]
        self.assertEqual(len(claims), 1)
        self.assertEqual(world.bacteria[4].owner, claims[0].id)

    def test_seed_reproduces_scene_and_behavior_without_rendering_side_effects(self):
        a, b = World(100, 30, 42), World(100, 30, 42)
        for _ in range(450):
            a.update()
            render(a, unicode=True)
            b.update()
        self.assertEqual(a.__dict__ | {"rng": None}, b.__dict__ | {"rng": None})
        self.assertEqual(a.rng.getstate(), b.rng.getstate())

    def test_long_running_scene_stays_bounded_and_active(self):
        world = World(80, 24, 42)
        world.cells[0].kind = "macrophage"
        world.cells[0].divide_at = 25
        captures_at_half = 0
        for index in range(18000):  # Ten simulated minutes, no wall-clock sleep.
            world.update()
            if index == 9000:
                captures_at_half = world.engulfed
        self.assertGreater(captures_at_half, 0)
        self.assertGreater(world.engulfed, captures_at_half)
        self.assertLessEqual(len(world.bacteria), world._limits()[1] * 2)
        self.assertGreater(len(world.bacteria), 0)
        self.assertGreater(world.divisions, 0)
        self.assertLessEqual(len(world.cells), world._limits()[0])
        self.assertLessEqual(len(world.cells[0].vesicles), 2)

    def test_resize_during_capture_releases_removed_owners(self):
        world = World(160, 60, 5)
        if len(world.cells) < 2:
            world._add_cell(1, 2)
        last = world.cells[-1]
        target = next(iter(world.bacteria.values()))
        target.owner, last.target, last.state = last.id, target.id, State.ENCLOSE
        world.resize(32, 12)
        self.assertEqual(len(world.cells), 1)
        self.assertIsNone(target.owner)
        for size in [(1, 1), (80, 24), (200, 60), (32, 12)]:
            world.resize(*size)
            for _ in range(90):
                world.update()
            frame = render(world)
            self.assertEqual((frame.width, frame.height), size)
            self.assertTrue(all(math.isfinite(c.x + c.y) for c in world.cells))

    def test_lost_target_recovers_instead_of_stalling(self):
        world = World(80, 24, 8)
        cell = world.cells[0]
        cell.state, cell.target = State.ENCLOSE, 9999
        world.update()
        self.assertEqual(cell.state, State.WANDER)
        self.assertIsNone(cell.target)

    def test_division_forms_two_nuclei_before_two_daughter_cells(self):
        world = World(120, 36, 12)
        self.assertEqual(len(world.cells), 1)
        world.bacteria.clear()
        cell = world.cells[0]
        cell.divide_at = 0
        world.update()
        self.assertEqual(cell.state, State.DIVIDE)
        adult_radius = cell.radius
        advance(world, DIVISION_TIME - 3)
        self.assertEqual(len(world.cells), 1, "division must be animated before spawning")
        nuclei = [
            (x, y)
            for y, row in enumerate(render(world).pixels)
            for x, pixel in enumerate(row)
            if pixel.ink is Ink.NUCLEOLUS
        ]
        self.assertEqual(len(nuclei), 2, "two daughter nuclei should be visible")
        advance(world, 3.1)
        self.assertEqual(len(world.cells), 2)
        self.assertEqual(world.divisions, 1)
        self.assertEqual(len({c.id for c in world.cells}), 2)
        for child in world.cells:
            self.assertEqual(child.state, State.WANDER)
            self.assertLess(child.radius, adult_radius)
            self.assertEqual(child.adult_radius, adult_radius)
            self.assertGreater(child.divide_at, world.time + 40)

    def test_simultaneous_divisions_reserve_capacity(self):
        world = World(120, 36, 42)
        world.cells[0].kind = "macrophage"
        world.bacteria.clear()
        for _ in range(round(DIVISION_TIME * 2.2 / STEP)):
            for cell in world.cells:
                if cell.state is not State.DIVIDE:
                    cell.divide_at = 0
            world.update()
            reserved = len(world.cells) + sum(c.state is State.DIVIDE for c in world.cells)
            self.assertLessEqual(reserved, world._limits()[0])
        self.assertEqual(len(world.cells), world._limits()[0])
        self.assertEqual(len({c.id for c in world.cells}), len(world.cells))

    def test_resize_cancels_division_when_daughters_would_not_fit(self):
        world = World(120, 36, 42)
        world.cells[0].kind = "macrophage"
        world.cells[0].divide_at = 0
        world.update()
        self.assertEqual(world.cells[0].state, State.DIVIDE)
        world.resize(32, 12)
        self.assertEqual(world.cells[0].state, State.WANDER)
        world.resize(200, 60)
        self.assertEqual(len(world.cells), 1, "enlarging must leave population growth to division")
        for _ in range(300):
            world.update()
        self.assertEqual(len(world.cells), 1)


class RenderingTests(unittest.TestCase):
    def test_phagocytosis_flash_is_confined_to_the_cup(self):
        cell = Cell(
            0,
            40,
            40,
            14,
            0,
            0,
            state=State.ENCLOSE,
            elapsed=7.1,
            reach=3.8,
            reach_angle=math.tau - 0.3,
            capture_distance=20,
        )
        frame = Frame(90, 45)
        draw_cell(frame, cell, 0, True)
        highlights = [
            (x, y)
            for y, row in enumerate(frame.pixels)
            for x, p in enumerate(row)
            if p.ink is Ink.CAPTURE
        ]
        self.assertTrue(highlights)
        for x, y in highlights:
            angle = math.atan2(y * 2 - cell.y, x - cell.x)
            delta = (angle - cell.reach_angle + math.pi) % math.tau - math.pi
            self.assertLess(abs(delta), 0.75)
        self.assertTrue(any(p.ink is Ink.MEMBRANE for row in frame.pixels for p in row))
        self.assertTrue(
            any(
                p.ink is Ink.MEMBRANE
                for row in frame.pixels
                for x, p in enumerate(row)
                if x < cell.x - cell.radius * 0.6
            )
        )

    def test_larger_default_cells_have_nuclei_and_distinct_organelles(self):
        world = World(120, 40, 42)
        self.assertGreaterEqual(world.cells[0].radius, 13)
        self.assertLessEqual(len(world.bacteria), 16, "larger organisms need more empty space")
        self.assertGreaterEqual(world.red_cells[0].size, 4)
        cell = Cell(0, 30, 30, 14, 0, 0)
        frame = Frame(65, 32)
        draw_cell(frame, cell, 0, True)
        self.assertEqual(sum(p.ink is Ink.NUCLEOLUS for row in frame.pixels for p in row), 1)
        for ink in (Ink.MITOCHONDRION, Ink.RETICULUM):
            points = [
                (x, y)
                for y, row in enumerate(frame.pixels)
                for x, p in enumerate(row)
                if p.ink is ink
            ]
            self.assertGreaterEqual(len(points), 3)
            for x, y in points:
                dx, dy = x - cell.x, y * 2 - cell.y
                self.assertLess(math.hypot(dx, dy), cell.outline(math.atan2(dy, dx), 0))

    def test_flagella_animate_without_changing_the_simulation(self):
        bacterium = Bacterium(7, 25, 20, 0, 1, "rod", 9999, 9999)
        before = vars(bacterium).copy()
        a, b = Frame(50, 24), Frame(50, 24)
        draw_bacterium(a, bacterium, True, now=0)
        draw_bacterium(b, bacterium, True, now=0.35)
        self.assertNotEqual(a.plain(), b.plain())
        self.assertEqual(vars(bacterium), before)
        points = [
            (x, y)
            for y, row in enumerate(a.pixels)
            for x, p in enumerate(row)
            if p.ink is Ink.BACTERIA and p.char != " "
        ]
        self.assertLess(min(x for x, y in points), bacterium.x - 6)
        self.assertGreater(max(x for x, y in points), bacterium.x + 2)

    def test_flagella_stop_at_membranes(self):
        world = World(80, 24, 42)
        world.cells = [Cell(0, 12, 24, 7, 0, 0)]
        world.red_cells.clear()
        bacterium = Bacterium(1, 25, 24, 0, 1, "rod", 9999, 9999)
        frame = Frame(80, 24)
        draw_bacterium(frame, bacterium, True, 0, world)
        for y, row in enumerate(frame.pixels):
            for x, p in enumerate(row):
                if p.char != " ":
                    dx, dy = x - 12, y * 2 - 24
                    self.assertGreaterEqual(
                        math.hypot(dx, dy), world.cells[0].outline(math.atan2(dy, dx), 0)
                    )

    def test_mitosis_has_distinct_envelope_spindle_and_chromosome_stages(self):
        def stage_frame(elapsed):
            cell = Cell(0, 30, 24, 9, 0, 0, state=State.DIVIDE, elapsed=elapsed)
            frame = Frame(60, 24)
            draw_cell(frame, cell, elapsed, True)
            return frame

        def count(frame, ink):
            return sum(p.ink is ink and p.char != " " for row in frame.pixels for p in row)

        prophase, breakdown = stage_frame(3), stage_frame(11.9)
        self.assertGreater(count(prophase, Ink.NUCLEUS), count(breakdown, Ink.NUCLEUS))
        self.assertGreater(count(breakdown, Ink.DNA), 0)
        spindle, metaphase = stage_frame(16), stage_frame(23)
        self.assertGreater(count(spindle, Ink.SPINDLE), 4)
        self.assertEqual(spindle.plain().count("*"), 2)
        aligned = [
            (x, y)
            for y, row in enumerate(metaphase.pixels)
            for x, p in enumerate(row)
            if p.char == "X"
        ]
        self.assertEqual(len(aligned), 3)
        self.assertEqual(len({x for x, _ in aligned}), 1)
        anaphase = stage_frame(30).plain()
        self.assertIn("<", anaphase)
        self.assertIn(">", anaphase)
        self.assertEqual(stage_frame(39).plain().count("●"), 2)
        self.assertEqual(stage_frame(47).plain().count("●"), 2)
        self.assertGreaterEqual(DIVISION_TIME, 40)

    def test_moving_nucleus_is_always_one_connected_sprite(self):
        for unicode in (False, True):
            for index in range(100):
                cell = Cell(0, 25 + index * 0.013, 25 + index * 0.027, 14, index * 0.14, 0)
                frame = Frame(60, 24)
                draw_cell(frame, cell, index * 0.03, unicode)
                pixels = [
                    (x, y)
                    for y, row in enumerate(frame.pixels)
                    for x, pixel in enumerate(row)
                    if pixel.ink in (Ink.NUCLEUS, Ink.NUCLEOLUS)
                ]
                self.assertGreater(len(pixels), 15)
                remaining = set(pixels)
                stack = [remaining.pop()]
                while stack:
                    x, y = stack.pop()
                    for neighbor in [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)]:
                        if neighbor in remaining:
                            remaining.remove(neighbor)
                            stack.append(neighbor)
                self.assertFalse(remaining, "the whole nucleus must stay connected")

    def test_each_microbe_has_a_distinct_color_in_both_color_themes(self):
        for theme in ("slide", "amber"):
            for color_index in (0, 1):  # Both 256-color and 8-color terminals.
                colors = {
                    PALETTES[theme][ink.value - 1][color_index]
                    for kind, ink in BACTERIA_INKS.items()
                    if color_index == 0 or kind in ("rod", "coccus", "spiral")
                }
                self.assertEqual(len(colors), len(BACTERIA_INKS) if color_index == 0 else 3)
        for kind, ink in BACTERIA_INKS.items():
            frame = Frame(20, 10)
            draw_bacterium(frame, Bacterium(1, 10, 10, 0, 0, kind, 99, 99), True)
            visible = [p for row in frame.pixels for p in row if p.char != " "]
            self.assertTrue(visible)
            self.assertTrue(any(p.ink is ink for p in visible))
            self.assertTrue(all(p.ink in (ink, Ink.MICROBIAL_DNA) for p in visible))

    def test_engulfed_microbes_keep_their_species_color(self):
        for kind, ink in BACTERIA_INKS.items():
            world = World(80, 24, 7)
            cell = world.cells[0]
            cell.x, cell.y, cell.cooldown = 40, 24, 0
            world.bacteria = {99: Bacterium(99, 47, 24, 0, 0, kind, 9999, 9999)}
            advance(world, ENCLOSE_TIME + 1)
            self.assertEqual(cell.state, State.DIGEST)
            self.assertEqual(cell.vesicles[0].kind, kind)
            self.assertTrue(any(p.ink is ink for row in render(world).pixels for p in row))


class MembraneTests(unittest.TestCase):
    def world(self):
        world = World(100, 36, 7)
        world.cells = [Cell(0, 45, 36, 7, 0, 0, cooldown=999)]
        world.bacteria.clear()
        world.debris.clear()
        world.red_cells.clear()
        world.phages.clear()
        world.replenish_at = math.inf
        world.nutrient_at = math.inf  # Isolate reflection from later food-seeking turns.
        return world

    def assert_outside(self, world, obj, padding):
        for cell in world.cells:
            dx, dy = obj.x - cell.x, obj.y - cell.y
            distance = math.hypot(dx, dy)
            boundary = cell.outline(math.atan2(dy, dx), world.time)
            self.assertGreaterEqual(distance, boundary + padding - 1e-6)

    def test_bacteria_bounce_and_debris_is_displaced_by_a_moving_membrane(self):
        world = self.world()
        world.current = lambda x, y: (2.0, 0)
        bacterium = Bacterium(0, 30, 36, 0, 3, "rod", 9999, 9999)
        debris = Drifter(55, 36, 0, 0.3)
        world.bacteria[0] = bacterium
        world.debris.append(debris)
        for _ in range(400):
            world.update()
            self.assert_outside(world, bacterium, BACTERIUM_PADDING)
            self.assert_outside(world, debris, DEBRIS_PADDING)
        self.assertLess(math.cos(bacterium.angle), 0, "collision should reflect swimming direction")

    def test_dividing_membranes_exclude_particles_in_every_stage(self):
        world = self.world()
        world.cells[0].state = State.DIVIDE
        world.current = lambda x, y: (0, 0)
        for index in range(16):
            angle = index * math.tau / 16
            world.bacteria[index] = Bacterium(
                index,
                45 + math.cos(angle) * 10,
                36 + math.sin(angle) * 10,
                angle + math.pi,
                1,
                "rod",
                9999,
                9999,
            )
        for _ in range(round((DIVISION_TIME - 0.1) / STEP)):
            world.update()
            for bacterium in world.bacteria.values():
                self.assert_outside(world, bacterium, BACTERIUM_PADDING)

    def test_spawn_resize_and_overlapping_cells_leave_no_hidden_extracellular_particles(self):
        world = self.world()
        world.cells.append(Cell(1, 53, 36, 7, 1, 0, cooldown=999))
        for index in range(12):
            world.bacteria[index] = Bacterium(index, 49, 36, index, 0, "coccus", 9999, 9999)
        world.debris = [Drifter(49, 36, 0, 0.3)]
        world._resolve_obstacles()
        for bacterium in world.bacteria.values():
            self.assert_outside(world, bacterium, BACTERIUM_PADDING)
        self.assert_outside(world, world.debris[0], DEBRIS_PADDING)
        world.resize(80, 24)
        for bacterium in world.bacteria.values():
            self.assert_outside(world, bacterium, BACTERIUM_PADDING)

    def test_red_blood_cells_also_block_free_microbes(self):
        world = self.world()
        world.cells.clear()
        world.current = lambda x, y: (0, 0)
        world.red_cells = [Drifter(45, 36, 0, 3)]
        microbe = Bacterium(0, 38, 36, 0, 2, "rod", 9999, 9999)
        world.bacteria[0] = microbe
        for _ in range(200):
            world.update()
            disc = world.red_cells[0]
            dx, dy = microbe.x - disc.x, microbe.y - disc.y
            angle = math.atan2(dy, dx)
            boundary = 3 * 2.4 / math.hypot(2.4 * math.cos(angle), 3 * math.sin(angle))
            self.assertGreaterEqual(math.hypot(dx, dy), boundary + BACTERIUM_PADDING - 1e-6)

    def test_ingestion_holds_outside_until_seal_then_transports_inside(self):
        world = self.world()
        cell = world.cells[0]
        cell.cooldown = 0
        microbe = Bacterium(99, 54, 36, 0, 0, "coccus", 9999, 9999)
        world.bacteria[99] = microbe
        world.update()
        self.assertEqual(cell.state, State.ENCLOSE)
        advance(world, SEAL_TIME - 0.2)
        self.assertAlmostEqual(
            math.hypot(microbe.x - cell.x, microbe.y - cell.y), cell.capture_distance
        )
        self.assertIn(99, world.bacteria)
        advance(world, 0.4)
        sealed_frame = render(world)
        self.assertTrue(any(p.ink is Ink.CAPTURE for row in sealed_frame.pixels for p in row))
        advance(world, 2.2)
        self.assertLess(math.hypot(microbe.x - cell.x, microbe.y - cell.y), cell.radius)
        self.assertEqual(cell.state, State.ENCLOSE)
        advance(world, 1)
        self.assertNotIn(99, world.bacteria)
        self.assertEqual(len(cell.vesicles), 1)
        self.assertEqual(cell.vesicles[0].kind, "coccus")


class MicroscopyDetailTests(unittest.TestCase):
    @staticmethod
    def tags(cell):
        return [tag for network in cell.organelles for tag in network.tags]

    def test_organelle_fusion_and_fission_conserve_material(self):
        world = World(120, 40, 9)
        cell = Cell(0, 60, 40, 14, 0, 0, remodel_at=0)
        original = sorted(self.tags(cell))

        def count():
            return sum(n.kind == "mitochondrion" for n in cell.organelles)

        before = count()
        world._remodel_organelles(cell)
        self.assertLess(count(), before, "nearby mitochondrial branches should fuse")
        fused = count()
        cell.remodel_at = 0
        world._remodel_organelles(cell)
        self.assertGreater(count(), fused, "fission should separate connected components")
        self.assertEqual(sorted(self.tags(cell)), original)
        er = next(n for n in cell.organelles if n.kind == "reticulum")
        self.assertEqual(len(er.fragments(set(range(len(er.nodes))))), 1)
        self.assertGreater(len(er.edges), len(er.nodes), "ER folds must have cross connections")

    def test_division_partitions_existing_organelle_material(self):
        for angle in (0, 0.5, 1.2, 2.4):
            world = World(140, 50, 9)
            cell = Cell(
                0,
                70,
                50,
                14,
                0.2,
                0,
                state=State.DIVIDE,
                elapsed=DIVISION_TIME,
                division_angle=angle,
            )
            world.cells = [cell]
            original = sorted(self.tags(cell))
            world._update_division(cell, STEP)
            left, right = world.cells
            self.assertTrue(left.organelles)
            self.assertTrue(right.organelles)
            self.assertFalse(set(self.tags(left)) & set(self.tags(right)))
            self.assertEqual(sorted(self.tags(left) + self.tags(right)), original)
            self.assertTrue(
                all(
                    n.kind in ("mitochondrion", "reticulum", "lysosome")
                    for child in world.cells
                    for n in child.organelles
                )
            )

    def test_ruffles_are_local_and_lobes_persist(self):
        cell = Cell(0, 40, 40, 14, 0.2, 0.5)
        angles = [i * math.tau / 120 for i in range(120)]
        first = [cell.body_outline(a, 0) for a in angles]
        later = [cell.body_outline(a, 4) for a in angles]
        self.assertGreater(max(first) - min(first), cell.radius * 0.2)
        self.assertLess(max(abs(a - b) for a, b in zip(first, later)), cell.radius * 0.07)
        self.assertGreater(
            first[angles.index(min(angles, key=lambda a: abs(a - cell.heading)))], cell.radius
        )

    def test_wrapping_tracks_the_captured_body_without_a_long_snout(self):
        for kind in ("rod", "coccus"):
            world = World(140, 50, 9)
            cell = Cell(0, 60, 50, 14, 0, 0)
            host = Bacterium(99, 78, 50, math.pi / 2, 0, kind, 9999, 9999)
            world.cells = [cell]
            world.bacteria = {99: host}
            world.red_cells.clear()
            world.phages.clear()
            world.debris.clear()
            world.current = lambda x, y: (0, 0)
            world.update()
            self.assertEqual(cell.state, State.ENCLOSE)
            advance(world, 6.85)
            self.assertAlmostEqual(cell.capture_axis, math.pi / 2)
            self.assertEqual(cell.capture_a == cell.capture_b, kind == "coccus")
            distance = math.hypot(host.x - cell.x, host.y - cell.y)
            self.assertGreater(
                distance, cell.body_outline(cell.reach_angle, world.time) + cell.capture_b
            )
            frame = Frame(140, 50)
            draw_capture(frame, cell, True, world.time)
            ca, sa = math.cos(cell.capture_axis), math.sin(cell.capture_axis)
            points = [
                (x, y * 2)
                for y, row in enumerate(frame.pixels)
                for x, p in enumerate(row)
                if p.ink is Ink.CAPTURE and p.char != " "
            ]
            self.assertTrue(points)
            self.assertTrue(
                all(
                    math.hypot(x - host.x, y - host.y) < max(cell.capture_a, cell.capture_b) + 8
                    for x, y in points
                )
            )
            for x, y in points:
                dx, dy = x - host.x, y - host.y
                if dx * math.cos(cell.reach_angle) + dy * math.sin(cell.reach_angle) >= 0:
                    # The outer rim hugs the target; shoulders may flare at the body.
                    self.assertLessEqual(abs(dx * ca + dy * sa), cell.capture_a + 2.5)

    def test_phage_attachment_follows_surface_normal_and_host_rotation(self):
        for heading in (0, 0.5, 1.7):
            for angle in (0, 0.6, 1.8, 3.4):
                host = Bacterium(
                    0, 40, 40, heading, 0, "rod", 99, 99, infection=Infection(10, angle)
                )
                x, y, inward = attachment_pose(host)
                dx, dy = x - host.x, y - host.y
                ux, uy = math.cos(heading), math.sin(heading)
                lx, ly = ux * dx + uy * dy, -uy * dx + ux * dy
                a, b = 3.2 * bacterial_scale(host), 1.65 * bacterial_scale(host)
                self.assertAlmostEqual((lx / a) ** 2 + (ly / b) ** 2, 1)
                nx, ny = lx / a**2, ly / b**2
                normal = math.atan2(ny, nx) + heading
                self.assertAlmostEqual(math.cos(inward - normal), -1)
                head_distances = []
                for contraction in (0, 0.3, 0.7, 1):
                    offset = 0.5 - 0.2 * contraction
                    phage = Phage(
                        -1,
                        x - math.cos(inward) * offset,
                        y - math.sin(inward) * offset,
                        angle=inward,
                    )
                    head, tip = phage_geometry(phage, contraction)
                    self.assertAlmostEqual(tip[0], x)
                    self.assertAlmostEqual(tip[1], y)
                    hx, hy = head[0] - host.x, head[1] - host.y
                    self.assertGreater(
                        ((ux * hx + uy * hy) / a) ** 2 + ((-uy * hx + ux * hy) / b) ** 2, 1
                    )
                    head_distances.append(math.dist(head, tip))
                self.assertEqual(head_distances, sorted(head_distances, reverse=True))

    def test_empty_capsid_remains_after_injection_and_lysis_then_expires(self):
        world = World(120, 40, 7)
        world.cells.clear()
        world.red_cells.clear()
        world.debris.clear()
        world.phages.clear()
        world.bacteria = {0: Bacterium(0, 40, 40, 0, 0, "rod", 9999, 9999, infection=Infection(10))}
        frame = render(world, True)
        empty = [
            (x, y)
            for y, row in enumerate(frame.pixels)
            for x, p in enumerate(row)
            if p.ink is Ink.MUTED and p.char in "<>ᛘᛦ"
        ]
        self.assertEqual(len(empty), 1)
        self.assertGreaterEqual(empty[0][0], 40 + 3.2 * bacterial_scale(world.bacteria[0]) - 0.5)
        world._lyse(world.bacteria[0])
        self.assertEqual(len(world.spent_capsids), 1)
        self.assertNotIn(world.spent_capsids[0], world.phages.values())
        world._update_phages(18.1)
        self.assertFalse(world.spent_capsids)


class DiversityTests(unittest.TestCase):
    def empty_world(self):
        world = World(160, 60, 8)
        world.cells.clear()
        world.bacteria.clear()
        world.red_cells.clear()
        world.debris.clear()
        world.phages.clear()
        world.hyphae.clear()
        world.replenish_at = world.phage_replenish_at = math.inf
        world.current = lambda x, y: (0, 0)
        return world

    def test_seeded_starting_communities_vary_and_are_reproducible(self):
        communities, kinds, immune = set(), set(), set()
        for seed in range(20):
            left, right = World(160, 60, seed), World(160, 60, seed)
            self.assertEqual(left.__dict__ | {"rng": None}, right.__dict__ | {"rng": None})
            counts = tuple(
                sum(b.kind == kind for b in left.bacteria.values()) for kind in MICROBE_KINDS
            )
            communities.add(counts + (len(left.red_cells), len(left.phages), len(left.hyphae)))
            kinds.update(b.kind for b in left.bacteria.values())
            immune.update(c.kind for c in left.cells)
        self.assertGreater(len(communities), 15)
        self.assertEqual(kinds, set(MICROBE_KINDS))
        self.assertEqual(immune, {"macrophage", "neutrophil"})

    def test_new_microbes_have_distinct_read_only_silhouettes(self):
        import copy

        frames = set()
        for kind in MICROBE_KINDS:
            microbe = Bacterium(2, 24, 24, 0.25, 1, kind, 9999, 9999)
            before = copy.deepcopy(microbe)
            for unicode in (False, True):
                frame = Frame(50, 24)
                draw_bacterium(frame, microbe, unicode, 0.7)
                if unicode:
                    frames.add(frame.plain())
                self.assertGreater(sum(p.char != " " for row in frame.pixels for p in row), 3)
                self.assertEqual(microbe, before)
        self.assertEqual(len(frames), len(MICROBE_KINDS))

    def test_yeast_buds_before_releasing_a_daughter(self):
        world = self.empty_world()
        host = Bacterium(0, 60, 60, 0, 0, "yeast", 9999, 0)
        world.bacteria = {0: host}
        world.next_id = 1
        advance(world, 6)
        self.assertEqual(len(world.bacteria), 1)
        self.assertAlmostEqual(host.bud, 0.5)
        advance(world, 6.1)
        self.assertEqual(len(world.bacteria), 2)
        self.assertEqual(host.bud, 0)
        child = world.bacteria[1]
        self.assertEqual(child.kind, "yeast")
        self.assertGreater(child.x, host.x + 6)
        self.assertEqual(child.speed, 0)

    def test_trypanosome_longitudinal_fission_preserves_type(self):
        world = self.empty_world()
        host = Bacterium(0, 60, 60, 0, 0, "trypanosome", 9999, 0)
        world.bacteria = {0: host}
        world.next_id = 1
        advance(world, 5)
        self.assertEqual(len(world.bacteria), 1)
        self.assertAlmostEqual(host.bud, 0.5)
        advance(world, 5.1)
        self.assertEqual(len(world.bacteria), 2)
        child = world.bacteria[1]
        self.assertEqual(child.kind, host.kind)
        self.assertGreater(abs(child.y - host.y), 4)

    def test_chains_and_colonies_add_segments_before_separating(self):
        for kind in ("bacillus", "colony"):
            world = self.empty_world()
            host = Bacterium(0, 60, 60, 0, 0, kind, 9999, 0)
            world.bacteria = {0: host}
            world.next_id = 1
            world.time = 1
            world._reproduce_microbe(host, STEP, 30)
            self.assertEqual(host.units, 4)
            self.assertEqual(len(world.bacteria), 1)
            host.units, host.divide_at = 5, 0
            world._reproduce_microbe(host, STEP, 30)
            self.assertEqual(len(world.bacteria), 2)
            self.assertEqual(sum(b.units for b in world.bacteria.values()), 5)
            self.assertEqual({b.kind for b in world.bacteria.values()}, {kind})

    def test_mature_neutrophils_feed_but_do_not_divide(self):
        world = self.empty_world()
        cell = Cell(0, 60, 60, 14, 0, 0, kind="neutrophil", divide_at=0)
        world.cells = [cell]
        world.bacteria = {0: Bacterium(0, 78, 60, 0, 0, "coccus", 9999, 9999)}
        advance(world, 11)
        self.assertEqual(len(world.cells), 1)
        self.assertEqual(world.divisions, 0)
        self.assertEqual(world.engulfed, 1)
        self.assertNotEqual(cell.state, State.DIVIDE)
        frame = render(world, True)
        self.assertTrue(any(p.ink is Ink.NEUTROPHIL for row in frame.pixels for p in row))
        self.assertFalse(any(p.ink is Ink.NUCLEOLUS for row in frame.pixels for p in row))

    def test_phages_do_not_infect_eukaryotic_microbes(self):
        for kind in ("yeast", "trypanosome"):
            world = self.empty_world()
            host = Bacterium(0, 60, 60, 0, 0, kind, 9999, 9999)
            world.bacteria = {0: host}
            phage = world._add_phage(61, 60)
            with patch.object(world.rng, "random", return_value=0) as roll:
                world._update_phages(STEP)
                world._infect(host, phage)
                self.assertEqual(roll.call_count, 0)
            self.assertIsNone(host.infection)
            self.assertIn(phage.id, world.phages)

    def test_fungal_growth_branches_stays_bounded_and_respects_membranes(self):
        world = self.empty_world()
        world._add_hypha((20, 20))
        advance(world, 180)
        hypha = world.hyphae[0]
        self.assertGreater(len(hypha.nodes), 10)
        self.assertLessEqual(len(hypha.nodes), 48)
        self.assertTrue(
            any(sum(a == index for a, b in hypha.edges) > 1 for index in range(len(hypha.nodes)))
        )
        world.cells = [Cell(0, 20, 20, 14, 0, 0, cooldown=999)]
        frame = Frame(160, 60)
        draw_hyphae(frame, world, True)
        for y, row in enumerate(frame.pixels):
            for x, p in enumerate(row):
                if p.ink is Ink.FUNGUS and p.char != " ":
                    self.assertIsNone(next(world._obstacles(x, y * 2, 0.1), None))
        world.resize(60, 24)
        self.assertLessEqual(len(world.hyphae), world._hypha_limit())
        self.assertTrue(all(math.isfinite(x + y) for h in world.hyphae for x, y in h.nodes))

    def test_large_microbes_stay_outside_immune_membranes(self):
        world = self.empty_world()
        cell = Cell(0, 50, 50, 14, 0, 0, cooldown=999)
        world.cells = [cell]
        for index, kind in enumerate(MICROBE_KINDS):
            world.bacteria = {index: Bacterium(index, 65, 50, math.pi, 2, kind, 9999, 9999)}
            advance(world, 0.3)
            host = world.bacteria[index]
            dx, dy = host.x - cell.x, host.y - cell.y
            self.assertGreaterEqual(
                math.hypot(dx, dy),
                cell.outline(math.atan2(dy, dx), world.time) + bacterial_padding(host) - 1e-6,
            )


class EcologyTests(unittest.TestCase):
    def world(self):
        world = DiversityTests.empty_world(self)
        world.nutrients.clear()
        world.nutrient_at = math.inf
        return world

    def test_missing_species_can_arrive_above_target_without_breaking_cap(self):
        world = self.world()
        target = world._limits()[1]
        reserve = min(2, max(1, target // 4))
        for _ in range(target * 2 - reserve):
            world._add_bacterium(kind="rod")
        for microbe in world.bacteria.values():
            microbe.divide_at = 0
        world.update()
        self.assertEqual(
            len(world.bacteria), target * 2 - reserve, "births must leave immigration slots"
        )
        world.time, world.replenish_at = 100, 0
        world._update_arrivals()
        newcomer = world.bacteria[world.next_id - 1]
        self.assertNotEqual(newcomer.kind, "rod")
        self.assertTrue(
            newcomer.x < 0
            or newcomer.x > world.width
            or newcomer.y < 0
            or newcomer.y > world.height
        )
        self.assertIsNotNone(newcomer.entry)
        self.assertLessEqual(len(world.bacteria), target * 2)

    def test_full_population_makes_space_by_departure_then_restores_diversity(self):
        world = self.world()
        cap = world._limits()[1] * 2
        for _ in range(cap):
            world._add_bacterium(kind="rod")
        for microbe in world.bacteria.values():
            microbe.x, microbe.y, microbe.speed, microbe.turn_at = 2, 20, 0, math.inf
        world.time, world.replenish_at = 100, 0
        world._update_arrivals()
        self.assertEqual(sum(b.leaving for b in world.bacteria.values()), 1)
        self.assertEqual(len(world.bacteria), cap, "no instantaneous population replacement")
        world.replenish_at = math.inf
        advance(world, 1)
        self.assertEqual(len(world.bacteria), cap - 1)
        world.replenish_at = 0
        world._update_arrivals()
        self.assertEqual(len(world.bacteria), cap)
        self.assertGreater(len({b.kind for b in world.bacteria.values()}), 1)

    def test_absent_fungi_and_large_entities_can_return_in_available_space(self):
        world = self.world()
        world.time, world.replenish_at = 120, 0
        world.fungal_arrival_at = world.large_arrival_at = 0
        world._update_arrivals()
        self.assertEqual(len(world.hyphae), 1)
        self.assertEqual(len(world.cells), 1)
        self.assertEqual(len(world.red_cells), 1)
        self.assertGreater(world.fungal_arrival_at, world.time)
        self.assertGreater(world.large_arrival_at, world.time)

    def test_food_attracts_bacteria_and_is_consumed_to_support_growth(self):
        world = self.world()
        host = Bacterium(1, 40, 40, math.pi, 2, "rod", math.inf, 100)
        world.bacteria = {1: host}
        world._add_nutrient(55, 40)
        before = math.dist((host.x, host.y), (55, 40))
        advance(world, 8)
        self.assertLess(math.dist((host.x, host.y), (55, 40)), before / 2)
        self.assertGreater(host.fed_until, world.time)
        self.assertLess(host.divide_at, 100)
        self.assertLess(world.nutrients[0].amount, 4 * math.exp(-8 * 0.012))

    def test_lysis_seeds_food_and_food_eventually_disperses(self):
        world = self.world()
        host = Bacterium(0, 50, 50, 0, 0, "rod", math.inf, math.inf)
        world.bacteria = {0: host}
        world._lyse(host)
        self.assertEqual(len(world.nutrients), 1)
        self.assertEqual((world.nutrients[0].x, world.nutrients[0].y), (50, 50))
        world._update_nutrients(41)
        self.assertFalse(world.nutrients)
        for _ in range(10):
            world._add_nutrient(20, 20)
        self.assertEqual(len(world.nutrients), 4)

    def test_highway_following_chooses_a_branch_and_then_detaches(self):
        world = self.world()
        world.hyphae = [
            Hypha(
                [(20, 30), (30, 30), (40, 34), (40, 25)],
                [(0, 1), (1, 2), (1, 3)],
                [(2, 0), (3, 0)],
                math.inf,
            )
        ]
        host = Bacterium(1, 21, 31.6, 0, 2, "rod", math.inf, math.inf)
        world.bacteria = {1: host}
        advance(world, 0.1)
        self.assertEqual(host.rail, 0)
        advance(world, 5)
        self.assertEqual(host.rail_from, 1)
        self.assertIn(host.rail_to, (2, 3))
        host.rail_until = world.time
        world._microbe_behavior(host, STEP)
        self.assertIsNone(host.rail)
        self.assertGreater(host.rail_ready, world.time)

    def test_escape_is_selective_brief_and_has_priority_over_food(self):
        world = self.world()
        world.cells = [Cell(0, 40, 40, 14, 0, 0, cooldown=999)]
        world._add_nutrient(35, 40)
        host = Bacterium(1, 60, 40, math.pi, 2, "vibrio", math.inf, math.inf)
        boost = world._microbe_behavior(host, 0.5)
        self.assertGreater(boost, 1)
        self.assertGreater(
            math.cos(host.angle), 0.9, "escape must override attraction toward the immune cell"
        )
        self.assertGreater(host.escape_ready, host.escape_until)
        world.time = host.escape_until + 0.1
        self.assertEqual(world._microbe_behavior(host, STEP), 1)
        passive = Bacterium(3, 60, 40, math.pi, 2, "vibrio", math.inf, math.inf)
        self.assertEqual(world._microbe_behavior(passive, STEP), 1)
        self.assertEqual(passive.escape_until, 0)

    def test_capture_freezes_behavior_and_keeps_microbes_inside_the_cup(self):
        world = self.world()
        host = Bacterium(1, 60, 40, 0, 2, "rod", math.inf, math.inf, owner=0, rail=0)
        cell = Cell(
            0, 40, 40, 14, 0, 0, state=State.ENCLOSE, elapsed=1, target=1, capture_distance=20
        )
        world.cells, world.bacteria = [cell], {1: host}
        host.escape_until = 999
        world._add_nutrient(100, 40)
        advance(world, 1)
        self.assertAlmostEqual(host.x, cell.capture_center()[0])
        self.assertAlmostEqual(host.y, cell.capture_center()[1])

    def test_nutrients_and_behavior_render_without_mutating_the_world(self):
        import copy

        world = self.world()
        world._add_nutrient(50, 40)
        world.bacteria = {1: Bacterium(1, 49, 40, 0, 0, "rod", math.inf, math.inf, fed_until=5)}
        before = copy.deepcopy(world.__dict__ | {"rng": None})
        frame = render(world, True)
        self.assertTrue(any(p.ink is Ink.NUTRIENT for row in frame.pixels for p in row))
        self.assertIn("*", frame.plain())
        self.assertEqual(world.__dict__ | {"rng": None}, before)
        world.resize(80, 30)
        self.assertEqual((world.nutrients[0].x, world.nutrients[0].y), (25, 20))


class EntryTests(unittest.TestCase):
    def world(self):
        return EcologyTests.world(self)

    def test_all_arrival_sprites_start_invisible_and_cross_each_edge_gradually(self):
        for side in range(4):
            for kind in (*MICROBE_KINDS, "macrophage", "neutrophil", "red", "phage"):
                with self.subTest(side=side, kind=kind):
                    world = self.world()
                    if kind in MICROBE_KINDS:
                        obj = Bacterium(0, 0, 0, 0, 2, kind, math.inf, math.inf)
                        world.bacteria = {0: obj}
                    elif kind in ("macrophage", "neutrophil"):
                        obj = Cell(0, 0, 0, 14, 0.2, 0, kind=kind)
                        world.cells = [obj]
                    elif kind == "red":
                        obj = Drifter(0, 0, 0, 5)
                        world.red_cells = [obj]
                    else:
                        obj = Phage(0, 0, 0)
                        world.phages = {0: obj}
                    with patch.object(world.rng, "randrange", return_value=side):
                        world._begin_entry(obj)
                    self.assertFalse(
                        render(world, True).plain().strip(),
                        "the complete sprite must start outside",
                    )
                    visible_while_entering = False
                    for step in range(700):
                        before = obj.x, obj.y
                        world._advance_entry(obj, 0.05)
                        self.assertLessEqual(math.dist(before, (obj.x, obj.y)), 0.131)
                        if step % 10 == 0 and obj.entry is not None:
                            visible_while_entering |= bool(render(world, True).plain().strip())
                        if obj.entry is None:
                            break
                    self.assertIsNone(obj.entry)
                    self.assertTrue(visible_while_entering)
                    self.assertTrue(0 < obj.x < world.width and 0 < obj.y < world.height)

    def test_entry_does_not_wrap_or_resume_other_behavior_early(self):
        world = self.world()
        world._add_bacterium(kind="vibrio", arrival=True)
        host = world.bacteria[world.next_id - 1]
        world._add_nutrient(world.width / 2, world.height / 2)
        host.divide_at = 0
        before = host.x, host.y
        advance(world, 1)
        self.assertIsNotNone(host.entry)
        self.assertLessEqual(math.dist(before, (host.x, host.y)), max(1.8, host.speed) + 1e-6)
        self.assertEqual(len(world.bacteria), 1)
        self.assertEqual(host.angle, host.entry.angle)

    def test_blocked_entry_waits_instead_of_being_projected_through_a_membrane(self):
        world = self.world()
        host = Bacterium(0, 0, 0, 0, 2, "rod", math.inf, math.inf)
        world.bacteria = {0: host}
        with patch.object(world.rng, "randrange", return_value=0):
            world._begin_entry(host)
        world.cells = [Cell(0, 5, host.y, 14, 0, 0, cooldown=999)]
        position = host.x, host.y
        world._advance_entry(host, 0.1)
        world._resolve_obstacles()
        self.assertEqual((host.x, host.y), position)
        self.assertIsNotNone(host.entry)
        world.cells.clear()
        world._advance_entry(host, 0.1)
        self.assertGreater(host.x, position[0])

    def test_resize_during_entry_preserves_direction_and_avoids_a_boundary_jump(self):
        for side in range(4):
            world = self.world()
            obj = Cell(0, 0, 0, 14, 0, 0)
            world.cells = [obj]
            with patch.object(world.rng, "randrange", return_value=side):
                world._begin_entry(obj)
            world._advance_entry(obj, 2)
            heading = obj.entry.angle
            world.resize(100, 40)
            world.red_cells.clear()
            world.bacteria.clear()
            while obj.entry is not None:
                before = obj.x, obj.y
                world._advance_entry(obj, 0.05)
                self.assertLessEqual(math.dist(before, (obj.x, obj.y)), 0.131)
            before = obj.x, obj.y
            world._update_cell(obj, 0.05)
            self.assertLess(math.dist(before, (obj.x, obj.y)), 0.2)
            self.assertAlmostEqual(obj.heading, heading, delta=0.05)

    def test_replacement_phage_also_enters_from_outside(self):
        world = self.world()
        world.phage_replenish_at = 0
        world._update_phages(STEP)
        self.assertEqual(len(world.phages), 1)
        phage = next(iter(world.phages.values()))
        self.assertIsNotNone(phage.entry)
        self.assertFalse(render(world, True).plain().strip())
        before = phage.x, phage.y
        world._update_phages(STEP)
        self.assertAlmostEqual(math.dist(before, (phage.x, phage.y)), 2 * STEP)


class PhageTests(unittest.TestCase):
    def world(self):
        world = World(100, 36, 7)
        world.cells.clear()
        world.red_cells.clear()
        world.debris.clear()
        world.bacteria = {0: Bacterium(0, 35 - PHAGE_CONTACT + 0.1, 30, 0, 0, "rod", 9999, 9999)}
        world.phages = {0: Phage(0, 35, 30)}
        world.next_phage_id = 1
        world.bursts.clear()
        world.hyphae.clear()
        world.current = lambda x, y: (0, 0)
        world.replenish_at = world.phage_replenish_at = math.inf
        return world

    def test_stationary_phage_ignores_currents(self):
        world = self.world()
        world.bacteria.clear()
        world.current = lambda x, y: (3, -2)
        advance(world, 5)
        self.assertEqual((world.phages[0].x, world.phages[0].y), (35, 30))

    def test_swimming_host_gets_an_infection_roll_after_approaching(self):
        world = self.world()
        host, phage = world.bacteria[0], world.phages[0]
        host.x, host.angle, host.speed = phage.x - PHAGE_CONTACT - 3, 0, 2
        with patch.object(world.rng, "random", return_value=0) as roll:
            advance(world, 1)
            self.assertIsNone(host.infection)
            self.assertEqual(roll.call_count, 0, "proximity alone must not consume an encounter")
            self.assertNotIn(host.id, phage.contacts)
            advance(world, 1)
            self.assertIsNotNone(host.infection)
            self.assertEqual(roll.call_count, 1)
        self.assertEqual(world.infections, 1)
        self.assertFalse(world.phages)

    def test_failed_approach_rolls_once_until_genuine_separation(self):
        world = self.world()
        host, phage = world.bacteria[0], world.phages[0]
        with patch.object(world.rng, "random", return_value=1) as roll:
            for gap in (0.9, 0.4, -0.1, 0.2, -0.1, 0.8, -0.1):
                host.x = phage.x - PHAGE_CONTACT - gap
                world._update_phages(STEP)
            self.assertEqual(roll.call_count, 1)
            host.x = phage.x - PHAGE_CONTACT - 2
            world._update_phages(STEP)
            host.x = phage.x - PHAGE_CONTACT + 0.1
            world._update_phages(STEP)
            self.assertEqual(roll.call_count, 2)

    def test_red_blood_cells_can_still_displace_a_settled_phage(self):
        world = self.world()
        world.bacteria.clear()
        world.red_cells = [Drifter(33, 30, 0, 5)]
        world._resolve_obstacles()
        self.assertGreater(world.phages[0].x, 35)
        self.assertEqual(world.red_cells[0].x, 33)

    def test_probability_is_rolled_once_per_encounter(self):
        world = self.world()
        with patch.object(world.rng, "random", return_value=INFECTION_CHANCE + 0.1) as roll:
            for _ in range(120):
                world._update_phages(STEP)
            self.assertEqual(roll.call_count, 1)
            self.assertIsNone(world.bacteria[0].infection)
            world.bacteria[0].x = 10
            world._update_phages(STEP)
            world.bacteria[0].x = 35 - PHAGE_CONTACT + 0.1
            world._update_phages(STEP)
            self.assertEqual(roll.call_count, 2)
        with patch.object(world.rng, "random", return_value=INFECTION_CHANCE - 0.1):
            world.bacteria[0].x = 10
            world._update_phages(STEP)
            world.bacteria[0].x = 35 - PHAGE_CONTACT + 0.1
            world._update_phages(STEP)
        self.assertIsNotNone(world.bacteria[0].infection)
        self.assertFalse(world.phages, "the infecting phage must be taken up")

    def test_full_viral_cycle_ends_in_a_host_burst_and_multiple_phages(self):
        world = self.world()
        with patch.object(world.rng, "random", return_value=0):
            world._update_phages(STEP)
        bacterium = world.bacteria[0]
        bacterium.divide_at = 0
        for seconds, stage in [
            (2, "attachment"),
            (2, "injection"),
            (5, "replication"),
            (7, "assembly"),
            (6, "lysis"),
        ]:
            advance(world, seconds)
            self.assertEqual(viral_stage(bacterium.infection.age)[0], stage)
            self.assertEqual(len(world.bacteria), 1, "infected bacteria must not divide")
        advance(world, 3)
        self.assertNotIn(0, world.bacteria)
        self.assertEqual(world.lysed, 1)
        self.assertGreaterEqual(len(world.phages), 4)
        self.assertLessEqual(len(world.phages), 7)
        self.assertTrue(world.bursts)
        self.assertTrue(any(p.flight > 0 for p in world.phages.values()))
        advance(world, 3)
        positions = [(p.x, p.y) for p in world.phages.values()]
        advance(world, 2)
        self.assertEqual(positions, [(p.x, p.y) for p in world.phages.values()])
        self.assertFalse(world.bursts)

    def test_release_is_capped_and_expired_phages_are_removed(self):
        world = self.world()
        world.phages.clear()
        for index in range(world._phage_limit() - 2):
            world._add_phage(60 + index * 2, 40)
        world._lyse(world.bacteria[0])
        self.assertEqual(len(world.phages), world._phage_limit())
        phage = next(iter(world.phages.values()))
        phage.lifetime = STEP / 2
        world._update_phages(STEP)
        self.assertNotIn(phage.id, world.phages)

    def test_phagocytosis_suppresses_viral_release(self):
        world = self.world()
        world.phages.clear()
        bacterium = world.bacteria[0]
        bacterium.owner = 0
        bacterium.infection = Infection(VIRAL_TIME - 0.01)
        cell = Cell(
            0,
            20,
            30,
            10,
            0,
            0,
            state=State.ENCLOSE,
            target=0,
            elapsed=SEAL_TIME + 0.1,
            capture_distance=15,
        )
        world.cells = [cell]
        advance(world, 3.1)
        self.assertNotIn(0, world.bacteria)
        self.assertEqual(world.engulfed, 1)
        self.assertEqual(world.lysed, 0)
        self.assertFalse(world.phages)

    def test_lysis_releases_a_pursuing_cell_and_keeps_phages_outside(self):
        world = self.world()
        world.phages.clear()
        bacterium = world.bacteria[0]
        bacterium.owner = 0
        bacterium.infection = Infection(VIRAL_TIME - STEP / 2)
        cell = Cell(0, 20, 30, 10, 0, 0, state=State.APPROACH, target=0)
        world.cells = [cell]
        world.update()
        self.assertEqual(cell.state, State.WANDER)
        self.assertIsNone(cell.target)
        for phage in world.phages.values():
            dx, dy = phage.x - cell.x, phage.y - cell.y
            self.assertGreaterEqual(
                math.hypot(dx, dy), cell.outline(math.atan2(dy, dx), world.time) + PHAGE_PADDING
            )

    def test_viral_stages_are_visually_distinct_and_rendering_is_read_only(self):
        world = self.world()
        world.phages.clear()
        bacterium = world.bacteria[0]
        frames = []
        for age in (1, 5, 10, 18, 23):
            bacterium.infection = Infection(age=age)
            before = (bacterium.x, bacterium.y, bacterium.infection.age, world.rng.getstate())
            frame = render(world, True)
            frames.append(frame.plain())
            self.assertEqual(
                before, (bacterium.x, bacterium.y, bacterium.infection.age, world.rng.getstate())
            )
        self.assertEqual(len(set(frames)), 5)

    def test_swelling_host_keeps_its_full_body_outside_membranes(self):
        world = self.world()
        world.phages.clear()
        cell = Cell(0, 12, 30, 7, 0, 0, cooldown=999)
        world.cells = [cell]
        bacterium = world.bacteria[0]
        bacterium.x = 23
        bacterium.infection = Infection(8)
        for _ in range(240):
            world.update()
            dx, dy = bacterium.x - cell.x, bacterium.y - cell.y
            self.assertGreaterEqual(
                math.hypot(dx, dy),
                cell.outline(math.atan2(dy, dx), world.time) + bacterial_padding(bacterium) - 1e-6,
            )

    def test_resize_preserves_infection_and_applies_the_phage_cap(self):
        world = self.world()
        bacterium = world.bacteria[0]
        bacterium.infection = Infection(12)
        for _ in range(20):
            world._add_phage(60, 50)
        world.resize(32, 12)
        self.assertEqual(bacterium.infection.age, 12)
        self.assertLessEqual(len(world.phages), world._phage_limit())
        for phage in world.phages.values():
            self.assertTrue(math.isfinite(phage.x + phage.y))


class CliTests(unittest.TestCase):
    def command(self, *args):
        return subprocess.run(
            [sys.executable, "cells.py", *args],
            cwd=Path(__file__).resolve().parents[1],
            text=True,
            capture_output=True,
            timeout=5,
        )

    def test_snapshot_can_be_used_in_pipes_and_is_exactly_sized(self):
        result = self.command("--snapshot", "--seed", "42", "--size", "80x24")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(result.stdout.splitlines()), 24)
        self.assertTrue(all(len(line) == 80 for line in result.stdout.splitlines()))
        self.assertTrue(result.stdout.isascii())
        self.assertNotIn("\x1b", result.stdout)
        self.assertEqual(result.stdout, self.command("--snapshot", "--seed", "42").stdout)

    def test_snapshot_at_zero(self):
        result = self.command("--snapshot", "--at", "0", "--size", "1x1")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_and_nonfinite_options_fail_cleanly(self):
        for option, value in [
            ("--speed", "nan"),
            ("--density", "inf"),
            ("--fps", "0"),
            ("--size", "no"),
            ("--size", "0x24"),
            ("--at", "-1"),
        ]:
            with self.subTest(option=option, value=value):
                result = self.command("--snapshot", option, value)
                self.assertEqual(result.returncode, 2)
                self.assertNotIn("Traceback", result.stderr)

    def test_non_terminal_has_actionable_error(self):
        result = self.command()
        self.assertEqual(result.returncode, 2)
        self.assertIn("--snapshot", result.stderr)


@unittest.skipUnless(os.name == "posix", "requires a POSIX pseudo-terminal")
class TerminalTests(unittest.TestCase):
    def session(
        self,
        keys=b"",
        extra=(),
        terminate=False,
        resize=False,
        events=(),
        activity=None,
        startup_delay=0,
    ):
        import fcntl
        import pty
        import select
        import struct
        import termios

        master, slave = pty.openpty()
        before = terminal_modes(slave)
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
        env = os.environ | {"TERM": "xterm-256color", "LANG": "C.UTF-8"}
        command = [sys.executable, "cells.py", "--seed", "42", "--duration", "2", *extra]
        if startup_delay:
            # Delay only the child interpreter, before app imports and handlers.
            command = [
                sys.executable,
                "-c",
                "import runpy, sys, time; time.sleep(float(sys.argv.pop(1))); "
                "sys.argv[0] = 'cells.py'; runpy.run_path('cells.py', run_name='__main__')",
                str(startup_delay),
                *command[2:],
            ]
        process = subprocess.Popen(
            command,
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=env,
            cwd=Path(__file__).resolve().parents[1],
            start_new_session=True,
        )
        output = bytearray()
        start = time.monotonic()
        sent = False
        event_index = 0
        ready_at = None
        try:
            while process.poll() is None and time.monotonic() - start < 4:
                readable = select.select([master], [], [], 0.02)[0]
                if readable:
                    output.extend(os.read(master, 65536))
                now = time.monotonic()
                if ready_at is None:
                    # Do not send raw mouse escapes before curses enables input.
                    # Interactive sessions must have drawn their first footer.
                    marker = b"? help" if "--interactive" in extra else b"\x1b[?1049h"
                    if marker in output:
                        ready_at = now
                elapsed = now - ready_at if ready_at is not None else None
                if readable and activity is not None and elapsed is not None:
                    activity.append(elapsed)
                # Input and output activity share a clock that starts at UI readiness,
                # so interpreter startup cannot reorder mouse press/release events.
                while (
                    elapsed is not None
                    and event_index < len(events)
                    and elapsed >= events[event_index][0]
                ):
                    os.write(master, events[event_index][1])
                    event_index += 1
                if not sent and elapsed is not None and elapsed > 0.2:
                    if resize:
                        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 16, 40, 0, 0))
                        process.send_signal(signal.SIGWINCH)
                    if keys:
                        os.write(master, keys)
                    if terminate:
                        process.send_signal(signal.SIGTERM)
                    sent = True
            process.wait(timeout=1)
            while select.select([master], [], [], 0)[0]:
                output.extend(os.read(master, 65536))
            self.assertEqual(process.returncode, 0, output.decode(errors="replace"))
            self.assertNotIn(b"Traceback", output)
            self.assertEqual(terminal_modes(slave), before, "terminal modes must be restored")
            self.assertIn(b"\x1b[?1049l", output, "must leave the alternate screen")
            return time.monotonic() - start, bytes(output)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)
            os.close(slave)

    def test_quit_is_responsive_even_at_one_fps(self):
        elapsed, _ = self.session(b"q", ("--fps", "1"))
        self.assertLess(elapsed, 1.2)

    def test_screensaver_exits_on_any_key(self):
        elapsed, _ = self.session(b"x", ("--screensaver",))
        self.assertLess(elapsed, 1.2)

    def test_controls_and_resize(self):
        self.session(b" ?s++--r? ", ("--ascii", "--theme", "amber"), resize=True)

    def test_duration_is_respected_at_one_fps(self):
        elapsed, _ = self.session(extra=("--fps", "1", "--duration", ".25"))
        self.assertLess(elapsed, 0.9)

    def test_new_display_controls_and_help_scroll(self):
        self.session(
            b"?jjkk?s",
            (
                "--style",
                "raster",
                "--scene",
                "microbial",
                "--calm",
                "--theme",
                "light",
                "--observe",
                "--stats",
                "--color",
                "always",
                "--unicode",
                "always",
            ),
            resize=True,
        )

    def test_stained_and_raster_fallbacks_restore_terminal(self):
        self.session(extra=("--style", "stained", "--duration", ".3"))
        self.session(extra=("--style", "raster", "--ascii", "--color", "never", "--duration", ".3"))

    def test_fast_simulation_still_quits_responsively(self):
        elapsed, _ = self.session(b"q", ("--speed", "8", "--fps", "1", "--density", "3"))
        self.assertLess(elapsed, 1.2)

    def test_magnified_tools_pan_resize_and_cleanup(self):
        _, output = self.session(
            b"HJKL1\t2\n3ll\n4\n",
            ("--interactive", "--magnification", "detail", "--style", "raster"),
            resize=True,
        )
        self.assertIn(b"? help", output)
        self.assertIn(b"1006", output)

    def test_interactive_keyboard_tools_and_resize(self):
        _, output = self.session(
            b"3hjk4\r1\t\r", ("--interactive", "--ascii", "--duration", ".7"), resize=True
        )
        self.assertIn(b"? help", output)
        self.assertNotIn(b"PAUSED", output)

    def test_interactive_mouse_reports_and_cleanup(self):
        _, output = self.session(
            b"3\x1b[<0;2;2M\x1b[<0;2;2m", ("--interactive", "--ascii", "--duration", ".7")
        )
        self.assertIn(b"? help", output)
        if b"1006" not in output:
            self.skipTest("terminal does not advertise SGR mouse reports")
        self.assertIn(b"? help", output)

    def test_mouse_input_waits_for_ui_after_slow_interpreter_startup(self):
        _, output = self.session(
            b"3\x1b[<0;2;2M\x1b[<0;2;2m",
            ("--interactive", "--ascii", "--duration", ".7"),
            startup_delay=0.5,
        )
        self.assertIn(b"? help", output)
        self.assertNotIn(b"^[[<", output, "mouse input must not echo before curses starts")

    def test_mouse_release_keeps_animation_running_without_further_input(self):
        activity = []
        elapsed, output = self.session(
            b"3\x1b[<0;2;2M",
            ("--interactive", "--ascii", "--duration", "1.1"),
            events=((0.45, b"\x1b[<0;2;2m"),),
            activity=activity,
        )
        if b"1006" not in output:
            self.skipTest("terminal does not advertise SGR mouse reports")
        self.assertIn(b"? help", output)
        self.assertNotIn(b"PAUSED", output)
        self.assertTrue(any(0.6 < at < 0.9 for at in activity), "must draw after mouse release")
        self.assertLess(elapsed, 1.8, "mouse release must not block the session deadline")

    def test_interactive_sigterm_restores_terminal(self):
        self.session(extra=("--interactive",), terminate=True)

    def test_sigterm_restores_terminal(self):
        self.session(terminate=True)

    def test_sigterm_cleanup_after_slow_interpreter_startup(self):
        self.session(terminate=True, startup_delay=0.4)


if __name__ == "__main__":
    unittest.main()
