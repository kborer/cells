"""Read-only geometry and foreground selection shared by all presentations.

Positions are simulation coordinates unless a function explicitly takes a
terminal column and row. Queries never update the world or consume its RNG.
"""

from dataclasses import dataclass
import math

from .events import segment_distance
from .frame import line_pixels
from .viewport import CURRENT, Grid, projection
from .models import (
    State,
    bacterial_scale,
    disc_axes,
    microbe_axes,
    nucleus_radii,
    smooth,
)


def cell_contains(cell, x: float, y: float, now: float, padding: float = 0) -> bool:
    dx, dy = x - cell.x, y - cell.y
    return math.hypot(dx, dy) <= cell.outline(math.atan2(dy, dx), now) + padding


def nuclear_bodies(cell):
    """Yield (x, y, radius, nucleolus) for intact nuclear bodies.

    Mitotic chromosomes/spindles are not intact bodies. Capture and division
    are exclusive, so the capture-selection tie-break only needs intact nuclei.
    """
    if cell.kind == "neutrophil":
        cx, cy = CURRENT.get().snap(cell.x, cell.y)
        for x, y in (
            (cx - cell.radius * 0.28, cy - 2),
            (cx, cy + 2),
            (cx + cell.radius * 0.28, cy - 2),
        ):
            yield x, y, cell.radius * 0.48, False
    elif cell.state is not State.DIVIDE:
        yield (
            cell.x - math.cos(cell.phase) * cell.radius * 0.22,
            cell.y - math.sin(cell.phase) * cell.radius * 0.22,
            cell.radius,
            True,
        )


def nuclear_mask(radius: float):
    """Raster offsets for an intact nucleus, anchored to one terminal cell."""
    rx, ry = nucleus_radii(radius)
    scale = CURRENT.get().scale
    rx, rows = max(2, round(rx * scale)), max(1, round(ry * scale / CURRENT.get().aspect))
    return frozenset(
        (col, row)
        for row in range(-rows, rows + 1)
        for col in range(-rx, rx + 1)
        if (col / rx) ** 2 + (row / rows) ** 2 <= 1.12
    )


def nuclear_contains(cell, col: int, row: int) -> bool:
    bodies = list(nuclear_bodies(cell))
    if any(
        (col - CURRENT.get().point(x, y)[0], row - CURRENT.get().point(x, y)[1])
        in nuclear_mask(radius)
        for x, y, radius, _ in bodies
    ):
        return True
    if cell.kind == "neutrophil":
        # The thin bridges between lobes also cover captured cargo.
        return any(
            (col, row) in line_pixels(left[0], left[1], right[0], right[1])
            for left, right in zip(bodies, bodies[1:])
        )
    return False


def obstacles(
    world,
    x: float,
    y: float,
    padding: float = 0,
    exempt: int | None = None,
    red: bool = True,
    visitors: bool = True,
):
    """Yield (normal_x, normal_y, penetration) at an obstructed specimen point.

    Positive padding expands each obstacle. Exempt names an immune-cell ID.
    This preserves the simulation's radial collision envelope.
    """
    if visitors:
        yield from world.events.obstacle(x, y, padding)
    for cell in world.cells:
        if cell.id == exempt:
            continue
        dx, dy = x - cell.x, y - cell.y
        bound = cell.extent() + padding + 2
        if abs(dx) > bound or abs(dy) > bound:
            continue
        angle = math.atan2(dy, dx)
        boundary = cell.outline(angle, world.time) + padding
        distance = math.hypot(dx, dy)
        if distance < boundary:
            yield math.cos(angle), math.sin(angle), boundary - distance
    if red:
        for disc in world.red_cells:
            dx, dy = x - disc.x, y - disc.y
            a, b = disc_axes(disc)
            if abs(dx) > a + padding or abs(dy) > b + padding:
                continue
            angle = math.atan2(dy, dx)
            boundary = a * b / math.hypot(b * math.cos(angle), a * math.sin(angle)) + padding
            distance = math.hypot(dx, dy)
            if distance < boundary:
                yield math.cos(angle), math.sin(angle), boundary - distance


@dataclass(eq=False)
class Target:
    kind: str
    obj: object
    segment: tuple[int, int] | None = None
    fraction: float = 0.5

    def alive(self, world):
        pools = {
            "cell": world.cells,
            "microbe": world.bacteria.values(),
            "red": world.red_cells,
            "phage": world.phages.values(),
            "hypha": world.hyphae,
            "food": world.nutrients,
        }
        if self.kind == "rotifer":
            return world.events.active is self.obj
        return any(obj is self.obj for obj in pools[self.kind]) and (
            self.segment is None or self.segment in self.obj.edges
        )

    @property
    def center(self):
        if self.kind == "hypha":
            a, b = (self.obj.nodes[i] for i in self.segment)
            return tuple(a[i] + (b[i] - a[i]) * self.fraction for i in (0, 1))
        return self.obj.x, self.obj.y

    @property
    def extent(self):
        if self.kind == "cell":
            return self.obj.extent()
        if self.kind == "microbe":
            return max(microbe_axes(self.obj)) * bacterial_scale(self.obj)
        if self.kind == "red":
            return self.obj.size
        return {"phage": 1.5, "rotifer": 14, "food": 5, "hypha": 2}[self.kind]


