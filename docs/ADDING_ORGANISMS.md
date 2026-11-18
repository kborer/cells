# Adding or changing an organism

Start with a small visual change to an existing organism. A new kind affects
population selection, collisions, capture, reproduction, infection, and the
legend as well as its appearance. Discuss a new kind in an issue first, ideally
with microscope references and a sketch of how it will read in a terminal.

## Worked example: follow a vibrio

A vibrio is a curved bacterium with a flagellum. These are the existing pieces
to follow before changing its shape or adding a related microbial form:

| Part | Existing implementation |
| --- | --- |
| Identity and state | `MICROBE_KINDS` and `Bacterium` in `terminal_cells/models.py` |
| Body geometry | The `vibrio` entry in `microbe_axes()`; `bacterial_padding()` adds collision clearance |
| Initial movement | `World._add_bacterium()` in `terminal_cells/world.py` gives vibrio a speed multiplier |
| Behavior | Shared microbe updates, evasion steering, nutrient seeking, and fungal-rail selection in `world.py` |
| Body shape | The `vibrio` branch of `draw_special_microbe()` in `terminal_cells/render.py` |
| Flagellum | `draw_bacterium()` supplies the traveling wave, orientation, and clipping at obstacles |
| Color and help | `Ink.VIBRIO`, palettes, `BACTERIA_INKS`, and `LEGEND` in `render.py` |
| Inspection name | `describe()` in `terminal_cells/interaction.py` |
| Illustrated example | `diversity_preview()` in `tools/preview.py` |

To inspect its existing shape without waiting for a random arrival, run this
from the repository root in your development environment:

```sh
python - <<'PY'
import math
from terminal_cells import Bacterium, Frame, draw_bacterium

frame = Frame(40, 16)
vibrio = Bacterium(0, 20, 16, 0.2, 0, "vibrio", math.inf, math.inf)
draw_bacterium(frame, vibrio, False, now=0.5)
print(frame.plain())
PY
```

Try a different angle or `now` value. World positions use aspect-corrected
coordinates: `Frame.point()` divides y by `ASPECT` to obtain a terminal row.
Keep shapes in organism-local coordinates and use the existing `point()`
transform for rotation and scale. Drawing is pure; animation depends on state
and `now`, without changing either or drawing random numbers.

For a shape change, begin in the `vibrio` drawing branch. If its physical extent
changes, update `microbe_axes()` too. Check that its body remains outside membranes
and that its flagellum clips at them. Compact drawings are also used for captured
cargo, so inspect the ingestion preview as well as the free-swimming form.

## When adding a new microbial kind

Reuse `Bacterium` and the shared lifecycle where they fit. The name is historical:
yeast and trypanosomes use this model too. A separate state model is useful only
when shared state and geometry cannot express the organism's behavior.

1. Add identity, geometry, and any necessary state in `models.py`. Decide whether
   it is a bacterial phage host: `BACTERIAL_KINDS` currently treats every kind
   except yeast and trypanosome as bacterial.
2. Review population setup in `World.__init__()`: weights follow `MICROBE_KINDS`
   order, and the blood scene has a corresponding multiplier tuple. Keep them
   aligned. Missing-type arrivals and offspring selection use the shared list;
   offspring retain their parent's kind.
3. Implement its silhouette and color. `BACTERIA_INKS` pairs an ordered ink tuple
   with `MICROBE_KINDS`; extend both. If adding an ink, update every palette in
   matching enum order. Add legend and inspection names, plus an illustrated
   preview. Use shape as well as color to distinguish it.
4. Decide which behaviors apply. Review the explicit kind lists for flagella,
   evasion, fungal rails, and reproduction. Shared reproduction already handles
   ordinary fission, while yeast/trypanosomes and chains/colonies have special
   paths. Respect ownership, infection, edge entry, and population limits.
5. Update [biology](BIOLOGY.md) and [colors](COLORS.md), including biological
   simplifications. Keep the README as an overview rather than a species catalog.

An entirely new entity family, such as a multicellular visitor, may fit the rare
sighting system better. See `events.py` and `event_render.py`, rather than forcing
it into the microbe model.

## Validate the result

Start with relevant cases in `tests/test_cells.py` (rendering, membranes, microbial
reproduction, and ecological interactions), then add a focused regression for the
new behavior. Advance simulation time with `World.update()` rather than sleeping.
Verify that rendering leaves the world and its RNG unchanged.

Check ASCII/Unicode, colorless output, both background styles, a compact terminal,
capture/digestion, and resizing. For a new kind, also check reproduction preserves
its kind, arrivals enter through edges, and phage-host selection is intentional.
Run the full checks in [CONTRIBUTING](../CONTRIBUTING.md), then regenerate affected
previews with `python tools/preview.py` and `python tools/colors.py` when relevant.
Include a screenshot or recording and reproduction details in the PR.
