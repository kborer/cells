"""Rare sightings: pacing, lifecycle effects, ownership, and palette identities."""

import math
import pickle
import unittest

from terminal_cells import World, Cell, Bacterium, Frame, Ink, PALETTES, render, State
from terminal_cells.cli import advance_frame, parser
from terminal_cells.events import Sighting, web_segments
from terminal_cells.models import STEP
from terminal_cells.render import BACTERIA_INKS, HELP_INKS, LEGEND, overlay


class RareEventTests(unittest.TestCase):
    def world(self, **kwargs):
        world = World(120, 40, 42, **kwargs)
        world.cells.clear()
        world.red_cells.clear()
        world.bacteria.clear()
        world.phages.clear()
        world.debris.clear()
        world.hyphae.clear()
        world.nutrients.clear()
        world.replenish_at = world.large_arrival_at = world.fungal_arrival_at = math.inf
        world.nutrient_at = world.phage_replenish_at = math.inf
        world.current = lambda x, y: (0, 0)
        return world

    def add_microbes(self, world, count=10):
        world.bacteria = {
            i: Bacterium(i, 60 + i * 0.4, 40, 0, 0, "rod", 99999, 99999) for i in range(count)
        }

    def net_world(self):
        world = self.world()
        world.cells = [Cell(0, 60, 40, 14, 0, 0, kind="neutrophil")]
        self.add_microbes(world)
        self.assertTrue(world.events.start(world, "net"))
        return world

    def test_seeded_wait_and_single_event_then_cooldown(self):
        first, second = self.world(), self.world()
        self.assertTrue(180 <= first.events.next_at <= 360)
        self.assertEqual(first.events.next_at, second.events.next_at)
        first.advance_events(first.events.next_at - 0.1)
        self.assertIsNone(first.events.active)
        first.advance_events(0.2)
        event = first.events.active
        self.assertIsNotNone(event)
        self.assertFalse(first.events.start(first, "pipette"))
        first.advance_events(110)
        self.assertIsNone(first.events.active)
        self.assertEqual(first.events.last_kind, event.kind)
        self.assertGreaterEqual(first.events.cooldowns[event.kind], first.events.clock + 790)
        self.assertTrue(
            180 <= first.events.next_at - (first.events.cooldowns[event.kind] - 900) <= 360
        )

    def test_wall_time_is_independent_of_fast_simulation(self):
        world = self.world()
        for _ in range(10):
            advance_frame(world, STEP * 6, events=False)
            world.advance_events(0.1)
        self.assertAlmostEqual(world.time, 2)
        self.assertAlmostEqual(world.events.clock, 1)

    def test_scene_calm_size_and_off_restrictions(self):
        blood = self.world(scene="blood")
        self.assertFalse(blood.events.start(blood, "rotifer"))
        calm = self.world(microscope_events=False)
        self.assertFalse(calm.events.start(calm, "pipette"))
        self.assertTrue(calm.events.start(calm, "rotifer"))
        off = self.world(rare_events=False)
        off.advance_events(1000)
        self.assertIsNone(off.events.active)
        self.assertFalse(off.events.start(off, "pipette"))
        small = World(40, 12, 42)
        self.assertFalse(small.events.start(small, "rotifer"))
        self.assertFalse(small.events.start(small, "pipette"))
        self.assertTrue(parser().parse_args(["--no-events"]).no_events)

    def test_visitor_enters_and_leaves_gradually(self):
        world = self.world()
        self.assertTrue(world.events.start(world, "rotifer"))
        event = world.events.active
        self.assertFalse(render(world, True).plain().strip())
        seen = False
        while world.events.active:
            before = event.x, event.y
            world.advance_events(0.1)
            self.assertLessEqual(math.dist(before, (event.x, event.y)), 0.201)
            if 20 < event.age < 48:
                seen |= bool(render(world, True).plain().strip())
        self.assertTrue(seen)
        self.assertTrue(event.x < -14 or event.x > world.width + 14)

    def test_rotifer_uses_staged_meals_preserves_species_and_limits_feeding(self):
        world = self.world()
        self.add_microbes(world)
        event = Sighting("rotifer", 40, 40, age=25, phase="feeding", traveled=36)
        world.events.active = event
        for i in range(10):
            world.bacteria[i].x, world.bacteria[i].y = event.mouth
        for _ in range(200):
            world.advance_events(0.1)
        self.assertEqual(event.eaten, 3)
        self.assertEqual(len(world.bacteria), 7)
        self.assertTrue(all(meal.kind == "rod" for meal in event.meals))
        frame = render(world)
        self.assertTrue(any(p.ink is Ink.ROTIFER for row in frame.pixels for p in row))

    def test_rotifer_respects_claimed_infected_and_population_floor(self):
        world = self.world()
        self.add_microbes(world, 4)
        event = Sighting("rotifer", 40, 40, age=25, phase="feeding", traveled=36)
        world.events.active = event
        for b in world.bacteria.values():
            b.x, b.y = event.mouth
        world.bacteria[0].owner = 99
        world.advance_events(1)
        self.assertEqual(len(world.bacteria), 4)
        self.assertFalse(event.meals)

    def test_rotifer_body_is_a_real_obstacle(self):
        world = self.world()
        world.events.active = Sighting("rotifer", 40, 40, age=25, phase="feeding", traveled=36)
        bacterium = Bacterium(0, 40, 40, 0, 0, "rod", 9999, 9999)
        world.bacteria = {0: bacterium}
        world._resolve_obstacles()
        self.assertGreater(math.dist((bacterium.x, bacterium.y), (40, 40)), 10)

    def test_net_starts_only_with_suitable_neutrophil(self):
        world = self.world()
        self.add_microbes(world)
        world.cells = [Cell(0, 60, 40, 14, 0, 0)]
        self.assertFalse(world.events.start(world, "net"))
        world.cells[0].kind = "neutrophil"
        world.cells[0].state = State.ENCLOSE
        self.assertFalse(world.events.start(world, "net"))
        world.cells[0].state = State.WANDER
        self.assertTrue(world.events.start(world, "net"))

    def test_neutrophil_can_trade_pursuit_for_a_trap_without_orphaning_a_claim(self):
        world = self.world()
        self.add_microbes(world)
        cell = Cell(0, 60, 40, 14, 0, 0, kind="neutrophil", state=State.APPROACH, target=0)
        world.cells = [cell]
        world.bacteria[0].owner = cell.id
        self.assertTrue(world.events.start(world, "net"))
        self.assertIsNone(world.bacteria[0].owner)
        self.assertIsNone(cell.target)
        self.assertTrue(world.events.freezes(cell))

    def test_net_unfolds_removes_source_and_holds_at_most_three(self):
        world = self.net_world()
        source = world.cells[0]
        world._update_cell(source, 2)
        self.assertEqual((source.x, source.y), (60, 40))
        world.advance_events(18)
        event = world.events.active
        self.assertFalse(world.cells)
        self.assertTrue(0 < len(event.held) <= 3)
        held = [world.bacteria[i] for i in event.held]
        for b in held:
            b.speed = 2
        positions = [(b.x, b.y) for b in held]
        world.update(events=False)
        self.assertEqual(positions, [(b.x, b.y) for b in held])
        world.advance_events(18)
        self.assertGreaterEqual(len(world.bacteria), 7)
        world.advance_events(25)
        self.assertIsNone(world.events.active)
        self.assertLess(world.large_arrival_at, math.inf)

    def test_claiming_a_trapped_microbe_releases_it_from_web(self):
        world = self.net_world()
        world.advance_events(18)
        event = world.events.active
        bacterium = world.bacteria[next(iter(event.held))]
        bacterium.owner = 15
        world.advance_events(0.1)
        self.assertNotIn(bacterium.id, event.held)
        self.assertFalse(world.events.trapped(bacterium))

    def test_pipette_deposits_once_and_disappears_after_withdrawal(self):
        world = self.world()
        self.assertTrue(world.events.start(world, "pipette"))
        event = world.events.active
        self.assertFalse(render(world).plain().strip())
        world.advance_events(12)
        self.assertTrue(event.deposited)
        self.assertEqual(len(world.nutrients), 1)
        world.advance_events(7)
        self.assertEqual(len(world.nutrients), 1)
        world.advance_events(14)
        self.assertIsNone(world.events.active)

    def test_pipette_does_not_deposit_inside_a_cell(self):
        world = self.world()
        event = Sighting("pipette", -18, 40, age=8)
        world.events.active = event
        world.cells = [Cell(0, 21, 40, 12, 0, 0)]
        world.advance_events(3)
        self.assertFalse(world.nutrients)
        self.assertFalse(event.deposited)

    def test_all_sightings_render_without_mutation_and_survive_resize(self):
        for kind in ("rotifer", "net", "pipette"):
            world = self.world()
            del world.current  # Pickle the normal class method.
            event = Sighting(kind, 30, 40, age=20, phase="feeding", traveled=36)
            world.events.active = event
            before = pickle.dumps(world)
            for unicode in (False, True):
                frame = render(world, unicode)
                self.assertEqual((frame.width, frame.height), (120, 40))
                if not unicode:
                    self.assertTrue(frame.plain().isascii())
            self.assertEqual(pickle.dumps(world), before)
            world.resize(40, 12)
            self.assertAlmostEqual(event.x, 10)
            self.assertAlmostEqual(event.y, 12)
            world.advance_events(110)
            self.assertIsNone(world.events.active)

    def test_web_contact_uses_drawn_segments(self):
        event = Sighting("net", 50, 40, age=18)
        self.assertEqual(len(list(web_segments(event))), 15)


