"""Read-only footprint estimates and local spacing for a legible community.

These are soft visual clearances, not new impermeable bacterial membranes.
Capture, infection, and the world's existing obstacle rules remain authoritative.
"""

import math

from .catalog import MICROBES
from .models import bacterial_scale, microbe_axes


def area(kind, units=3, bud=0, scale=1):
    a, b = MICROBES[kind].body_axes(units, bud)
    # A little breathing room, plus a modest allowance for a flexible tail.
    return (math.pi * (a + 1) * (b + 1) + (8 if MICROBES[kind].flagellum else 0)) * scale**2


def occupied(world):
    return sum(
        area(b.kind, b.units, b.bud, bacterial_scale(b))
        for b in world.bacteria.values()
        if not b.leaving
    )


def budget(world):
    # Density still lets a user deliberately choose a busy slide.
    return world.width * world.height * min(0.5, 0.16 * world.density)


def has_room(world, microbe):
    return occupied(world) + area(microbe.kind, microbe.units) <= budget(world)


def support(obj, angle):
    a, b = microbe_axes(obj)
    relative = angle - obj.angle
    return math.hypot(a * math.cos(relative), b * math.sin(relative)) * bacterial_scale(obj)


def gap(left, right, x=None, y=None):
    dx, dy = (left.x if x is None else x) - right.x, (left.y if y is None else y) - right.y
    angle = math.atan2(dy, dx)
    return math.hypot(dx, dy) - support(left, angle) - support(right, angle)


def tail_fraction(world, obj):
    """Shorten only a tail whose path runs into a nearby free microbial body."""
    length = 6 * bacterial_scale(obj)
    a = microbe_axes(obj)[0] * bacterial_scale(obj)
    ca, sa = math.cos(obj.angle), math.sin(obj.angle)
    for other in world.bacteria.values():
        if other is obj or other.owner is not None:
            continue
        dx, dy = other.x - obj.x, other.y - obj.y
        reach = (max(microbe_axes(obj)) + 6) * bacterial_scale(obj) + max(
            microbe_axes(other)
        ) * bacterial_scale(other)
        if abs(dx) > reach or abs(dy) > reach:
            continue
        along, across = dx * ca + dy * sa, -dx * sa + dy * ca
        if along < -a and abs(across) < support(other, obj.angle + math.pi / 2) + 1:
            length = min(length, max(0, -along - a - support(other, obj.angle) - 1))
    return length / (6 * bacterial_scale(obj))


def place(world, microbe):
    """Choose a clear initial position with a bounded seeded search."""
    best = None
    for index in range(24):
        x, y = (
            (microbe.x, microbe.y)
            if index == 0
            else (world.rng.uniform(0, world.width), world.rng.uniform(0, world.height))
        )
        if world.is_blocked(x, y, max(microbe_axes(microbe)) + 1):
            continue
        clearance = min(
            (
                gap(microbe, other, x, y)
                for other in world.bacteria.values()
                if other is not microbe and other.owner is None
            ),
            default=math.inf,
        )
        if best is None or clearance > best[0]:
            best = clearance, x, y
        if clearance >= 3:
            break
    if best is not None:
        _, microbe.x, microbe.y = best


class Neighbors:
    """Per-update spatial bins; no world or object references are retained globally."""

    def __init__(self, world):
        self.bins = {}
        self.radius = max(
            (max(microbe_axes(obj)) * bacterial_scale(obj) for obj in world.bacteria.values()),
            default=0,
        )
        for obj in world.bacteria.values():
            if obj.owner is None and obj.entry is None:
                key = math.floor(obj.x / 24), math.floor(obj.y / 24)
                self.bins.setdefault(key, []).append(obj)

    def drift(self, obj):
        if obj.owner is not None or obj.infection is not None or obj.rail is not None:
            return 0, 0
        bx, by = math.floor(obj.x / 24), math.floor(obj.y / 24)
        vx = vy = 0.0
        reach = max(microbe_axes(obj)) * bacterial_scale(obj) + self.radius + 2
        bins = max(1, math.ceil(reach / 24))
        for x in range(bx - bins, bx + bins + 1):
            for y in range(by - bins, by + bins + 1):
                for other in self.bins.get((x, y), ()):
                    if other is obj:
                        continue
                    dx, dy = obj.x - other.x, obj.y - other.y
                    distance = math.hypot(dx, dy)
                    if distance > reach:
                        continue
                    clearance = gap(obj, other)
                    if clearance >= 2:
                        continue
                    # Stable opposing directions resolve coincident centers.
                    angle = (
                        math.atan2(dy, dx)
                        if distance > 1e-6
                        else (0 if obj.id > other.id else math.pi)
                    )
                    force = min(1, (2 - clearance) * 0.16)
                    vx += math.cos(angle) * force
                    vy += math.sin(angle) * force
        speed = max(1, math.hypot(vx, vy))
        return vx / speed, vy / speed
