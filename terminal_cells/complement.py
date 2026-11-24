"""A bounded, stylized dissolved complement system, independent of presentation.

This illustrates coating, recognition, and selective membrane attack. It does
not model the biochemical cascade or infer susceptibility from bacterial shape.
"""

from dataclasses import dataclass

from .catalog import MICROBES
from .models import ComplementBinding, State


@dataclass
class Complement:
    enabled: bool = True
    next_at: float = 35.0
    bindings: int = 0
    lysed: int = 0

    def bind(self, world, microbe):
        if (
            not self.enabled
            or not MICROBES[microbe.kind].bacterial
            or microbe.owner is not None
            or microbe.entry is not None
            or microbe.infection is not None
            or microbe.leaving
            or microbe.complement is not None
            or sum(b.complement is not None for b in world.bacteria.values()) >= 8
        ):
            return False
        microbe.complement = ComplementBinding()
        self.bindings += 1
        return True

    def update(self, world, dt):
        if not self.enabled:
            return
        for microbe in list(world.bacteria.values()):
            binding = microbe.complement
            if binding is None:
                continue
            if microbe.infection is not None:
                microbe.complement = None
                continue
            owner = next((c for c in world.cells if c.id == microbe.owner), None)
            if owner is not None and owner.state is State.ENCLOSE:
                continue  # A sealed/capturing owner's lifecycle is authoritative.
            binding.age += dt
            if microbe.complement_sensitive and binding.age >= 18:
                world._lyse(microbe, progeny=0, cause="complement")
            elif binding.age >= 32:
                microbe.complement = None
        if world.time < self.next_at:
            return
        self.next_at = world.time + world.rng.uniform(45, 85)
        candidates = [
            b
            for b in world.bacteria.values()
            if (
                MICROBES[b.kind].bacterial
                and b.owner is None
                and b.entry is None
                and b.infection is None
                and not b.leaving
                and b.complement is None
            )
        ]
        if candidates:
            self.bind(world, world.rng.choice(candidates))


def recognition(microbe):
    return microbe.complement.level if microbe.complement is not None else 0