def targets(world, *, grid=None):
    result = [Target("cell", obj) for obj in world.cells]
    result += [Target("microbe", obj) for obj in world.bacteria.values()]
    result += [Target("red", obj) for obj in world.red_cells]
    result += [Target("phage", obj) for obj in world.phages.values()]
    for obj in world.hyphae:
        if not obj.edges:
            continue
        if grid is None or grid.columns is None or grid.rows is None:
            result.append(Target("hypha", obj, obj.edges[0]))
            continue
        visible = [
            ((col - grid.columns / 2) ** 2 + (row - grid.rows / 2) ** 2, edge, col, row)
            for edge in obj.edges
            for col, row in line_pixels(*obj.nodes[edge[0]], *obj.nodes[edge[1]], grid=grid)
            if 0 <= col < grid.columns and 0 <= row < grid.rows - 1
        ]
        if visible:
            _, edge, col, row = min(visible)
            result.append(Target("hypha", obj, edge, segment_fraction(obj, edge, grid, col, row)))
    result += [Target("food", obj) for obj in world.nutrients]
    if world.events.active is not None and world.events.active.kind == "rotifer":
        result.append(Target("rotifer", world.events.active))
    return result


def segment_fraction(obj, edge, grid, col, row):
    a, b = (obj.nodes[i] for i in edge)
    ax, ay = grid.column(a[0]), grid.row(a[1])
    dx, dy = grid.column(b[0]) - ax, grid.row(b[1]) - ay
    return max(0, min(1, ((col - ax) * dx + (row - ay) * dy) / max(1e-9, dx * dx + dy * dy)))


def hit_test(world, col: int, row: int, *, grid=None):
    """Pick a body in screen coordinates, optionally through a camera projection."""
    grid = Grid() if grid is None else grid
    with projection(grid):
        return _hit_test(world, col, row, grid)


def _hit_test(world, col, row, grid):
    x, y = grid.world(col, row)
    hits = []
    for order, target in enumerate(targets(world)):
        obj = target.obj
        cx, cy = target.center
        dx, dy = x - cx, y - cy
        priority = {
            "food": 0,
            "hypha": 1,
            "red": 2,
            "phage": 3,
            "microbe": 4,
            "cell": 5,
            "rotifer": 7,
        }[target.kind]
        distance = math.hypot(dx, dy)
        if target.kind == "cell":
            inside = cell_contains(obj, x, y, world.time, padding=0.6 / grid.scale)
            order = obj.radius  # Large cells are painted over small cells.
        elif target.kind == "microbe":
            owner = next((c for c in world.cells if c.id == obj.owner), None)
            if owner and owner.state is State.ENCLOSE:
                priority = 6
            a, b = microbe_axes(obj)
            scale = bacterial_scale(obj)
            ux, uy = math.cos(obj.angle), math.sin(obj.angle)
            inside = ((dx * ux + dy * uy) / (a * scale + 0.6 / grid.scale)) ** 2 + (
                (-dx * uy + dy * ux) / (b * scale + 0.8 / grid.scale)
            ) ** 2 <= 1
        elif target.kind == "red":
            a, b = disc_axes(obj)
            inside = (dx / (a + 0.5 / grid.scale)) ** 2 + (dy / (b + 0.8 / grid.scale)) ** 2 <= 1
        elif target.kind == "phage":
            if grid.scale >= 2:
                inside = distance <= 1.5 + 0.5 / grid.scale
            elif abs(math.cos(obj.angle)) > abs(math.sin(obj.angle)):
                cx, cy = grid.point(obj.x - 0.5, obj.y)
                inside = row == cy and col in (cx, cx + 1)
            else:
                inside = (col, row) == grid.point(obj.x, obj.y)
        elif target.kind == "hypha":

            def screen_distance(edge):
                a, b = (obj.nodes[i] for i in edge)
                return segment_distance(
                    col,
                    row,
                    (grid.column(a[0]), grid.row(a[1])),
                    (grid.column(b[0]), grid.row(b[1])),
                )

            edges = sorted(obj.edges, key=screen_distance)
            target.segment = edges[0]
            target.fraction = segment_fraction(obj, target.segment, grid, col, row)
            inside = screen_distance(target.segment) <= 0.75
        elif target.kind == "rotifer":
            ux, uy = math.cos(obj.angle), math.sin(obj.angle)
            along, across = dx * ux + dy * uy, -dx * uy + dy * ux
            opening = smooth((obj.age - 14) / 6) * (1 - smooth((obj.age - 48) / 5))
            inside = (
                (along / 9.6) ** 2 + (across / 4.6) ** 2 <= 1
                or -14 <= along <= -8
                and abs(across) <= 2
                or any(
                    math.hypot(along - 11, across - sign * (1 + opening * 2.5))
                    < 1.3 + opening * 1.7
                    for sign in (-1, 1)
                )
            )
        else:
            inside = distance < obj.radius
        if inside:
            hits.append((priority, order, target))
    if not hits:
        return None
    top = max(hits, key=lambda item: item[:2])[2]
    # Nuclear bodies are shared geometry, not a sample of a style's artwork.
    if top.kind == "microbe" and top.obj.owner is not None:
        owner = next(
            (t for _, _, t in hits if t.kind == "cell" and t.obj.id == top.obj.owner), None
        )
        if owner is not None and nuclear_contains(owner.obj, col, row):
            return owner
    return top
