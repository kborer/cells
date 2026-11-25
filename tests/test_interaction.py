"""Experimental tools, visible-body targeting, compartment cleanup, and mouse fallback."""

import math
import pickle
import unittest
from unittest.mock import patch

from terminal_cells import (
    World,
    Cell,
    Bacterium,
    Drifter,
    Phage,
    Infection,
    Hypha,
    render,
    State,
    STEP,
)
from terminal_cells.events import Sighting
from terminal_cells.interaction import (
    Interaction,
    describe,
    enable_mouse,
    restore_mouse,
    read_click,
)
from terminal_cells.lab import Target, hit_test
from terminal_cells.cli import parser


def advance(world, seconds):
    for _ in range(round(seconds / STEP)):
        world.update(events=False)


class MouseBackend:
    class error(Exception):
        pass

    BUTTON1_PRESSED, BUTTON1_CLICKED, BUTTON1_RELEASED = 1, 2, 4
    KEY_LEFT, KEY_RIGHT, KEY_UP, KEY_DOWN, KEY_ENTER = 260, 261, 259, 258, 343

    def __init__(self, available=True):
        self.available = available
        self.masks = []
        self.intervals = []
        self.event = (0, 20, 10, 0, self.BUTTON1_PRESSED)

    def mousemask(self, mask):
        self.masks.append(mask)
        return (mask if self.available else 0), 17

    def mouseinterval(self, interval):
        self.intervals.append(interval)
        return 200

    def getmouse(self):
        return self.event


