#!/usr/bin/env python3
"""Accelerated seeded endurance checks with bounded-state and allocation evidence."""

from __future__ import annotations

import argparse
import gc
import json
import math
from pathlib import Path
import random
import statistics
import sys
import time
import tracemalloc

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from terminal_cells import World  # noqa: E402
from terminal_cells import crowding  # noqa: E402
from terminal_cells.capabilities import RenderCapabilities  # noqa: E402
from terminal_cells.styles import STYLES, RenderOptions  # noqa: E402
from terminal_cells.viewport import Camera, MAGNIFICATIONS  # noqa: E402


def check_world(world):
    assert len(world.cells) <= 8
    assert len(world.bacteria) <= world._limits()[1] * 2
    assert len(world.phages) <= world._phage_limit()
    assert len(world.nutrients) <= 4
    assert len(world.hyphae) <= world._hypha_limit()
    for hypha in world.hyphae:
        assert len(hypha.nodes) <= 48
    for entity in [
        *world.cells,
        *world.bacteria.values(),
        *world.phages.values(),
        *world.red_cells,
        *world.debris,
        *world.spent_capsids,
    ]:
        assert math.isfinite(entity.x) and math.isfinite(entity.y)
    if world.vessel is not None:
        vessel = world.vessel
        assert len(vessel.platelets) <= vessel.platelet_limit
        assert len(vessel.fibroblasts) <= 2
        assert len(vessel.fibers) <= 16
        assert vessel.wound is None or 0 <= vessel.wound.repair < 1
        assert vessel.transit is None or any(c.id == vessel.transit.cell_id for c in world.cells)
        for obj in vessel.platelets + vessel.fibroblasts:
            assert math.isfinite(obj.x) and math.isfinite(obj.y)
    for cell in world.cells:
        if cell.target is not None:
            assert cell.target in world.bacteria


class Progress:
    """Bounded progress observations; no references to entities are retained."""

    def __init__(self, world):
        self.last_immune = dict.fromkeys(("macrophage", "neutrophil"), world.time)
        self.buds = {}
        self.oldest_entry = 0.0
        self.longest_immune_absence = 0.0
        self.free_samples = []

    def observe(self, world):
        for obj in [
            *world.cells,
            *world.bacteria.values(),
            *world.phages.values(),
            *world.red_cells,
        ]:
            if obj.entry is not None:
                self.oldest_entry = max(self.oldest_entry, obj.entry.age)
                assert obj.entry.age < 180, (
                    f"Stalled edge crossing: {type(obj).__name__} {obj.entry}"
                )
        self.free_samples.append(
            sum(b.entry is None and b.owner is None for b in world.bacteria.values())
        )
        if world._limits()[0] >= 2:
            present = {c.kind for c in world.cells if c.entry is None}
            for kind, last in self.last_immune.items():
                if kind in present:
                    self.last_immune[kind] = world.time
                else:
                    absent = world.time - last
                    self.longest_immune_absence = max(self.longest_immune_absence, absent)
                    assert absent < 600, (
                        f"Immune diversity did not recover: {kind} absent {absent:.1f}s"
                    )
        pending = {}
        capacity = world._limits()[1]
        limit = capacity * 2 - min(2, max(1, capacity // 4))
        for obj in world.bacteria.values():
            if (
                obj.bud
                and obj.owner is None
                and obj.entry is None
                and obj.infection is None
                and not obj.leaving
                and len(world.bacteria) < limit
                and crowding.has_room(world, obj, reproduction=True)
            ):
                value, since = self.buds.get(obj.id, (obj.bud, world.time))
                if value != obj.bud:
                    since = world.time
                assert world.time - since < 30, f"Eligible bud stopped growing: {obj.id}"
                pending[obj.id] = obj.bud, since
        self.buds = pending


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--steps", type=int, default=108000)
    cli.add_argument("--seed", type=int, default=42)
    cli.add_argument("--scene", choices=["mixed", "blood", "microbial", "vessel"], default="mixed")
    cli.add_argument("--size", choices=["80x24", "120x40", "200x60"], default="120x40")
    cli.add_argument("--fixed-size", action="store_true", help="do not unblock routes by resizing")
    cli.add_argument("--magnification", choices=tuple(MAGNIFICATIONS), default="normal")
    cli.add_argument("--style", choices=tuple(STYLES), default="classic")
    cli.add_argument("--output", type=Path, default=Path("endurance.json"))
    args = cli.parse_args()
    if args.steps < 1800:
        cli.error("--steps must be at least 1800 (one simulated minute)")
    columns, rows = map(int, args.size.split("x"))
    camera = Camera(columns, rows, args.magnification)
    world = World(*camera.simulation_size(), args.seed, scene=args.scene)
    camera.focus(world)
    style = STYLES[args.style]
    options = RenderOptions.resolve(
        RenderCapabilities(
            unicode=True, colors=256, backgrounds=True, blocks=True, color_pairs=256
        ),
        fill=style.default_fill,
    )
    rng = random.Random(args.seed)
    for _ in range(900):
        world.update()
    gc.collect()
    tracemalloc.start(1)
    baseline = tracemalloc.get_traced_memory()[0]
    latencies, counts = [], []
    progress = Progress(world)
    for step in range(args.steps):
        start = time.perf_counter()
        world.update()
        if step % 60 == 0:
            latencies.append(time.perf_counter() - start)
        if step % 300 == 0:
            check_world(world)
            camera.render(style, world, options)
            progress.observe(world)
            counts.append(len(world.bacteria))
        if not args.fixed_size and step % 1800 == 0:
            camera.columns, camera.rows = rng.choice([(80, 24), (120, 40), (200, 60)])
            world.resize(*camera.simulation_size())
            camera.x = camera.y = None
        if step % 900 == 0:
            world.lab.stir(
                world,
                rng.randrange(max(1, int(world.width))),
                rng.randrange(max(1, int(world.height / 2))),
            )
    gc.collect()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    first = statistics.median(latencies[: max(1, len(latencies) // 5)])
    last = statistics.median(latencies[-max(1, len(latencies) // 5) :])
    report = dict(
        seed=args.seed,
        scene=args.scene,
        style=args.style,
        magnification=args.magnification,
        size=args.size,
        fixed_size=args.fixed_size,
        steps=args.steps,
        allocation_growth=current - baseline,
        peak_bytes=peak,
        update_first_median_ms=first * 1000,
        update_last_median_ms=last * 1000,
        microbe_samples=counts,
        free_microbe_samples=progress.free_samples,
        oldest_entry_seconds=progress.oldest_entry,
        longest_immune_absence_seconds=progress.longest_immune_absence,
        completed_entries=world.entry_completions,
        entry_retries=world.entry_retries,
    )
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if not k.endswith("samples")}, indent=2))
    assert peak < 128 * 1024 * 1024, "Excessive tracked allocation"
    assert current - baseline < 32 * 1024 * 1024, "Possible memory retention"
    assert last < max(0.1, first * 20), "Severe update-latency regression"
    assert any(counts[len(counts) // 2 :]), "Microbial population stayed extinct"
    assert any(progress.free_samples[len(progress.free_samples) // 2 :]), "No active free microbes"
    if args.steps >= 27000:
        assert world.entry_completions > 0, "No edge arrivals completed"


if __name__ == "__main__":
    main()
