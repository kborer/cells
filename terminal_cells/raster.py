"""Whole-specimen indexed raster, sampled at two by four points per character.

The paper, cells, microbes, organelles, and filaments share one shaded field.
Fourteen pigments bound every foreground/background combination to 196 pairs,
leaving room for semantic UI colors on a 256-pair curses terminal.
"""

from array import array
from collections import Counter
from functools import lru_cache
import math

from .catalog import MICROBES
from .crowding import tail_fraction
from .frame import Frame, Ink
from .geometry import nuclear_bodies
from .models import (
    DIVISION_TIME,
    SEAL_TIME,
    State,
    bacterial_scale,
    disc_axes,
    division_stage,
    microbe_axes,
    nucleus_radii,
    smooth,
)
from .render import render as classic_render
from .stained import grain
from .viewport import CURRENT

# Paper; three eosin reds; gray/lavender cytoplasm; purple chromatin;
# pale cytoplasm; three microbial greens; neutral glass/flagella.
COLORS = (255, 224, 217, 175, 252, 253, 139, 96, 53, 254, 65, 108, 151, 244)
PATTERNS = (
    (0, " "),
    (15, "▀"),
    (192, "▂"),
    (240, "▄"),
    (252, "▆"),
    (85, "▌"),
    (170, "▐"),
    (5, "▘"),
    (10, "▝"),
    (80, "▖"),
    (160, "▗"),
    (165, "▚"),
    (90, "▞"),
    (95, "▛"),
    (175, "▜"),
    (245, "▙"),
    (250, "▟"),
    (255, "█"),
)
# Keep explanatory lifecycle marks, while normal anatomy is drawn as pigment.
MARKS = frozenset((Ink.DNA, Ink.SPINDLE, Ink.CAPTURE, Ink.VIRAL_DNA, Ink.LYSIS, Ink.COMPLEMENT))
EFFECTS = frozenset((Ink.NET, Ink.ROTIFER, Ink.GLASS))
ROLE_COLOR = {
    Ink.DNA: 8,
    Ink.SPINDLE: 7,
    Ink.CAPTURE: 3,
    Ink.VIRAL_DNA: 10,
    Ink.LYSIS: 6,
    Ink.COMPLEMENT: 13,
    Ink.NET: 6,
    Ink.ROTIFER: 3,
    Ink.GLASS: 13,
    Ink.MITOCHONDRION: 6,
    Ink.RETICULUM: 5,
    Ink.VESICLE: 11,
}