class InteractionTests(unittest.TestCase):
    def world(self):
        world = World(120, 40, 42, rare_events=False)
        for name in ("cells", "red_cells", "debris", "hyphae", "nutrients"):
            getattr(world, name).clear()
        world.bacteria.clear()
        world.phages.clear()
        world.replenish_at = world.large_arrival_at = world.fungal_arrival_at = math.inf
        world.nutrient_at = world.phage_replenish_at = math.inf
        world.current = lambda x, y: (0, 0)
        return world

    def test_mouse_capture_and_restoration_and_release_filtering(self):
        backend = MouseBackend()
        available, mask, interval = enable_mouse(backend)
        self.assertTrue(available)
        self.assertEqual(read_click(backend), (20, 10))
        backend.event = (0, 20, 10, 0, backend.BUTTON1_RELEASED)
        self.assertIsNone(read_click(backend))
        restore_mouse(backend, mask, interval)
        self.assertEqual(backend.masks, [7, 17])
        self.assertEqual(backend.intervals, [0, 200])
        self.assertFalse(enable_mouse(MouseBackend(False))[0])

    def test_mouse_restores_when_the_session_is_interrupted(self):
        import importlib

        cli = importlib.import_module("terminal_cells.cli")
        for failure in (KeyboardInterrupt, RuntimeError):
            with self.subTest(failure=failure):
                backend = MouseBackend()
                with (
                    patch.object(cli, "load_curses", return_value=backend),
                    patch.object(cli, "_session", side_effect=failure),
                ):
                    with self.assertRaises(failure):
                        cli.run(None, parser().parse_args(["--interactive"]))
                self.assertEqual(backend.masks[-1], 17)
                self.assertEqual(backend.intervals[-1], 200)

    def test_hit_testing_tracks_visible_layers_and_avoids_distant_entities(self):
        world = self.world()
        cell = Cell(0, 50, 40, 12, 0, 0)
        microbe = Bacterium(0, 50, 40, 0, 0, "rod", 999, 999)
        world.cells = [cell]
        world.bacteria = {0: microbe}
        self.assertIs(hit_test(world, 50, 20).obj, cell)
        cell.state, cell.target, microbe.owner = State.ENCLOSE, 0, 0
        microbe.x = 65
        self.assertIs(hit_test(world, 65, 20).obj, microbe)
        self.assertIsNone(hit_test(world, 5, 3))
        world.phages = {0: Phage(0, 20, 20, angle=0)}
        self.assertEqual(hit_test(world, 20, 10).kind, "phage")
        self.assertIsNone(hit_test(world, 19, 10))

    def test_nuclear_foreground_remains_selectable_over_captured_cargo(self):
        from terminal_cells import Ink

        world = self.world()
        cell = Cell(0, 50, 40, 12, 0, 0, state=State.ENCLOSE, elapsed=9, target=0)
        host = Bacterium(0, 47, 40, 0, 0, "rod", 999, 999, owner=0)
        world.cells, world.bacteria = [cell], {0: host}
        points = [
            (x, y)
            for y, row in enumerate(render(world).pixels)
            for x, pixel in enumerate(row)
            if pixel.ink is Ink.NUCLEOLUS
        ]
        self.assertTrue(points)
        for x, y in points:
            self.assertIs(hit_test(world, x, y).obj, cell)

    def test_visible_arrival_can_be_targeted_and_ruptured(self):
        from terminal_cells.models import Entry

        world = self.world()
        particle = Phage(0, 1, 40, entry=Entry(0, 5, 6, 40))
        world.phages = {0: particle}
        target = hit_test(world, 1, 20)
        self.assertIs(target.obj, particle)
        world.lab.lyse(world, target, 1, 40)
        advance(world, 1.3)
        self.assertFalse(world.phages)

    def test_keyboard_tools_inspection_and_visible_toolbar(self):
        world = self.world()
        cell = Cell(0, 40, 30, 12, 0, 0)
        world.cells = [cell]
        control = Interaction(0, 0)
        control.key(world, 9, MouseBackend, 0)
        self.assertIs(control.selected.obj, cell)
        self.assertEqual((control.col, control.row), (40, 15))
        control.key(world, 10, MouseBackend, 0)
        self.assertIn("Macrophage", describe(world, control.selected))
        cell.x += 2
        frame = render(world)
        scene_rows = frame.plain().splitlines()[-3:-1]
        control.draw(frame, world, 1)
        self.assertEqual(control.col, 42)
        self.assertEqual(frame.plain().splitlines()[-3:-1], scene_rows)
        footer = frame.plain().splitlines()[-1].rstrip()
        self.assertIn("? help", footer)
        self.assertIn("[Inspect]", footer)
        self.assertIn("Macrophage", footer)
        control.key(world, ord("4"), MouseBackend, 2)
        control.key(world, MouseBackend.KEY_RIGHT, MouseBackend, 2)
        control.key(world, 10, MouseBackend, 2)
        self.assertEqual(len(world.lab.stirs), 1)

    def test_tool_and_refusal_feedback_stay_on_one_row_and_expire(self):
        world = self.world()
        control = Interaction(0, 0)
        control.key(world, ord("2"), MouseBackend, 0)
        frame = render(world)
        before = frame.plain().splitlines()[:-1]
        control.draw(frame, world, 1)
        self.assertIn("Lyse selected", frame.plain().splitlines()[-1])
        control.apply(world, 2)
        control.draw(frame, world, 3)
        self.assertIn("No cell at cursor", frame.plain().splitlines()[-1])
        control.draw(frame, world, 7)
        self.assertNotIn("No cell at cursor", frame.plain().splitlines()[-1])
        # Reticles can affect the scene; feedback itself only occupies the footer.
        self.assertEqual(frame.plain().splitlines()[2:-1], before[2:])

    def test_toolbar_click_is_never_destructive_and_resize_clamps_aim(self):
        world = self.world()
        control = Interaction(100, 35, tool=2)
        control.click(world, 10, 39, 0)
        self.assertFalse(world.nutrients)
        control.click(world, 10, 38, 0)
        self.assertEqual(len(world.nutrients), 1)
        world.resize(40, 12)
        control.follow(world)
        self.assertTrue(0 <= control.col < 40 and 0 <= control.row < 11)

    def test_feed_is_bounded_and_requires_clear_fluid(self):
        world = self.world()
        world.cells = [Cell(0, 60, 40, 12, 0, 0)]
        self.assertIn("outside", world.lab.feed(world, 60, 40))
        self.assertFalse(world.nutrients)
        for i in range(20):
            world.lab.feed(world, 5 + i, 5)
        self.assertEqual(len(world.nutrients), 4)
        self.assertLessEqual(len(world.lab.pings), 8)

    def test_cell_lysis_is_immediate_releases_claims_and_scatters_organelles(self):
        world = self.world()
        cell = Cell(0, 50, 40, 12, 0, 0, state=State.ENCLOSE, target=0)
        microbe = Bacterium(0, 65, 40, 0, 0, "rod", 999, 999, owner=0)
        world.cells, world.bacteria = [cell], {0: microbe}
        Interaction(60, 20, tool=1).click(world, 60, 20, 0)
        self.assertEqual(world.time, 0)
        self.assertFalse(world.cells)
        self.assertIsNone(microbe.owner)
        roles = {p.role for p in world.lab.ruptures[0].fragments}
        self.assertTrue({"nucleus", "mitochondrion", "reticulum", "vesicle"} <= roles)
        self.assertTrue(world.nutrients)
        advance(world, 7.1)
        self.assertFalse(world.lab.ruptures)

    def test_red_cell_ghost_has_no_nuclear_fragments(self):
        world = self.world()
        red = Drifter(50, 40, 0, 5)
        world.red_cells = [red]
        world.lab.lyse(world, Target("red", red), 50, 40)
        advance(world, 1.3)
        self.assertFalse(world.red_cells)
        self.assertEqual({f.role for f in world.lab.ruptures[0].fragments}, {"red", "red_dim"})
        self.assertTrue(any(p.char == ":" for row in render(world).pixels for p in row))

    def test_infected_host_releases_only_already_assembled_phages(self):
        for age, expected in ((2, 0), (10, 0), (15, 2), (20, 5)):
            with self.subTest(age=age):
                world = self.world()
                host = Bacterium(0, 60, 40, 0, 0, "rod", 999, 999, infection=Infection(age))
                world.bacteria = {0: host}
                world.lab.lyse(world, Target("microbe", host), 60, 40)
                advance(world, 1.3)
                self.assertNotIn(0, world.bacteria)
                self.assertEqual(len(world.phages), expected)

    def test_sealed_infected_cargo_stays_contained(self):
        world = self.world()
        owner = Cell(0, 60, 40, 12, 0, 0, state=State.ENCLOSE, elapsed=8, target=0)
        host = Bacterium(0, 65, 40, 0, 0, "rod", 999, 999, owner=0, infection=Infection(20))
        world.cells, world.bacteria = [owner], {0: host}
        world.lab.lyse(world, Target("microbe", host), 65, 40)
        advance(world, 1.3)
        self.assertFalse(world.phages)
        self.assertFalse(world.nutrients)
        self.assertNotIn(0, world.bacteria)
        self.assertIsNone(owner.target)
        self.assertEqual(owner.state, State.DIGEST)
        self.assertTrue(owner.vesicles)
        self.assertFalse(world.lab.ruptures[0].fragments)

    def test_cutting_fungus_preserves_surviving_network_and_regrowth_tips(self):
        world = self.world()
        fungus = Hypha([(40, 40), (43, 40), (46, 40)], [(0, 1), (1, 2)], [(2, 0)], 999)
        world.hyphae = [fungus]
        target = hit_test(world, 41, 20)
        self.assertEqual(target.segment, (0, 1))
        world.lab.lyse(world, target, 41, 40)
        advance(world, 1.3)
        self.assertEqual(fungus.edges, [(1, 2)])
        self.assertTrue({0, 1} <= {node for node, _ in fungus.tips})
        advance(world, 8)
        self.assertGreater(len(fungus.nodes), 3)

    def test_cut_only_detaches_riders_of_the_severed_edge(self):
        world = self.world()
        fungus = Hypha([(40, 40), (43, 40), (46, 40)], [(0, 1), (1, 2)], [(2, 0)], 999)
        world.hyphae = [fungus]
        first = Bacterium(0, 41, 40, 0, 0, "rod", 999, 999, rail=0, rail_from=0, rail_to=1)
        second = Bacterium(1, 45, 40, 0, 0, "rod", 999, 999, rail=0, rail_from=1, rail_to=2)
        world.bacteria = {0: first, 1: second}
        world.lab.lyse(world, Target("hypha", fungus, (0, 1)), 41, 40)
        world.lab.update(world, 1.3)
        self.assertIsNone(first.rail)
        self.assertEqual(second.rail, 0)

    def test_stir_immediately_moves_clicked_phage_debris_and_red_cells(self):
        # No simulation step: these must visibly respond even when paused.
        for kind in ("phage", "debris", "red", "capsid", "microbe", "fragment"):
            with self.subTest(kind=kind):
                world = self.world()
                if kind == "microbe":
                    obj = Bacterium(0, 60, 40, 0, 0, "rod", 999, 999)
                    world.bacteria = {0: obj}
                elif kind == "fragment":
                    cell = Cell(0, 60, 40, 12, 0, 0)
                    world.cells = [cell]
                    world.lab.lyse(world, Target("cell", cell), 65, 40)
                    obj = world.lab.ruptures[0].fragments[0]
                elif kind in ("phage", "capsid"):
                    obj = Phage(0, 60, 40)
                    if kind == "phage":
                        world.phages = {0: obj}
                    else:
                        world.spent_capsids = [obj]
                else:
                    obj = Drifter(60, 40, 0, 5 if kind == "red" else 1)
                    if kind == "red":
                        world.red_cells = [obj]
                    else:
                        world.debris = [obj]
                x, y = obj.x, obj.y
                control = Interaction(round(x), round(y / 2), tool=3)
                control.key(world, 10, MouseBackend, 0)
                self.assertEqual(world.time, 0)
                # Measured in terminal glyphs, rather than epsilon movement.
                self.assertGreater(math.hypot(obj.x - x, (obj.y - y) / 2), 3)
                self.assertLessEqual(math.hypot(*world.lab.flow(x, y)), 18 + 1e-12)
                pushed_x, pushed_y = obj.x, obj.y
                advance(world, 0.5)
                self.assertGreater(math.hypot(obj.x - pushed_x, (obj.y - pushed_y) / 2), 2)
                advance(world, 5)
                self.assertFalse(world.lab.stirs)

    def test_stir_is_local_and_repeated_clicks_stay_bounded(self):
        world = self.world()
        near, far = Phage(0, 68, 40), Phage(1, 100, 40)
        world.phages = {0: near, 1: far}
        world.lab.stir(world, 60, 40)
        self.assertGreater(math.hypot(near.x - 68, (near.y - 40) / 2), 1)
        self.assertEqual((far.x, far.y), (100, 40))
        for _ in range(20):
            world.lab.stir(world, 60, 40)
        self.assertEqual(len(world.lab.stirs), 4)
        self.assertLessEqual(math.hypot(*world.lab.flow(60, 40)), 18 + 1e-12)
        self.assertEqual((far.x, far.y), (100, 40))

    def test_stir_preserves_captured_microbes(self):
        world = self.world()
        owner = Cell(0, 60, 40, 12, 0, 0, state=State.ENCLOSE, elapsed=8, target=0)
        cargo = Bacterium(0, 65, 40, 0, 0, "rod", 999, 999, owner=0)
        world.cells, world.bacteria = [owner], {0: cargo}
        world.lab.stir(world, 65, 40)
        self.assertEqual((cargo.x, cargo.y, cargo.owner), (65, 40, 0))
        self.assertEqual(owner.elapsed, 8)

    def test_stir_cannot_push_bacteria_inside_a_membrane(self):
        world = self.world()
        cell = Cell(0, 60, 40, 12, 0, 0, cooldown=999)
        host = Bacterium(0, 80, 40, 0, 0, "rod", 999, 999)
        world.cells, world.bacteria = [cell], {0: host}
        world.lab.stir(world, 84, 40)
        for _ in range(round(3 / STEP)):
            dx, dy = host.x - cell.x, host.y - cell.y
            self.assertGreaterEqual(
                math.hypot(dx, dy), cell.outline(math.atan2(dy, dx), world.time)
            )
            world.update(events=False)

    def test_active_tools_survive_resize_and_render_without_mutation(self):
        world = self.world()
        del world.current
        cell = Cell(0, 60, 40, 12, 0, 0)
        world.cells = [cell]
        world.lab.lyse(world, Target("cell", cell), 65, 40)
        world.lab.stir(world, 80, 40)
        advance(world, 0.5)
        world.resize(50, 16)
        before = pickle.dumps(world)
        for unicode in (False, True):
            frame = render(world, unicode)
            if not unicode:
                self.assertTrue(frame.plain().isascii())
        self.assertEqual(before, pickle.dumps(world))
        advance(world, 8)
        self.assertFalse(world.lab.ruptures)
        self.assertFalse(world.lab.stirs)

    def test_lysing_a_net_source_finishes_the_event_cleanly(self):
        world = self.world()
        cell = Cell(0, 60, 40, 12, 0, 0, kind="neutrophil")
        world.cells = [cell]
        world.events.enabled = True
        world.events.active = Sighting("net", 60, 40, source=0, age=2)
        world.lab.lyse(world, Target("cell", cell), 60, 40)
        advance(world, 1.3)
        self.assertIsNone(world.events.active)
        self.assertGreater(world.events.next_at, world.events.clock)

    def test_disappearing_selection_and_noncell_targets_are_safe(self):
        world = self.world()
        host = Bacterium(0, 50, 40, 0, 0, "rod", 999, 999)
        world.bacteria = {0: host}
        control = Interaction(50, 20)
        control.click(world, 50, 20, 0)
        world.bacteria.clear()
        control.follow(world)
        self.assertIsNone(control.selected)
        self.assertIn("No cell", world.lab.lyse(world, Target("microbe", host), 50, 40))
        world.events.active = Sighting("rotifer", 50, 40)
        self.assertIn(
            "Choose", world.lab.lyse(world, Target("rotifer", world.events.active), 50, 40)
        )

    def test_interactive_mode_is_opt_in_and_incompatible_with_screensaver(self):
        self.assertFalse(parser().parse_args([]).interactive)
        self.assertTrue(parser().parse_args(["--interactive"]).interactive)
        with patch("sys.stderr"):
            with self.assertRaises(SystemExit):
                parser().parse_args(["--interactive", "--screensaver"])
