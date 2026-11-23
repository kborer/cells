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
| Identity and state | `MICROBES` in `terminal_cells/catalog.py`; `Bacterium` in `models.py` |
| Body geometry | The `vibrio` catalog entry supplies `microbe_axes()`; `bacterial_padding()` adds collision clearance |
| Initial movement | The catalog speed multiplier is applied by `World._add_bacterium()` |
| Behavior | Shared microbe updates, evasion steering, nutrient seeking, and fungal-rail selection in `world.py` |
| Body shape | The `vibrio` branch of `draw_special_microbe()` in `terminal_cells/render.py` |
| Flagellum | `draw_bacterium()` supplies the traveling wave, orientation, and clipping at obstacles |
| Color and help | `Ink.VIBRIO` and palettes in `frame.py`; keyed `BACTERIA_INKS` and `LEGEND` in `render.py` |
| Inspection name | The catalog label used by `describe()` in `interaction.py` |
| Illustrated example | `diversity_preview()` in `tools/preview.py` |
| ASCII fallback beside Unicode | `fallback_preview()` in `tools/preview.py` |

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

1. Add a keyed `MicrobeSpec` to `MICROBES` in `catalog.py`: label, body axes,
   growth, speed, blood-scene weight, bacterial identity, phage-host status, flagellum, evasion,
   fungal rails, and reproduction defaults. Existing insertion order is preserved
   for seeded selection. `MICROBE_KINDS`, `BACTERIAL_KINDS`, and
   `PHAGE_HOST_KINDS` derive from it; bacterial identity and phage susceptibility
   are separate decisions.
2. Reuse catalog-backed geometry and behavior where they fit. Dynamic state stays
   on `Bacterium` in `models.py`; interactions still belong to `world.py`. New
   behavior code is needed only when the shared lifecycle cannot express it.
3. Implement silhouette and color in each presentation that supports the new
   organism. Classic's `BACTERIA_INKS` is keyed, so adding a species cannot shift
   another species' ink. Add an `Ink` and palette entries in `frame.py` if needed,
   plus legend and illustrated previews. Inspection uses the catalog label.
4. Check growth and offspring geometry, reproduction, edge arrivals, phage-host
   selection, capture, and fungal rails. Public geometry queries are documented in
   [the extension contract](EXTENSIONS.md). Respect ownership and population caps.
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

The side by side ASCII and Unicode comparison of every inhabitant lives in
[fallback.svg](fallback.svg), generated by `fallback_preview()`.
