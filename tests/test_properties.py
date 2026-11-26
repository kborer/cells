"""Optional generated lifecycle/resize sequences; install requirements-dev.txt."""

import pickle
import math
import os
import unittest

from terminal_cells import World, render
from terminal_cells.lab import hit_test

try:
    from hypothesis import settings, strategies as st
    from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule
except ImportError:

    class MissingHypothesis(unittest.TestCase):
        @unittest.skip("Install requirements-dev.txt to run generated state tests")
        def test_generated_sequences(self):
            pass
else:

    class SlideMachine(RuleBasedStateMachine):
        @initialize(
            seed=st.integers(0, 2**32 - 1),
            scene=st.sampled_from(["mixed", "blood", "microbial", "vessel"]),
        )
        def create(self, seed, scene):
            self.world = World(80, 24, seed, scene=scene)
            self.twin = World(80, 24, seed, scene=scene)

        @rule(steps=st.integers(1, 90))
        def advance(self, steps):
            for _ in range(steps):
                self.world.update()
                self.twin.update()

        @rule(columns=st.integers(1, 160), rows=st.integers(1, 50))
        def resize(self, columns, rows):
            self.world.resize(columns, rows)
            self.twin.resize(columns, rows)

        @rule(
            col=st.integers(0, 159),
            row=st.integers(0, 49),
            tool=st.sampled_from(["lyse", "feed", "stir"]),
        )
        def intervene(self, col, row, tool):
            for world in (self.world, self.twin):
                x, y = min(col, world.width - 1), min(row, world.height / 2 - 1)
                if tool == "lyse":
                    world.lab.lyse(world, hit_test(world, round(x), round(y)), x, y * 2)
                elif tool == "feed":
                    world.lab.feed(world, x, y * 2)
                else:
                    world.lab.stir(world, x, y * 2)

        @invariant()
        def finite_bounded_and_reproducible(self):
            world = self.world
            assert world.rng.getstate() == self.twin.rng.getstate()
            assert world.bacteria == self.twin.bacteria
            assert world.cells == self.twin.cells
            assert world.vessel == self.twin.vessel
            for name in ("phages", "red_cells", "debris", "hyphae", "nutrients", "spent_capsids"):
                assert getattr(world, name) == getattr(self.twin, name)
            from tools.endurance import check_world

            check_world(world)
            assert len(world.bacteria) <= 90
            assert len(world.cells) <= 8
            for entity in [
                *world.cells,
                *world.bacteria.values(),
                *world.phages.values(),
                *world.red_cells,
            ]:
                assert math.isfinite(entity.x) and math.isfinite(entity.y)
            before = pickle.dumps(world)
            render(world, True)
            assert pickle.dumps(world) == before

    TestSlideSequences = SlideMachine.TestCase
    TestSlideSequences.settings = settings(
        max_examples=100 if os.environ.get("CELLS_EXTENDED_TESTS") else 15,
        stateful_step_count=40 if os.environ.get("CELLS_EXTENDED_TESTS") else 12,
        deadline=None,
    )
