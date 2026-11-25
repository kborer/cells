"""Microscope tools and keyboard/mouse targeting; no terminal initialization."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .geometry import Target, hit_test, targets
from .catalog import MICROBES
from .models import ASPECT, State, clamp, division_stage, viral_stage
from .frame import Ink
from .viewport import Camera, Grid

TOOLS = ("Inspect", "Lyse", "Feed", "Stir")


def entry_phase(entry):
    if not entry.exiting:
        return "arriving from edge"
    return "withdrawing to retry arrival" if entry.retry else "leaving slide"


def describe(world, target):
    if target is None or not target.alive(world):
        return "No selection / click a body or use Tab to choose one"
    obj = target.obj
    if target.kind == "cell":
        phase = (
            division_stage(obj.elapsed)[0]
            if obj.state is State.DIVIDE
            else {
                State.WANDER: "wandering",
                State.APPROACH: "pursuing prey",
                State.ENCLOSE: "engulfing prey",
                State.DIGEST: "digesting",
            }[obj.state]
        )
        if obj.entry is not None:
            phase = entry_phase(obj.entry)
        if world.events.freezes(obj):
            phase = "releasing DNA trap"
        return f"{obj.kind.capitalize()} #{obj.id} / {phase} / vesicles {len(obj.vesicles)} / mitochondrial networks {sum(n.kind == 'mitochondrion' for n in obj.organelles)}"
    if target.kind == "microbe":
        phase = (
            "infection: " + viral_stage(obj.infection.age)[0]
            if obj.infection
            else "captured"
            if obj.owner is not None
            else "trapped"
            if world.events.trapped(obj)
            else "feeding"
            if obj.fed_until > world.time
            else "swimming"
            if obj.speed
            else "drifting"
        )
        label = MICROBES[obj.kind].label
        if obj.entry is not None:
            phase = entry_phase(obj.entry)
        if obj.complement is not None:
            phase += (
                " / complement pores"
                if obj.complement_sensitive and obj.complement.age >= 10
                else " / complement-coated"
            )
        return f"{label} #{obj.id} / {phase}"
    if target.kind == "red":
        return "Red blood cell / drifting / no nucleus"
    if target.kind == "phage":
        return f"Bacteriophage #{obj.id} / " + (
            entry_phase(obj.entry)
            if obj.entry is not None
            else "dispersing"
            if obj.flight
            else "waiting for a host"
        )
    if target.kind == "hypha":
        return f"Fungal branch / {len(obj.nodes)} compartments / growing tips {len(obj.tips)}"
    if target.kind == "food":
        return f"Nutrient cloud / food remaining {obj.amount:.1f}"
    return f"Rotifer visitor / {obj.phase} / meals {obj.eaten}"


@dataclass
class Interaction:
    col: int
    row: int
    mouse: bool = False
    tool: int = 0
    selected: Target | None = None
    tracking: bool = False
    message: str = ""
    message_until: float = 0.0
    camera: Camera | None = None
    selection_lost: bool = False

    def grid(self, world):
        return self.camera.grid(world) if self.camera is not None else Grid()

    def dimensions(self, world):
        return (
            (self.camera.columns, self.camera.rows)
            if self.camera is not None
            else (round(world.width), round(world.height / ASPECT))
        )

    def hit(self, world):
        return hit_test(world, self.col, self.row, grid=self.grid(world))

    def resize(self, columns, rows):
        self.col = int(clamp(self.col, 0, max(0, columns - 1)))
        self.row = int(clamp(self.row, 0, max(0, rows - 2)))

    def aim(self, world, col, row):
        self.selection_lost = False
        self.col, self.row = int(col), int(row)
        self.resize(*self.dimensions(world))
        self.tracking = False
        self.selected = self.hit(world)

    def cycle(self, world):
        self.selection_lost = False
        grid = self.grid(world)
        columns, rows = self.dimensions(world)
        available = []
        for target in targets(world, grid=grid):
            col, row = grid.point(*target.center)
            if 0 <= col < columns and 0 <= row < rows - 1:
                available.append(target)
        if not available:
            self.selected = None
            self.tracking = False
            return
        previous = next(
            (
                i
                for i, t in enumerate(available)
                if self.selected is not None
                and t.obj is self.selected.obj
                and t.kind == self.selected.kind
            ),
            -1,
        )
        self.selected = available[(previous + 1) % len(available)]
        self.tracking = True
        self.follow(world)

    def follow(self, world):
        if self.selected is not None and not self.selected.alive(world):
            self.selection_lost = self.tracking
            self.selected = None
            self.tracking = False
        if self.tracking and self.selected is not None:
            x, y = self.selected.center
            col, row = self.grid(world).point(x, y)
            columns, rows = self.dimensions(world)
            if not (0 <= col < columns and 0 <= row < rows - 1):
                self.selected = None
                self.tracking = False
                self.selection_lost = True
                self.message = "Selection left the view / select a visible body"
                self.message_until = math.inf
            else:
                self.col, self.row = col, row
        self.resize(*self.dimensions(world))

    def apply(self, world, now):
        self.follow(world)
        if self.tool == 1 and self.selection_lost:
            self.message = "Selection lost / click a body or use Tab to choose one"
            self.message_until = now + 4
            return
        wx, wy = self.grid(world).world(self.col, self.row)
        if self.tool == 0:
            if not self.tracking:
                self.selected = self.hit(world)
            self.tracking = self.selected is not None
            self.message = describe(world, self.selected)
        elif self.tool == 1:
            target = self.selected if self.tracking else self.hit(world)
            identity = describe(world, target)
            self.message = world.lab.lyse(world, target, wx, wy) + " / " + identity
            self.selected = target
        elif self.tool == 2:
            self.message = world.lab.feed(world, wx, wy)
            self.tracking = False
        else:
            self.message = world.lab.stir(world, wx, wy)
            self.tracking = False
        self.message_until = now + 4

    def click(self, world, col, row, now):
        columns, rows = self.dimensions(world)
        if row >= rows - 1 or col < 0 or row < 0 or col >= columns:
            return  # The toolbar is never a target for destructive actions.
        self.aim(world, col, row)
        self.apply(world, now)

    def key(self, world, key, curses, now):
        if ord("1") <= key <= ord("4"):
            self.tool = key - ord("1")
            self.message = TOOLS[self.tool] + " selected / click or Enter to apply"
            self.message_until = now + 4
            return True
        directions = {
            curses.KEY_LEFT: (-1, 0),
            curses.KEY_RIGHT: (1, 0),
            curses.KEY_UP: (0, -1),
            curses.KEY_DOWN: (0, 1),
            ord("h"): (-1, 0),
            ord("l"): (1, 0),
            ord("k"): (0, -1),
            ord("j"): (0, 1),
        }
        if key in directions:
            dx, dy = directions[key]
            self.aim(world, self.col + dx, self.row + dy)
        elif key == 9:
            self.cycle(world)
        elif key in (10, 13, getattr(curses, "KEY_ENTER", -999)):
            self.apply(world, now)
        else:
            return False
        return True

    def draw(self, frame, world, now, paused=False):
        self.follow(world)
        if self.selected is not None:
            x, y = self.selected.center
            radius = self.selected.extent + 1
            left = right = radius
            if self.selected.kind == "cell":
                left = self.selected.obj.outline(math.pi, world.time) + 1.5
                right = self.selected.obj.outline(0, world.time) + 1.5
            frame.point(x - left, y, "[", Ink.TEXT, True)
            frame.point(x + right, y, "]", Ink.TEXT, True)
        # Corner reticle leaves the aimed glyph visible.
        for dx, dy, char in ((-1, -1, "+"), (1, 1, "+")):
            frame.put(self.col + dx, self.row + dy, char, Ink.TEXT)
        bottom = frame.height - 1
        frame.text(0, bottom, " " * frame.width, Ink.TEXT)
        text = "? help" + (" / PAUSED" if paused else "") + f" / [{TOOLS[self.tool]}]"
        if now < self.message_until and self.message:
            text += " / " + self.message
        elif self.selected is not None:
            text += " / " + describe(world, self.selected)
        frame.text(0, bottom, text[: frame.width], Ink.MUTED)


def enable_mouse(curses):
    """Return capability and previous settings; callers restore them on every exit."""
    old_mask = old_interval = None
    available = False
    try:
        actions = curses.BUTTON1_PRESSED | getattr(curses, "BUTTON1_CLICKED", 0)
        # ncurses can keep reading after an excluded release event, even on a
        # nodelay window. Receive releases too, then ignore them in read_click.
        mask = actions | getattr(curses, "BUTTON1_RELEASED", 0)
        active, old_mask = curses.mousemask(mask)
        available = bool(active & actions)
        if available:
            old_interval = curses.mouseinterval(0)
    except (AttributeError, curses.error):
        pass
    return available, old_mask, old_interval


def restore_mouse(curses, old_mask, old_interval):
    if old_mask is not None:
        try:
            curses.mousemask(old_mask)
        except curses.error:
            pass
    if isinstance(old_interval, int) and old_interval >= 0:
        try:
            curses.mouseinterval(old_interval)
        except curses.error:
            pass


def read_click(curses):
    try:
        _, col, row, _, buttons = curses.getmouse()
        if not all(isinstance(value, int) for value in (col, row, buttons)) or col < 0 or row < 0:
            return None
        if buttons & (curses.BUTTON1_PRESSED | getattr(curses, "BUTTON1_CLICKED", 0)):
            return col, row
    except (AttributeError, TypeError, ValueError, curses.error):
        pass
    return None