class PaletteTests(unittest.TestCase):
    def test_entity_colors_are_distinct_and_microbe_rgb_separation_is_useful(self):
        entities = list(BACTERIA_INKS.values()) + [
            Ink.RED,
            Ink.MEMBRANE,
            Ink.NEUTROPHIL,
            Ink.PHAGE,
            Ink.FUNGUS,
            Ink.NUTRIENT,
            Ink.ROTIFER,
            Ink.NET,
            Ink.GLASS,
            Ink.ENDOTHELIUM,
            Ink.PLATELET,
            Ink.FIBROBLAST,
        ]

        def rgb(code):
            if code >= 232:
                return (8 + (code - 232) * 10,) * 3
            levels = (0, 95, 135, 175, 215, 255)
            code -= 16
            return levels[code // 36], levels[code // 6 % 6], levels[code % 6]

        for theme, palette in PALETTES.items():
            self.assertEqual(len(palette), len(Ink))
            self.assertTrue(
                all(0 <= extended < 256 and 0 <= basic < 8 for extended, basic in palette)
            )
            if theme == "mono":
                continue
            colors = [palette[ink.value - 1][0] for ink in entities]
            self.assertEqual(len(colors), len(set(colors)), theme)
            microbes = [rgb(palette[ink.value - 1][0]) for ink in BACTERIA_INKS.values()]
            for i, color in enumerate(microbes):
                for other in microbes[i + 1 :]:
                    self.assertGreaterEqual(math.dist(color, other), 50, theme)

    def test_legend_is_actually_colored(self):
        lines = [label for label, _ in LEGEND]
        frame = Frame(100, len(lines) + 2)
        overlay(frame, lines, [HELP_INKS[label] for label in lines])
        for label, ink in LEGEND:
            self.assertTrue(
                any(
                    "".join(p.char for p in row).strip().startswith(label)
                    and any(p.ink is ink and p.char != " " for p in row)
                    for row in frame.pixels
                )
            )
