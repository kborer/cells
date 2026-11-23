"""Deterministic specimen fixtures for comparing presentations.

These deliberately stage encounters; they are developer demonstrations, not new
population presets for ordinary runs. Time advances through the real simulator.
"""

import math
from dataclasses import dataclass
from types import MappingProxyType

from .models import (
    CELL_RADIUS,
    NEUTROPHIL_RADIUS,
    Drifter,
    BACTERIUM_PADDING,
    STEP,
    Cell,
    Bacterium,
    Infection,
    State,
)
from .world import World


@dataclass(frozen=True)
class SceneSpec:
    description: str
    times: tuple[float, ...]


SCENES = MappingProxyType(
    {
        "blood-smear": SceneSpec(
            "Reference-like blood smear with a neutrophil and red cells", (0, 12)
        ),
        "division": SceneSpec(
            "Nuclear organization through daughter separation", (0, 9, 22, 30, 37, 46, 51)
        ),
        "ingestion": SceneSpec(
            "Contact, enclosure, sealing, and inward transport", (0, 3, 6.9, 9, 12)
        ),
        "infection": SceneSpec(
            "Phage attachment, replication, assembly, and lysis", (0, 5, 10, 18, 22.5, 24.3)
        ),
        "overlap": SceneSpec("Captured cargo beneath its owner's nucleus", (0,)),
        "crowding": SceneSpec("A dense seeded community", (0, 12)),
    }
)


def make_scene(name: str, *, seed: int = 42, at: float = 0) -> World:
    """Return an independent 100x40 specimen, advanced to simulated seconds.

    A fresh world is built for every call, so styles compare exactly the same
    state. This is a fixture API; staged initial layouts may evolve with artwork.
    """
    if name not in SCENES:
        raise ValueError(f"Unknown comparison scene: {name}")
    if not math.isfinite(at) or not 0 <= at <= 60:
        raise ValueError("Scene time must be finite and between 0 and 60 seconds")
    world = World(
        100,
        40,
        seed,
        density=3 if name in ("crowding", "blood-smear") else 1,
        scene="blood" if name == "blood-smear" else "mixed",
        rare_events=False,
        microscope_events=False,
    )
    if name == "blood-smear":
        world.cells = [
            Cell(0, 50, 40, NEUTROPHIL_RADIUS, 0, 0, kind="neutrophil", divide_at=math.inf)
        ]
        world.bacteria.clear()
        world.hyphae.clear()
        world.phages.clear()
        world.nutrients.clear()
        points = (
            (12, 10),
            (36, 7),
            (65, 10),
            (89, 8),
            (3, 35),
            (22, 27),
            (78, 30),
            (96, 42),
            (12, 61),
            (31, 70),
            (65, 71),
            (85, 62),
            (47, -1),
            (98, 73),
        )
        world.red_cells = [
            Drifter(x, y, i * 0.6, 5 + (i % 3) * 0.3) for i, (x, y) in enumerate(points)
        ]
        world.replenish_at = world.phage_replenish_at = math.inf
        world.nutrient_at = world.fungal_arrival_at = world.large_arrival_at = math.inf
    if name not in ("crowding", "blood-smear"):
        for pool in (
            world.cells,
            world.bacteria,
            world.phages,
            world.red_cells,
            world.debris,
            world.hyphae,
            world.nutrients,
            world.spent_capsids,
            world.bursts,
        ):
            pool.clear()
        world.replenish_at = world.phage_replenish_at = math.inf
        world.nutrient_at = world.fungal_arrival_at = world.large_arrival_at = math.inf
        if name == "division":
            world.cells = [
                Cell(0, 50, 40, CELL_RADIUS, 0, 0, state=State.DIVIDE, divide_at=math.inf)
            ]
            world.next_cell_id = 1
        elif name == "ingestion":
            world.cells = [Cell(0, 42, 40, CELL_RADIUS, 0, 0, divide_at=math.inf)]
            world.bacteria = {
                0: Bacterium(
                    0, 42 + CELL_RADIUS + BACTERIUM_PADDING, 40, 0, 0, "coccus", math.inf, math.inf
                )
            }
            world.next_id, world.next_cell_id = 1, 1
        elif name == "infection":
            world.bacteria = {
                0: Bacterium(0, 50, 40, 0, 0, "rod", math.inf, math.inf, infection=Infection())
            }
            world.infections, world.next_id = 1, 1
        elif name == "overlap":
            world.cells = [
                Cell(
                    0,
                    50,
                    40,
                    12,
                    0,
                    0,
                    state=State.ENCLOSE,
                    elapsed=9,
                    target=0,
                    divide_at=math.inf,
                )
            ]
            world.bacteria = {0: Bacterium(0, 47, 40, 0, 0, "rod", math.inf, math.inf, owner=0)}
            world.next_id, world.next_cell_id = 1, 1
    for _ in range(round(at / STEP)):
        world.update()
    return world