def rgb(index):
    if index >= 232:
        return (8 + (index - 232) * 10,) * 3
    levels = (0, 95, 135, 175, 215, 255)
    index -= 16
    return levels[index // 36], levels[index // 6 % 6], levels[index % 6]


DISTANCE = tuple(
    tuple(sum((a - b) ** 2 for a, b in zip(rgb(x), rgb(y))) for y in COLORS) for x in COLORS
)


@lru_cache(maxsize=2048)
def tile(samples):
    """Approximate eight pigment samples with one block and two colors."""
    counts = Counter(samples)
    background = counts.most_common(1)[0][0]
    if len(counts) == 1:
        return " ", COLORS[background], COLORS[background]
    foreground = max(
        (color for color in counts if color != background),
        key=lambda color: DISTANCE[background][color] * math.sqrt(counts[color]),
    )
    mask = sum(
        1 << i
        for i, color in enumerate(samples)
        if DISTANCE[color][foreground] < DISTANCE[color][background]
    )
    _, glyph = min(
        PATTERNS, key=lambda entry: ((mask ^ entry[0]).bit_count(), entry[0] == 0 and mask != 0)
    )
    return glyph, COLORS[foreground], COLORS[background]


class Field:
    """Per-frame pigment samples; all painting uses specimen coordinates."""

    def __init__(self, columns, rows):
        self.grid = CURRENT.get()
        self.width, self.height = columns * 2, rows * 4
        self.colors = array("B", [0]) * (self.width * self.height)
        self.roles = array("B", [Ink.DEBRIS.value]) * len(self.colors)

    def paint(self, x, y, extent_x, extent_y, shade, role):
        left, right = (
            max(0, math.floor((self.grid.column(x - extent_x) + 0.5) * 2)),
            min(self.width, math.ceil((self.grid.column(x + extent_x) + 0.5) * 2)),
        )
        top, bottom = (
            max(0, math.floor((self.grid.row(y - extent_y) + 0.5) * 4)),
            min(self.height, math.ceil((self.grid.row(y + extent_y) + 0.5) * 4)),
        )
        for py in range(top, bottom):
            dy = self.grid.world(0, (py + 0.5) / 4 - 0.5)[1] - y
            base = py * self.width
            for px in range(left, right):
                dx = self.grid.world((px + 0.5) / 2 - 0.5, 0)[0] - x
                color = shade(dx, dy)
                if color is not None:
                    self.colors[base + px] = color
                    self.roles[base + px] = role.value

    def ellipse(self, x, y, a, b, pigment, ident=0, angle=0, role=Ink.DEBRIS, keep=None):
        ca, sa = math.cos(angle), math.sin(angle)

        def shade(dx, dy):
            if keep is not None and not keep(x + dx, y + dy):
                return None
            u, v = (dx * ca + dy * sa) / a, (-dx * sa + dy * ca) / b
            r = math.hypot(u, v)
            if r > 1:
                return None
            noise = (grain(dx, dy, ident) - 23) / 47
            if pigment == "red":
                # A biconcave, softly shaded annulus rather than a flat disc.
                ring = math.exp(-(((r - 0.68) / 0.23) ** 2))
                value = ring + 0.12 * v + 0.16 * noise
                if r > 0.94:
                    return 1 if value < 0.45 else 2
                return 1 if value < 0.3 else 2 if value < 0.78 else 3
            if pigment == "nucleus":
                value = 0.48 + 0.3 * r + 0.5 * noise - 0.12 * u
                return 6 if value < 0.38 else 7 if value < 0.76 else 8
            if pigment == "microbe":
                value = 0.35 + 0.4 * r + 0.2 * noise
                return 12 if value < 0.4 else 11 if value < 0.65 else 10
            return 6 if r < 0.65 else 9

        self.paint(x, y, max(a, b), max(a, b), shade, role)

    def line(self, x, y, xx, yy, color, role, keep=None):
        # Round caps make organelle tubules and flagella continuous under motion.
        count = max(1, math.ceil(math.hypot(xx - x, yy - y) * 2 * self.grid.scale))
        for step in range(count + 1):
            wx, wy = x + (xx - x) * step / count, y + (yy - y) * step / count
            if keep is not None and not keep(wx, wy):
                continue
            px, py = (
                round((self.grid.column(wx) + 0.5) * 2 - 0.5),
                round((self.grid.row(wy) + 0.5) * 4 - 0.5),
            )
            if 0 <= px < self.width and 0 <= py < self.height:
                self.colors[py * self.width + px] = color
                self.roles[py * self.width + px] = role.value

    def frame(self):
        frame = Frame(self.width // 2, self.height // 4, fill=True)
        frame.grid = self.grid
        for row in range(frame.height):
            for col in range(frame.width):
                samples = tuple(
                    self.colors[(row * 4 + y) * self.width + col * 2 + x]
                    for y in range(4)
                    for x in range(2)
                )
                char, color, background = tile(samples)
                role = Ink(self.roles[(row * 4 + 2) * self.width + col * 2 + 1])
                frame.indexed(col, row, char, color, background, role)
        return frame


def microbe(field, world, obj, compact=False):
    a, b = microbe_axes(obj)
    scale = bacterial_scale(obj) * (min(0.65, 2.2 / a) if compact else 1)
    ca, sa = math.cos(obj.angle), math.sin(obj.angle)

    def point(along, across):
        return obj.x + scale * (ca * along - sa * across), obj.y + scale * (
            sa * along + ca * across
        )

    def body(along, across, rx, ry=None):
        field.ellipse(
            *point(along, across),
            rx * scale,
            (ry or rx) * scale,
            "microbe",
            obj.id,
            obj.angle,
            Ink.BACTERIA,
        )

    if obj.kind == "bacillus":
        for i in range(obj.units):
            body((i - (obj.units - 1) / 2) * 3.4, 0, 2.3, 1.6)
    elif obj.kind == "colony":
        body(0, 0, 1.3)
        for i in range(obj.units):
            theta = i * math.tau / obj.units
            body(3.1 * math.cos(theta), 3.1 * math.sin(theta), 1.3)
    elif obj.kind in ("spiral", "spirochete", "vibrio"):
        previous = None
        for i in range(33):
            t = i / 32
            across = (
                1.1 * math.sin(t * math.tau * 2 - world.time * 5 + obj.id)
                if obj.kind != "vibrio"
                else 1.3 * math.cos((t - 0.5) * math.pi)
            )
            pos = point((2 * t - 1) * a, across)
            field.ellipse(*pos, 0.65 * scale, 0.65 * scale, "microbe", obj.id, role=Ink.BACTERIA)
            if previous is not None:
                field.line(*previous, *pos, 10, Ink.BACTERIA)
            previous = pos
    else:
        body(0, 0, a, b)
        if obj.bud:
            body(a + obj.bud, 0, 0.5 + 2 * obj.bud)
    if MICROBES[obj.kind].flagellum and not compact:
        previous = point(-a, 0)
        tail = tail_fraction(world, obj)
        for i in range(1, 17):
            t = i / 16
            pos = point(-a - 5 * t * tail, t * tail * math.sin(8 * t - world.time * 7 + obj.id))
            if world.is_blocked(*pos, padding=1.1):
                break
            field.line(*previous, *pos, 10, Ink.BACTERIA)
            previous = pos
    if field.grid.scale >= 2 and obj.infection is None and not compact:
        previous = None
        for i in range(9):
            along = (i / 8 - 0.5) * a
            pos = point(along, math.sin(i * 1.5) * b * 0.25)
            if previous is not None:
                field.line(*previous, *pos, 6, Ink.MICROBIAL_DNA)
            previous = pos
    if obj.infection:
        field.ellipse(obj.x, obj.y, 0.7, 0.7, "nucleus", role=Ink.VIRAL_DNA)


def nuclei(field, cell):
    if cell.kind != "neutrophil" and cell.state is State.DIVIDE:
        stage, progress = division_stage(cell.elapsed)
        if stage in ("prophase", "envelope breakdown"):
            rx, ry = nucleus_radii(cell.radius)
            keep = (
                None
                if stage == "prophase"
                else lambda x, y: grain(x - cell.x, y - cell.y, cell.id) / 47 > progress
            )
            field.ellipse(cell.x, cell.y, rx, ry, "nucleus", cell.id, role=Ink.NUCLEUS, keep=keep)
        elif stage in ("telophase", "cytokinesis"):
            separation = (
                cell.radius * (0.55 + 0.165 * smooth(progress))
                if stage == "telophase"
                else cell.radius * 0.715
            )
            rx, ry = nucleus_radii(cell.radius * 0.72)
            for sign in (-1, 1):
                x = cell.x + sign * separation * math.cos(cell.division_angle)
                y = cell.y + sign * separation * math.sin(cell.division_angle)
                keep = (
                    None
                    if stage == "cytokinesis"
                    else lambda xx, yy: grain(xx - x, yy - y, cell.id) / 47 < progress
                )
                field.ellipse(x, y, rx, ry, "nucleus", cell.id, role=Ink.NUCLEUS, keep=keep)
        return
    bodies = list(nuclear_bodies(cell))
    if cell.kind == "neutrophil":
        for left, right in zip(bodies, bodies[1:]):
            field.line(*left[:2], *right[:2], 7, Ink.NUCLEUS)
    for x, y, radius, nucleolus in bodies:
        rx, ry = nucleus_radii(radius)
        field.ellipse(x, y, rx, ry, "nucleus", cell.id, role=Ink.NUCLEUS)
        if nucleolus:
            field.ellipse(x, y, 0.65, 0.65, "nucleus", role=Ink.NUCLEOLUS)


def cell_body(field, world, cell, fade=1, show_nucleus=True):
    def shade(dx, dy):
        distance = math.hypot(dx, dy)
        boundary = cell.outline(math.atan2(dy, dx), world.time)
        if distance > boundary:
            return None
        r = distance / max(1, boundary)
        noise = grain(dx, dy, cell.id)
        if noise / 47 >= fade:
            return None
        if noise < 1:
            return 6
        return 4 if r > 0.9 else 5 if noise < 8 else 9

    field.paint(cell.x, cell.y, cell.extent(), cell.extent(), shade, Ink.CYTOPLASM)
    division = (
        smooth((cell.elapsed - 26) / (DIVISION_TIME - 26)) if cell.state is State.DIVIDE else 0
    )
    ux, uy = math.cos(cell.division_angle), math.sin(cell.division_angle)

    def inside(x, y):
        dx, dy = x - cell.x, y - cell.y
        return (
            math.hypot(dx, dy) < cell.outline(math.atan2(dy, dx), world.time) - 1.1
            and grain(dx, dy, cell.id) / 47 < fade
        )

    for network in cell.organelles:
        nodes, sides = [], []
        for x, y in network.nodes:
            side = 1 if x * ux + y * uy >= 0 else -1
            sides.append(side)
            nodes.append(
                (
                    cell.x
                    + (x * (1 - 0.28 * division) + side * ux * 0.62 * division) * cell.radius,
                    cell.y
                    + (y * (1 - 0.28 * division) + side * uy * 0.62 * division) * cell.radius,
                )
            )
        for a, b in network.edges:
            if cell.state is State.DIVIDE and cell.elapsed >= 40 and sides[a] != sides[b]:
                continue
            field.line(
                *nodes[a],
                *nodes[b],
                6 if network.kind == "mitochondrion" else 5,
                Ink.MITOCHONDRION if network.kind == "mitochondrion" else Ink.RETICULUM,
                inside,
            )
    for vesicle in cell.vesicles:
        x = cell.x + math.cos(vesicle.angle) * cell.radius * vesicle.distance
        y = cell.y + math.sin(vesicle.angle) * cell.radius * vesicle.distance
        field.ellipse(x, y, 2, 2, "microbe", cell.id, role=Ink.VESICLE, keep=inside)
    if show_nucleus:
        nuclei(field, cell)


def phage(field, obj, empty=False):
    ca, sa = math.cos(obj.angle), math.sin(obj.angle)

    def point(along, across):
        return obj.x + ca * along - sa * across, obj.y + sa * along + ca * across

    if empty:
        for i in range(8):
            a, b = i * math.tau / 8, (i + 1) * math.tau / 8
            field.line(
                *point(-0.5 + 0.6 * math.cos(a), 0.6 * math.sin(a)),
                *point(-0.5 + 0.6 * math.cos(b), 0.6 * math.sin(b)),
                13,
                Ink.PHAGE,
            )
    else:
        field.ellipse(*point(-0.5, 0), 0.6, 0.6, "platelet", role=Ink.PHAGE)
    field.line(*point(0, 0), *point(1.1, 0), 13, Ink.PHAGE)
    for side in (-1, 1):
        field.line(*point(1.1, 0), *point(1.4, side * 0.65), 13, Ink.PHAGE)


def supported(options):
    caps = options.capabilities
    return bool(
        options.fill
        and caps is not None
        and caps.colors >= 256
        and caps.blocks
        and caps.color_pairs > len(Ink) + len(COLORS) ** 2
    )


def render(world, options):
    if not supported(options):
        return classic_render(world, options.unicode, options.fill)
    grid = CURRENT.get()
    field = Field(
        grid.columns or round(world.width), grid.rows or round(world.height / grid.aspect)
    )
    source = classic_render(world, True, True)
    for patch in world.nutrients:
        field.ellipse(
            patch.x,
            patch.y,
            min(2, patch.radius * 0.3),
            min(2, patch.radius * 0.3),
            "platelet",
            role=Ink.NUTRIENT,
        )
    for item in world.debris:
        field.ellipse(item.x, item.y, item.size * 0.5, item.size * 0.5, "platelet", role=Ink.DEBRIS)
    for branch in world.hyphae:
        for a, b in branch.edges:
            field.line(*branch.nodes[a], *branch.nodes[b], 11, Ink.FUNGUS)
    for disc in world.red_cells:
        field.ellipse(
            disc.x, disc.y, *disc_axes(disc), "red", ident=round(disc.phase * 100), role=Ink.RED
        )
    for obj in world.phages.values():
        phage(field, obj)
    for obj in world.spent_capsids:
        phage(field, obj, True)
    captured = {c.target: c for c in world.cells if c.state is State.ENCLOSE}
    for obj in world.bacteria.values():
        if obj.id not in captured:
            microbe(field, world, obj)
    for cell in sorted(world.cells, key=lambda c: c.radius):
        event = world.events.active
        if event is not None and event.kind == "net" and event.source == cell.id and event.age >= 2:
            cell_body(field, world, cell, 1 - smooth((event.age - 6) / 4), False)
        else:
            cell_body(field, world, cell)
    for ident, owner in captured.items():
        obj = world.bacteria.get(ident)
        if obj is not None:
            microbe(field, world, obj, owner.elapsed >= SEAL_TIME)
            nuclei(field, owner)
    # Rare visitors and glass use the canonical visibility mask, then become
    # pigment strokes. They keep occlusion and animation without ASCII outlines.
    for row, pixels in enumerate(source.pixels):
        for col, pixel in enumerate(pixels):
            if pixel.char != " " and pixel.ink in EFFECTS:
                color = ROLE_COLOR[pixel.ink]
                x, y = grid.world(col, row)
                dx, dy = (
                    (0.45, 0.8)
                    if pixel.char in ("/", "\\")
                    else (0.45, 0)
                    if pixel.char in ("-", "─", "_")
                    else (0, 0.8)
                )
                if pixel.char == "/":
                    dx = -dx
                field.line(x - dx, y - dy, x + dx, y + dy, color, pixel.ink)
    for pulse in world.lab.stirs + world.lab.pings:
        for i in range(12):
            angle = math.tau * i / 12 + pulse.age * 2
            radius = 2 + pulse.age * 4
            x, y = pulse.x + radius * math.cos(angle), pulse.y + radius * math.sin(angle)
            if not world.is_blocked(x, y, padding=0.2):
                field.ellipse(x, y, 0.3, 0.3, "platelet", role=Ink.NUTRIENT)
    for effect in world.lab.ruptures:
        visible = 1 - smooth((effect.age - 3) / 4)
        for i, piece in enumerate(effect.fragments):
            if (i * 17) % 23 / 23 > visible:
                continue
            pigment = (
                "nucleus"
                if piece.role in ("nucleus", "microbial_dna")
                else "red"
                if piece.role.startswith("red")
                else "microbe"
                if piece.role in ("microbe", "fungus")
                else "platelet"
            )
            role = (
                Ink.NUCLEUS
                if pigment == "nucleus"
                else Ink.RED
                if pigment == "red"
                else Ink.BACTERIA
                if pigment == "microbe"
                else Ink.LYSIS
            )
            field.ellipse(piece.x, piece.y, 0.65, 0.5, pigment, i, role=role)
    frame = field.frame()
    infected = [b for b in world.bacteria.values() if b.infection is not None]

    def assembled(col, row):
        for obj in infected:
            a, b = microbe_axes(obj)
            scale = bacterial_scale(obj)
            wx, wy = grid.world(col, row)
            dx, dy = wx - obj.x, wy - obj.y
            ca, sa = math.cos(obj.angle), math.sin(obj.angle)
            if ((dx * ca + dy * sa) / (a * scale + 1)) ** 2 + (
                (-dx * sa + dy * ca) / (b * scale + 1)
            ) ** 2 <= 1:
                return True
        return False

    for row, pixels in enumerate(source.pixels):
        for col, pixel in enumerate(pixels):
            assembly = pixel.ink is Ink.PHAGE and assembled(col, row)
            if pixel.char != " " and (pixel.ink in MARKS or assembly):
                background = frame.pixels[row][col].background
                frame.indexed(
                    col,
                    row,
                    pixel.char,
                    COLORS[ROLE_COLOR.get(pixel.ink, 8)],
                    background,
                    pixel.ink,
                    pixel.bold,
                )
    return frame
