"""Bounded vessel and tissue repair, independent of presentation.

The opt-in scene illustrates rolling, diapedesis, a platelet plug, and slow
matrix repair. It is not a coagulation cascade or a model of vascular disease.
"""

from dataclasses import dataclass, field
import math
import random

from .models import State, clamp, smooth


@dataclass
class Endothelium:
    x: float
    y: float
    side: int


@dataclass
class Wound:
    x: float
    side: int
    age: float = 0.0
    repair: float = 0.0
    recruited: bool = False

    @property
    def half_width(self):
        return 6 * (1 - self.repair)


@dataclass
class Platelet:
    id: int
    x: float
    y: float
    phase: str = "resting"
    age: float = 0.0
    spread: float = 0.0
    slot: int = -1


@dataclass
class Fibroblast:
    x: float
    y: float
    side: int
    heading: float = 0.0
    deposit_at: float = 0.0


@dataclass
class Fiber:
    start: tuple[float, float]
    end: tuple[float, float]
    age: float = 0.0


@dataclass
class Transit:
    cell_id: int
    side: int
    x: float
    age: float = 0.0
    start_x: float = 0.0
    start_y: float = 0.0
    radius: float = 0.0

    @property
    def phase(self):
        return "rolling" if self.age < 10 else "adhering" if self.age < 16 else "crossing junction"


