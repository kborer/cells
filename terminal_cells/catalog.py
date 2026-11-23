"""Immutable microbial identity and shared behavior defaults.

Artwork, palettes, and animation remain in presentation styles. Insertion order
is intentional: preserving it keeps seeded population selection reproducible.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class MicrobeSpec:
    label: str
    axes: tuple[float, float]
    blood_weight: float = 1
    speed: float = 1
    bacterial: bool = True
    phage_host: bool = True
    flagellum: bool = False
    evasive: bool = False
    fungal_rails: bool = False
    reproduction: str = "fission"
    bud_seconds: float = 0
    split_axis: int = 1
    unit_growth: tuple[float, float] = (0, 0)
    bud_growth: tuple[float, float] = (0, 0)
    unit_origin: int = 0

    def body_axes(self, units: int = 3, bud: float = 0) -> tuple[float, float]:
        return tuple(
            a + u * (units - self.unit_origin) + b * bud
            for a, u, b in zip(self.axes, self.unit_growth, self.bud_growth)
        )


MICROBES: Mapping[str, MicrobeSpec] = MappingProxyType(
    {
        "rod": MicrobeSpec(
            "Rod bacterium",
            (3.2, 1.65),
            blood_weight=2,
            flagellum=True,
            evasive=True,
            fungal_rails=True,
        ),
        "coccus": MicrobeSpec("Coccus", (2.3, 2.3), blood_weight=3),
        "spiral": MicrobeSpec(
            "Short spiral", (3.2, 1.65), blood_weight=0.3, flagellum=True, evasive=True
        ),
        "bacillus": MicrobeSpec(
            "Bacillary chain",
            (2.4, 1.7),
            blood_weight=0.5,
            fungal_rails=True,
            reproduction="segmented",
            split_axis=0,
            unit_growth=(1.7, 0),
            unit_origin=1,
        ),
        "spirochete": MicrobeSpec("Spirochete", (7, 1.7), blood_weight=0.2, evasive=True),
        "vibrio": MicrobeSpec(
            "Vibrio",
            (3.3, 2.1),
            blood_weight=0.3,
            speed=1.8,
            flagellum=True,
            evasive=True,
            fungal_rails=True,
        ),
        "colony": MicrobeSpec(
            "Coccal colony",
            (3.2, 3.2),
            blood_weight=0.5,
            reproduction="segmented",
            unit_growth=(0.35, 0.35),
        ),
        "yeast": MicrobeSpec(
            "Yeast",
            (3.3, 2.7),
            speed=0,
            bacterial=False,
            phage_host=False,
            reproduction="budding",
            bud_seconds=12,
            split_axis=0,
            bud_growth=(3.5, 0),
        ),
        "trypanosome": MicrobeSpec(
            "Trypanosome",
            (7, 2.4),
            blood_weight=2,
            speed=1.5,
            bacterial=False,
            phage_host=False,
            flagellum=True,
            reproduction="budding",
            bud_seconds=10,
        ),
    }
)
MICROBE_KINDS = tuple(MICROBES)
BACTERIAL_KINDS = frozenset(key for key, spec in MICROBES.items() if spec.bacterial)

PHAGE_HOST_KINDS = frozenset(key for key, spec in MICROBES.items() if spec.phage_host)
