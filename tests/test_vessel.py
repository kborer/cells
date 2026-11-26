"""Vessel containment, shared repair lifecycles, tools, and long-run cleanup."""

import math
import pickle
import unittest

from terminal_cells import World, Cell, State
from terminal_cells.capabilities import RenderCapabilities
from terminal_cells.frame import Frame, Ink
from terminal_cells.geometry import Target, hit_test, targets, endothelial_rows
from terminal_cells.interaction import describe
from terminal_cells.models import STEP
from terminal_cells.scenes import make_scene
from terminal_cells.style_checks import check_style
from terminal_cells.styles import STYLES, RenderOptions
from terminal_cells.viewport import Camera, Grid, projection
from terminal_cells.vessel_render import draw_wall
from tools.endurance import check_world


def advance(world, seconds):
    for _ in range(round(seconds / STEP)):
        world.update()


class VesselTests(unittest.TestCase):
    def test_endothelial_nuclei_remain_between_connected_consistent_borders(self):
        world = World(240, 60, 42, scene="vessel", rare_events=False)
        world.cells.clear()
        world.bacteria.clear()
        world.red_cells.clear()
        world.phages.clear()
        world.vessel.fibroblasts.clear()
        world.vessel.platelets.clear()
        for scale in (0.5, 1, 3):
            for top in (0, 0.7, 1.6):
                grid = Grid(scale, left=0.35, top=top, columns=240, rows=190)
                with projection(grid):
                    frame = Frame(240, 190)
                    draw_wall(frame, world)
                for obj in world.vessel.endothelium:
                    col = round(grid.column(obj.x))
                    inner, outer, nucleus = endothelial_rows(world.vessel, obj.x, obj.side, grid)
                    if not (
                        0 <= col < frame.width
                        and 0 <= min(inner, outer) <= max(inner, outer) < frame.height
                    ):
                        continue
                    with self.subTest(scale=scale, top=top, x=obj.x, side=obj.side):
                        self.assertGreater(abs(inner - outer), 1)
                        self.assertTrue(min(inner, outer) < nucleus < max(inner, outer))
                        self.assertEqual(frame.pixels[nucleus][col].char, "o")
                        for row in (inner, outer):
                            self.assertIs(frame.pixels[row][col].ink, Ink.ENDOTHELIUM)
                            self.assertNotEqual(frame.pixels[row][col].char, "o")
                        self.assertEqual(
                            hit_test(world, col, nucleus, grid=grid).kind, "endothelium"
                        )

    def test_scene_is_opt_in_and_small_windows_degrade_then_recover(self):
        self.assertIsNone(World(100, 40, 42).vessel)
        world = World(20, 8, 42, scene="vessel")
        self.assertFalse(world.vessel.room)
        self.assertFalse(world.vessel.injure(10, -1))
        advance(world, 2)
        check_world(world)
        world.resize(100, 40)
        advance(world, 1)
        self.assertEqual(len(world.vessel.fibroblasts), 2)
        self.assertTrue(world.vessel.platelets)
        self.assertTrue(world.vessel.endothelium)
        check_world(world)

    def test_walls_block_free_bodies_and_edge_arrivals_use_open_ends(self):
        world = World(120, 40, 19, scene="vessel", rare_events=False)
        vessel = world.vessel
        self.assertTrue(world.is_blocked(60, 2))
        self.assertTrue(world.is_blocked(60, 78))
        self.assertTrue(vessel.injure(60, 1))
        self.assertTrue(world.is_blocked(60, 79))  # No passive leakage at a wound.
        for _ in range(300):
            world.update()
        for obj in [*world.bacteria.values(), *world.red_cells, *world.phages.values()]:
            if getattr(obj, "owner", None) is not None or obj.entry is not None:
                continue
            low, high = vessel.bounds(obj.x)
            self.assertGreaterEqual(obj.y, low)
            self.assertLessEqual(obj.y, high)
        for _ in range(20):
            x, y, angle = world._edge_position(3)
            self.assertIn(angle, (0, math.pi))
            self.assertGreater(y, vessel.wall(x, -1))
            self.assertLess(y, vessel.wall(x, 1))

    def test_rolling_adhesion_and_crossing_release_claims_and_leave_gradually(self):
        world = make_scene("vessel-rolling")
        cell = world.cells[0]
        phases = set()
        largest_step = 0
        for _ in range(round(41 / STEP)):
            before = cell.x, cell.y
            world.update()
            if world.vessel.transit is not None:
                phases.add(world.vessel.transit.phase)
                self.assertIn(world.vessel.transit.phase, describe(world, Target("cell", cell)))
            largest_step = max(largest_step, math.dist(before, (cell.x, cell.y)))
        self.assertEqual(phases, {"rolling", "adhering", "crossing junction"})
        self.assertLess(largest_step, 0.3)
        self.assertEqual(world.vessel.crossed, 1)
        self.assertNotIn(cell, world.cells)
        self.assertGreater(cell.y - cell.extent(), world.height)
        self.assertIsNone(cell.target)
        self.assertIsNone(world.vessel.transit)
        self.assertLess(world.large_arrival_at, math.inf)

    def test_busy_immune_cells_are_not_stolen_from_capture_or_division(self):
        for state in (State.APPROACH, State.ENCLOSE, State.DIVIDE):
            world = make_scene("vessel-rolling")
            world.cells[0].state = state
            world.vessel.update(world, STEP)
            self.assertIsNone(world.vessel.transit)
        world.cells = [Cell(1, 50, 40, 10, 0, 0, kind="macrophage")]
        world.vessel.update(world, STEP)
        self.assertIsNone(world.vessel.transit)

    def test_platelets_contact_then_spread_and_make_a_local_bounded_plug(self):
        world = make_scene("platelet-plug")
        self.assertTrue(all(p.phase == "resting" for p in world.vessel.platelets))
        advance(world, 1)
        self.assertTrue(any(p.phase == "activated" for p in world.vessel.platelets))
        advance(world, 24)
        bound = [p for p in world.vessel.platelets if p.phase == "adhered"]
        self.assertGreaterEqual(len(bound), 6)
        self.assertLessEqual(len(bound), 8)
        self.assertEqual(len({p.slot for p in bound}), len(bound))
        for obj in bound:
            self.assertLess(abs(obj.x - world.vessel.wound.x), 6)
        frame = STYLES["classic"].render(world, RenderOptions())
        self.assertTrue(any(p.ink is Ink.FIBRIN for row in frame.pixels for p in row))
        world.vessel.wound.age = 111
        advance(world, 1)
        self.assertFalse(any(p.phase == "adhered" for p in world.vessel.platelets))
        advance(world, 16)
        self.assertTrue(all(p not in world.vessel.platelets for p in bound))
        check_world(world)

    def test_fibroblasts_repair_then_matrix_decays_and_injury_can_recur(self):
        world = make_scene("wound-repair")
        advance(world, 60)
        self.assertEqual(world.vessel.healed, 1)
        self.assertIsNone(world.vessel.wound)
        self.assertGreater(world.vessel.deposited, 0)
        self.assertTrue(world.vessel.fibers)
        for obj in world.vessel.fibroblasts:
            low, high = world.vessel.bounds(obj.x)
            self.assertTrue(obj.y < low or obj.y > high)
        advance(world, 110)
        self.assertFalse(world.vessel.fibers)
        self.assertTrue(world.vessel.injure(45, -1))
        self.assertFalse(world.vessel.injure(70, 1))
        advance(world, 240)
        self.assertIsNone(world.vessel.wound)
        self.assertEqual(world.vessel.healed, 2)
        check_world(world)

    def test_ambient_injuries_obey_no_events_but_manual_injuries_still_work(self):
        world = World(100, 40, 42, scene="vessel", rare_events=False)
        world.time = 100
        world.update()
        self.assertIsNone(world.vessel.wound)
        obj = world.vessel.endothelium[2]
        target = Target("endothelium", obj)
        self.assertIn("injury", world.lab.lyse(world, target, obj.x, obj.y))
        self.assertIsNotNone(world.vessel.wound)
        self.assertEqual(world.vessel.injuries, 1)
        world.lab.lyse(world, target, obj.x, obj.y)
        self.assertEqual(world.vessel.injuries, 1)

    def test_tools_pick_new_entities_and_replacements_arrive_from_edges(self):
        world = make_scene("platelet-plug")
        vessel = world.vessel
        obj = vessel.platelets[0]
        obj.x, obj.y = 40, 40
        target = hit_test(world, 40, 20)
        self.assertIs(target.obj, obj)
        self.assertIn("Platelet", describe(world, target))
        world.lab.lyse(world, target, 40, 40)
        self.assertFalse(target.alive(world))
        advance(world, STEP)
        self.assertLess(vessel.platelets[-1].x, 0)
        fibro = vessel.fibroblasts[0]
        target = Target("fibroblast", fibro)
        world.lab.lyse(world, target, fibro.x, fibro.y)
        self.assertFalse(target.alive(world))
        advance(world, STEP)
        self.assertLess(next(f for f in vessel.fibroblasts if f.side == fibro.side).x, 0)
        self.assertTrue(any(t.kind == "endothelium" for t in targets(world)))
        for style in STYLES.values():
            check_style(style, world, RenderOptions())
        check_world(world)

    def test_lysing_a_crossing_cell_clears_the_transit_immediately(self):
        world = make_scene("vessel-rolling", at=24)
        cell = world.cells[0]
        world.lab.lyse(world, Target("cell", cell), cell.x, cell.y)
        self.assertIsNone(world.vessel.transit)
        check_world(world)
        advance(world, 1)
        check_world(world)

    def test_stir_moves_free_platelets_immediately_but_keeps_attached_plug(self):
        world = make_scene("platelet-plug", at=25)
        vessel = world.vessel
        bound = next(p for p in vessel.platelets if p.phase == "adhered")
        before = bound.x, bound.y
        world.lab.stir(world, *before)
        self.assertEqual(before, (bound.x, bound.y))
        vessel.platelets.pop()
        vessel._add_platelet()
        free = vessel.platelets[-1]
        free.x, free.y = 20, 40
        world.lab.stir(world, 20, 40)
        self.assertNotEqual((free.x, free.y), (20, 40))

    def test_resize_cancels_crossing_and_keeps_state_bounded_and_pickable(self):
        world = make_scene("vessel-rolling", at=24)
        self.assertIsNotNone(world.vessel.transit)
        old = Target("endothelium", world.vessel.endothelium[0])
        for size in ((1, 1), (200, 60), (60, 22), (100, 40)):
            world.resize(*size)
            advance(world, 1)
            self.assertIsNone(world.vessel.transit)
            self.assertFalse(old.alive(world))
            check_world(world)
            frame = STYLES["classic"].render(world, RenderOptions())
            self.assertEqual((frame.width, frame.height), size)

    def test_all_styles_and_camera_scales_share_read_only_lifecycles(self):
        profiles = (
            RenderCapabilities(),
            RenderCapabilities(
                unicode=True, colors=256, backgrounds=True, blocks=True, color_pairs=256
            ),
        )
        for scene, at in (("vessel-rolling", 24), ("platelet-plug", 25), ("wound-repair", 40)):
            world = make_scene(scene, at=at)
            for style in STYLES.values():
                for caps in profiles:
                    for scale in ("overview", "normal", "detail"):
                        camera = Camera(100, 40, scale)
                        camera.focus(world)
                        with self.subTest(scene=scene, style=style.name, scale=scale, caps=caps):
                            check_style(
                                style, world, RenderOptions.resolve(caps, fill=True), camera=camera
                            )

    def test_seeded_long_run_repeats_repairs_without_retaining_old_state(self):
        first = World(100, 32, 42, scene="vessel")
        second = World(100, 32, 42, scene="vessel")
        for i in range(18000):
            first.update()
            second.update()
            if i % 900 == 0:
                check_world(first)
        self.assertEqual(pickle.dumps(first), pickle.dumps(second))
        self.assertGreaterEqual(first.vessel.healed, 2)
        self.assertGreater(first.vessel.deposited, 0)
        self.assertGreater(first.vessel.crossed, 0)
        self.assertLessEqual(len(first.vessel.fibers), 16)
