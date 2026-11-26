"""Canonical vessel/tissue glyphs; all coordinates come from the simulation."""

import math

from .frame import Ink


def draw_wall(frame, world, unicode=False):
    vessel = world.vessel
    if vessel is None or not vessel.room:
        return
    # Flattened neighbors share a narrow inner boundary and staggered junctions.
    for side in (-1, 1):
        for col in range(frame.width):
            x, _ = frame.grid.world(col, 0)
            wall = vessel.wall(x, side)
            wound = vessel.wound
            gap = wound is not None and wound.side == side and abs(x - wound.x) < wound.half_width
            transit = vessel.transit
            junction = (
                transit is not None
                and transit.side == side
                and transit.age >= 16
                and abs(x - transit.x) < 2
            )
            if not gap and not junction:
                frame.point(x, wall, "─" if unicode else "_", Ink.ENDOTHELIUM)
            frame.point(x, wall + side * 3, "─" if unicode else "-", Ink.ENDOTHELIUM)
        for obj in vessel.endothelium:
            if obj.side != side:
                continue
            x = obj.x - 9
            wall = vessel.wall(x, side)
            frame.line(x, wall, x + 2, wall + side * 3, Ink.ENDOTHELIUM, unicode, bg=None)
            frame.point(obj.x, obj.y, "o", Ink.ENDOTHELIUM)
    wound = vessel.wound
    if wound is not None:
        for sign in (-1, 1):
            x = wound.x + sign * max(1, wound.half_width)
            y = vessel.wall(x, wound.side)
            frame.point(x, y, "*", Ink.PLATELET, bold=True)


def draw_repair(frame, world, unicode=False):
    vessel = world.vessel
    if vessel is None or not vessel.room:
        return
    # Matrix is local, parallel and unbranched, unlike living fungal hyphae.
    for index, fiber in enumerate(vessel.fibers):
        if fiber.age < 75 or index % 4 > int((fiber.age - 75) / 7):
            frame.line(*fiber.start, *fiber.end, Ink.MATRIX, unicode)
    for obj in vessel.fibroblasts:
        stretch = math.sin(world.time * 0.6 + obj.side) * 0.8
        left, right = obj.x - 6 - stretch, obj.x + 6 + stretch
        frame.line(left, obj.y, obj.x - 2, obj.y - 2.5, Ink.FIBROBLAST, unicode)
        frame.line(obj.x - 2, obj.y - 2.5, right, obj.y, Ink.FIBROBLAST, unicode)
        frame.line(right, obj.y, obj.x + 2, obj.y + 2.5, Ink.FIBROBLAST, unicode)
        frame.line(obj.x + 2, obj.y + 2.5, left, obj.y, Ink.FIBROBLAST, unicode)
        frame.point(obj.x, obj.y, "o", Ink.FIBROBLAST, bold=True)
        lead = right if obj.heading == 0 else left
        frame.line(
            lead,
            obj.y,
            lead + (3 if obj.heading == 0 else -3),
            obj.y - 0.5,
            Ink.FIBROBLAST,
            unicode,
        )
    bound = sorted((p for p in vessel.platelets if p.phase == "adhered"), key=lambda p: p.slot)
    for obj in vessel.platelets:
        if obj.phase == "resolving" and obj.age > 8 and obj.id % 3 == 0:
            continue
        if obj.phase == "resting" or obj.spread < 0.2:
            frame.point(obj.x, obj.y, "o", Ink.PLATELET)
            continue
        radius = 1 + obj.spread * (0.35 if obj.phase == "adhered" else 1.4)
        spokes = 3 if obj.phase == "adhered" else 5
        for index in range(spokes):
            angle = math.tau * index / spokes + obj.id
            frame.line(
                obj.x,
                obj.y,
                obj.x + math.cos(angle) * radius,
                obj.y + math.sin(angle) * radius,
                Ink.PLATELET,
                unicode,
            )
        frame.point(
            obj.x,
            obj.y,
            "*" if obj.phase != "resolving" else ".",
            Ink.PLATELET,
            bold=obj.phase == "adhered",
        )

    for index, obj in enumerate(bound):
        if obj.spread > 0.5 and index > 0:
            other = bound[index - 1]
            frame.line(other.x, other.y, obj.x, obj.y, Ink.FIBRIN, unicode)
        if obj.spread > 0.8 and index > 2:
            other = bound[index - 3]
            frame.line(other.x, other.y, obj.x, obj.y, Ink.FIBRIN, unicode)
    for obj in bound:
        frame.point(obj.x, obj.y, "*", Ink.PLATELET, bold=True)