@dataclass
class Vessel:
    seed: int
    width: float
    height: float
    endothelium: list[Endothelium] = field(default_factory=list)
    wound: Wound | None = None
    transit: Transit | None = None
    platelets: list[Platelet] = field(default_factory=list)
    fibroblasts: list[Fibroblast] = field(default_factory=list)
    fibers: list[Fiber] = field(default_factory=list)
    next_at: float = 35.0
    next_platelet: int = 0
    injuries: int = 0
    recruited: int = 0
    crossed: int = 0
    healed: int = 0
    deposited: int = 0
    rng: random.Random = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        self.rng = random.Random(self.seed ^ 0x71A55E1)
        self._lining()
        if self.room:
            self.fibroblasts = [
                Fibroblast(self.width * 0.5, self.tissue_y(side), side) for side in (-1, 1)
            ]
            for _ in range(self.platelet_limit):
                self._add_platelet(initial=True)

    def _lining(self):
        self.endothelium = (
            [
                Endothelium(x, self.wall(x, side) + side * 1.5, side)
                for side in (-1, 1)
                for x in range(9, math.ceil(self.width), 18)
            ]
            if self.room
            else []
        )

    @property
    def room(self):
        return self.width >= 60 and self.height >= 44

    @property
    def band(self):
        return min(10, self.height * 0.14)

    @property
    def platelet_limit(self):
        return min(24, max(6, round(self.width / 12))) if self.room else 0

    def tissue_y(self, side):
        return self.band * 0.35 if side < 0 else self.height - self.band * 0.35

    def wall(self, x, side):
        depth = self.band + 0.55 * math.sin(x * 0.11) + 0.3 * math.sin(x * 0.29)
        return depth if side < 0 else self.height - depth

    def bounds(self, x, padding=0):
        return self.wall(x, -1) + padding, self.wall(x, 1) - padding

    def obstacles(self, x, y, padding=0, exempt=None):
        if not self.room or self.transit is not None and self.transit.cell_id == exempt:
            return
        low, high = self.bounds(x, padding)
        if y < low:
            yield 0.0, 1.0, low - y
        if y > high:
            yield 0.0, -1.0, y - high

    def contain(self, obj, padding):
        """Keep suspended bodies in the lumen, even at an illustrated injury."""
        if not self.room or getattr(obj, "entry", None) is not None:
            return
        low, high = self.bounds(obj.x, padding)
        obj.y = clamp(obj.y, min(low, self.height / 2), max(high, self.height / 2))

    def injure(self, x, side):
        if not self.room or self.wound is not None or self.transit is not None:
            return False
        self.wound = Wound(clamp(x, 14, self.width - 14), -1 if side < 0 else 1)
        self.injuries += 1
        return True

    @property
    def caption(self):
        if not self.room:
            return "Vessel detail needs at least 60 columns and 22 rows"
        if self.transit is not None:
            return "Vessel / neutrophil " + self.transit.phase
        if self.wound is not None:
            attached = sum(p.phase == "adhered" for p in self.platelets)
            return f"Vessel repair / plug {attached}/8 / matrix {self.wound.repair:.0%}"
        return f"Vessel / repaired patches {self.healed}"

    def _add_platelet(self, *, initial=False):
        x = self.rng.uniform(0, self.width) if initial else -3.0
        low, high = self.bounds(x, 2)
        self.platelets.append(Platelet(self.next_platelet, x, self.rng.uniform(low, high)))
        self.next_platelet += 1

    def _platelets(self, world, dt):
        wound = self.wound
        attached = sum(p.phase == "adhered" for p in self.platelets)
        occupied = {p.slot for p in self.platelets if p.phase == "adhered"}
        for obj in self.platelets:
            obj.age += dt
            if wound is None or wound.repair > 0.9 or wound.age > 110:
                if obj.phase in ("adhered", "activated"):
                    obj.phase, obj.age, obj.slot = "resolving", 0, -1
            if obj.phase == "adhered":
                obj.spread = min(1, obj.spread + dt / 5)
                obj.x = wound.x + (obj.slot % 4 - 1.5) * 3.2
                obj.y = self.wall(obj.x, wound.side) - wound.side * (1.2 + obj.slot // 4 * 3.4)
                continue
            vx, vy = world.current(obj.x, obj.y)
            fx, fy = world.lab.flow(obj.x, obj.y)
            vx, vy = vx + fx, vy + fy
            if wound is not None and wound.age < 95 and attached < 8:
                wy = self.wall(wound.x, wound.side) - wound.side * 2
                dx, dy = wound.x - obj.x, wy - obj.y
                distance = math.hypot(dx, dy)
                if distance < 28 and obj.phase == "resting":
                    obj.phase, obj.age = "activated", 0
                if obj.phase == "activated":
                    obj.spread = min(1, obj.spread + dt / 4)
                    vx, vy = dx / max(1, distance) * 2.5, dy / max(1, distance) * 2.5
                    if distance < 2:
                        obj.slot = next(i for i in range(8) if i not in occupied)
                        occupied.add(obj.slot)
                        obj.phase, obj.age = "adhered", 0
                        attached += 1
                        continue
            if obj.phase == "resolving":
                obj.spread = max(0, obj.spread - dt / 6)
            # Small steps prevent a stir from jumping through a cell membrane.
            steps = max(1, math.ceil(math.hypot(vx, vy) * dt / 0.5))
            for _ in range(steps):
                nx, ny = obj.x + vx * dt / steps, obj.y + vy * dt / steps
                if not world.is_blocked(nx, ny, 1.2):
                    obj.x, obj.y = nx, ny
                elif not world.is_blocked(nx, obj.y, 1.2):
                    obj.x = nx
            self.contain(obj, 1.2)
            world._exclude(obj, 1.2)
        self.platelets = [
            p
            for p in self.platelets
            if p.x < self.width + 4 and not (p.phase == "resolving" and p.age > 15)
        ]
        # New fragments enter from the upstream edge, never appear in the lumen.
        if len(self.platelets) < self.platelet_limit:
            self._add_platelet()

    def _fibroblasts(self, world, dt):
        for side in (-1, 1):
            if not any(obj.side == side for obj in self.fibroblasts):
                self.fibroblasts.append(Fibroblast(-12, self.tissue_y(side), side))
        for obj in self.fibroblasts:
            wound = self.wound
            active = wound is not None and wound.side == obj.side and wound.age >= 20
            target = (
                wound.x
                if active
                else self.width * (0.5 + 0.15 * math.sin(world.time * 0.02 + obj.side))
            )
            dx = target - obj.x
            obj.heading = 0 if dx >= 0 else math.pi
            obj.x += clamp(dx, -0.7 * dt, 0.7 * dt)
            obj.y = self.tissue_y(obj.side)
            if active and abs(dx) < 9 and world.time >= obj.deposit_at:
                obj.deposit_at = world.time + 4
                if len(self.fibers) < 16:
                    offset = self.rng.uniform(-4, 4)
                    y = self.wall(wound.x, wound.side) + wound.side * 2.5
                    self.fibers.append(
                        Fiber((wound.x - 7, y + offset * 0.2), (wound.x + 7, y - offset * 0.2))
                    )
                    self.deposited += 1
            if (
                active
                and wound.age >= 35
                and sum(
                    math.dist(
                        f.start, (wound.x - 7, self.wall(wound.x, wound.side) + wound.side * 2.5)
                    )
                    < 2
                    for f in self.fibers
                )
                >= 3
            ):
                wound.repair = min(1, wound.repair + dt / 65)
        for fiber in self.fibers:
            fiber.age += dt
        self.fibers = [f for f in self.fibers if f.age < 100]

    def update(self, world, dt):
        if not self.room:
            return
        if (
            self.wound is None
            and self.transit is None
            and world.events.enabled
            and world.time >= self.next_at
        ):
            self.injure(self.width * self.rng.uniform(0.35, 0.65), self.rng.choice((-1, 1)))
        wound = self.wound
        if wound is not None:
            wound.age += dt
            if self.transit is None and not wound.recruited and wound.age < 65:
                candidates = [
                    c
                    for c in world.cells
                    if c.kind == "neutrophil"
                    and c.entry is None
                    and c.state in (State.WANDER, State.DIGEST)
                    and not c.vesicles
                    and not world.events.freezes(c)
                    and abs(c.x - wound.x) < 50
                ]
                if candidates:
                    cell = min(
                        candidates,
                        key=lambda c: math.hypot(
                            c.x - wound.x, c.y - self.wall(wound.x, wound.side)
                        ),
                    )
                    world._release(cell)
                    self.transit = Transit(
                        cell.id,
                        wound.side,
                        wound.x,
                        start_x=cell.x,
                        start_y=cell.y,
                        radius=cell.radius,
                    )
                    self.recruited += 1
                    wound.recruited = True
            # A sparse or resized scene must still finish a repair cycle.
            if wound.age > 160:
                wound.repair = min(1, wound.repair + dt / 50)
        self._platelets(world, dt)
        self._fibroblasts(world, dt)
        if wound is not None and wound.repair >= 1:
            self.wound = None
            self.healed += 1
            self.next_at = world.time + self.rng.uniform(180, 300)
        if self.transit is not None and not any(c.id == self.transit.cell_id for c in world.cells):
            self.transit = None

    def update_cell(self, world, cell, dt):
        transit = self.transit
        if transit is None or transit.cell_id != cell.id:
            return False
        transit.age += dt
        if transit.age < 10:
            progress = smooth(transit.age / 10)
            x = transit.x - 10 * (1 - progress)
            wall = self.wall(x, transit.side)
            cell.x = transit.start_x * (1 - progress) + x * progress
            cell.y = (
                transit.start_y * (1 - progress)
                + (wall - transit.side * (cell.radius + 1)) * progress
            )
            cell.phase += dt * 0.5  # Visible slow roll before adhesion.
        elif transit.age < 16:
            cell.x = transit.x
            cell.y = self.wall(cell.x, transit.side) - transit.side * (cell.radius + 1)
        else:
            # Gradual squeezing through one junction, then entirely offscreen.
            progress = smooth((transit.age - 16) / 24)
            cell.radius = transit.radius * (1 - 0.35 * math.sin(progress * math.pi))
            cell.x = transit.x
            start = self.wall(cell.x, transit.side) - transit.side * (transit.radius + 1)
            end = -transit.radius * 1.8 if transit.side < 0 else self.height + transit.radius * 1.8
            cell.y = start * (1 - progress) + end * progress
            if transit.age >= 40:
                world.cells.remove(cell)
                world.large_arrival_at = min(world.large_arrival_at, world.time + 8)
                self.transit = None
                self.crossed += 1
        cell.heading = transit.side * math.pi / 2
        return True

    def resize(self, width, height):
        sx, sy = width / self.width, height / self.height
        self.width, self.height = width, height
        self._lining()
        if not self.room:
            self.wound = None
            self.fibers.clear()
            self.platelets.clear()
            self.fibroblasts.clear()
            return
        if self.wound is not None:
            self.wound.x = clamp(self.wound.x * sx, 14, width - 14)
        for obj in self.platelets:
            obj.x *= sx
            obj.y *= sy
            self.contain(obj, 1.2)
        self.platelets = self.platelets[: self.platelet_limit]
        for obj in self.fibroblasts:
            obj.x *= sx
            obj.y = self.tissue_y(obj.side)
        if not self.fibroblasts:
            self.fibroblasts = [Fibroblast(width / 2, self.tissue_y(s), s) for s in (-1, 1)]
        for fiber in self.fibers:
            fiber.start = fiber.start[0] * sx, fiber.start[1] * sy
            fiber.end = fiber.end[0] * sx, fiber.end[1] * sy
