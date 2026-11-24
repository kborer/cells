# Presentation styles

The simulation is shared; styles determine how it looks. `cells` and
`cells --style classic` use the original glyph renderer. `--fill` remains an
optional classic enhancement, and `--theme` still selects a color palette.
`cells --style stained` opts into an experimental stained/block presentation;
`--theme light` suits a light terminal background. It automatically requests body
tints and falls back to classic drawing when color, block glyphs, or sufficient
color pairs are unavailable. Snapshots remain plain ASCII in every style.
`cells --style raster` uses a separate whole-specimen shaded rendering path; it
is described below. The earlier unreleased `microscopy` name is now `stained`.

## Boundaries

```text
World (models, biology, seeded updates)
  -> Camera / scoped specimen-to-terminal Grid
  -> PresentationStyle.render(world, RenderOptions)
  -> Frame (Pixel grid with semantic foreground/background inks)
  -> session overlays (help, observations, interactive cursor)
  -> TerminalRenderer (curses colors, changed spans, terminal writes)
```

- `terminal_cells/styles.py` defines the protocol, immutable rendering options,
  explicit built-in registry, and classic adapter. Both the animated session and
  snapshot command dispatch through it. There is no dynamic plugin loading.
- `terminal_cells/frame.py` owns the shared frame, pixel, semantic inks, palettes,
  and grid primitives. Styles can draw blocks as well as ordinary glyphs.
- `terminal_cells/render.py` remains the classic drawing implementation and
  re-exports its original frame API for existing callers and preview tools.
- `terminal_cells/capabilities.py` describes resolved color, glyph, background,
  color-pair, and theme support. `RenderOptions.resolve()` negotiates effects.
- `World.update`, input, timing, resize, and UI composition remain outside styles.
  Model geometry remains the authority for membranes, capture, and division.

A style returns a fresh frame allocated with `Frame.from_world(world)`. Without a
camera it has `round(world.width)` columns and `round(world.height / ASPECT)` rows;
with a camera it matches the physical terminal viewport. It must not mutate the world,
consume any simulation RNG, write to the terminal, or advance time. Use simulation
coordinates/time for deterministic texture; never use random draws during painting.
A Python protocol expresses this contract, rather than enforcing read-only models.

The session supplies resolved `RenderCapabilities` on every frame: Unicode,
block-glyph permission, 0/8/256 colors, background support, available color pairs,
and theme. `RenderOptions.resolve(capabilities, fill=requested)` enables only
supported effects. A style can inspect `options.capabilities` to choose its
presentation. The two-flag `RenderOptions(unicode, fill)` constructor remains
available for existing drawing tools that have already resolved those flags. In
particular, failed curses color-pair allocation can disable fill during a run.
Styles must honor those fallbacks and preserve recognizable ASCII/colorless output.
Snapshots always negotiate monochrome ASCII capabilities for ASCII without background tints or
escape codes. Color policy and theme are applied by the output backend, not by
changing the world.

## Adding a style

Implement `PresentationStyle.render(world, options)` in a separate module and
register an instance under a unique name in `STYLES`. Set `default_fill` to request
background tints automatically, and implement `palette(theme)` to return a full
semantic-ink palette (256-color/basic-color pairs). Preserve species/effect color
meanings when changing stain backgrounds. CLI choices derive from that
registry. The stateless classic adapter is the starting example. Keep any future
caches bounded; do not retain worlds in the shared style instance. Implement
`cache_info()` returning a mapping of cache names to `CacheInfo(size, limit)`;
report every retained drawing cache. Classic has no caches and returns `{}`. Use the common
frame contract so captions, tool cursors, and terminal cleanup continue to work.

Compare seeded output, check that rendering leaves the complete world and RNG
unchanged, exercise lifecycle stages and overlapping bodies, and test resizing,
small terminals, ASCII, no color, and limited color pairs. Benchmark dense scenes
at the normal 30 FPS target. Use public `World.obstacles()` / `World.is_blocked()` and the queries in
`geometry.py`. Selection and nuclear foreground now share geometry and never
render a classic frame. Preserve that shared foreground order in new styles.

## Experimental stained style

[Compare classic and stained](stained.svg), generated with
`python tools/gallery.py --scene ingestion --at 9 --style classic --style stained --theme light --fill --output docs/stained.svg`.

[Issue #35](https://github.com/kborer/cells/issues/35) and the
[Pocket adaptation](https://github.com/gordol/n810-revival/pull/17) inspired this
terminal-only experiment. `stained.py` independently paints four coverage
samples per character into half/quarter blocks, with specimen-local deterministic
granules, pale red-cell centers, and stained cytoplasm and nuclei. It uses the
shared geometry and composites the existing organelles, capture effects, mitosis,
viral cycle, and tool effects. DNA-trap sources retain their canonical fade.

The prototype uses finite semantic-color pairs, not true-color raster output.
Species and transient-effect hues retain their classic meanings; only cytoplasm
and stain backgrounds differ. The backend reserves up to 252 color pairs, below
the 256-pair limit. ASCII, basic-color, colorless, mono-theme, and plain snapshot
output use classic drawing. A failed tint allocation also triggers that fallback.

Classic remains the default. The experiment does more work per frame: in one
local dense-scene measurement, classic/stained rendering took approximately
4/13 ms at 80x24, 9/22 ms at 120x40, and 20/51 ms at 200x60, excluding terminal
writes. These are observations, not portable limits. Large dense views can fall
below 30 FPS; caching and finer stain design are further experiments. Measure
styles on your machine with:

```sh
python tools/benchmark.py --style stained --samples 100
python tools/benchmark.py --style classic --fill --samples 100
```

Live switching, external plugins, a pixel GUI, and a true-color backend remain
future decisions. The stained prototype is not a replacement for classic.

## Experimental raster style

[View the raster blood smear](raster.svg). Generate it with:

```sh
python tools/gallery.py --scene blood-smear --at 0 --style raster --output docs/raster.svg
```

`raster.py` paints a shared specimen field at two horizontal by four vertical
samples per terminal cell, then approximates each tile using foreground color,
background color, and a block glyph. Every ordinary entity family is rendered
into the field, including red cells, immune cells, microbes, phages, fungi, food,
and debris. Human cells are not simply filled behind classic outlines. Shading
and granules are anchored to the specimen; drawing never consumes simulation RNG.

The visual target is the terminal panel in the
[Pocket comparison](https://github.com/kborer/cells/issues/35#issuecomment-7073405367).
This is an independent implementation using shared model geometry and a bounded
14-pigment xterm palette, so it approximates rather than reproduces that project's
true-color output. The light field is part of the image, regardless of terminal
background. A style-specific legend explains its coherent stain colors.

Mitosis dissolves and reforms nuclear pigment; canonical chromosome/spindle marks
remain readable. Capture ownership and nuclear foreground are preserved. Viral
replication/assembly/lysis marks, DNA traps, glass, visitors, and tool fragments
remain visible. Glyphs for explanatory genetic events may be composited over the
raster; ordinary bacteria, membranes, and organelles are pigment shapes/strokes.

`Frame.indexed()` supplies explicit 0..255 foreground/background colors while
retaining each pixel's semantic ink. Plain UI overlays replace indexed tiles.
Fourteen pigments have at most 196 ordered pairs; together with 42 semantic UI
pairs this stays below 256. The backend caches pairs without reassigning them,
compares indexed colors during incremental output, and falls back after allocation
failure. Unsupported color/glyph output and snapshots use classic drawing.
The tile cache is bounded to 2,048 pigment patterns and retains no worlds.

Measure performance using `python tools/benchmark.py --style raster`. Sampling
and quantization add work and can reduce FPS in large or dense views. Increasing
pigment count beyond the pair budget requires a different backend strategy;
`COLORTERM` alone does not turn the curses renderer into a true-color backend.

## Run contributor contract checks

`python -m unittest discover -s tests -p test_extensions.py -v` exercises every
registered style across staged lifecycle scenes, ASCII/Unicode, monochrome/basic/
256-color output, background tints, resizing, and tiny viewports. It also checks
that the test helpers reject broken example styles.

Use `style_checks.check_style(style, world, options)` for your own scenes. It checks
world/RNG purity, fresh frames, deterministic drawing, dimensions, supported glyphs,
fallbacks, and reported cache bounds. `check_world_retention(style, make_world,
options)` checks that a style does not retain a completed World. These are opt-in
test tools using serialization and garbage collection, not per-frame production
checks. Cache reporting is a contributor contract, not a memory sandbox.

For a visual comparison:

```sh
python tools/gallery.py --scene ingestion --at 9 --fill --output /tmp/ingestion.svg
python tools/gallery.py --scene division --output /tmp/division.svg
python tools/gallery.py --scene infection --at 18 --output /tmp/infection.txt
```

Repeat `--style NAME` to compare registered styles on identical independently
built worlds, or omit it to include all styles. Omitting `--at` shows the scene's
sampled stages. SVG output preserves foreground and background colors; `.txt` and
stdout always use plain ASCII. `--ascii`, `--theme light`, and `--theme mono` help
compare fallbacks. Labels record scene, style, seed, actual simulation time, and
size. Available scenes are division, ingestion, infection, overlap, crowding, and blood-smear.

## Half-block comparison study

`python tools/preview.py` also writes [halfblock.svg](halfblock.svg), contributed
by [shiwng](https://github.com/kborer/cells/pull/38). It compares the same seeded
slide as line art and as two vertically sampled rows per terminal cell. This is
an offline silhouette experiment, not a selectable runtime style. Each output
cell uses one ink: when the two samples differ, the lower sample wins. It does
not yet preserve two independent colors or replace strokes with filled anatomy.
The preview uses a scoped sampling grid instead of changing module globals;
ordinary rendering resumes with its previous projection. Existing ASCII/Unicode comparison previews remain available.

## Magnification and camera coordinates

`viewport.py` owns a finite, immutable `Grid` and a lightweight `Camera`. The
session selects overview (0.5×), normal (1×), or detail (3×) and calls
`camera.render(style, world, options)`. This scopes the grid with a `ContextVar`
and restores it on success or exception. No model coordinates, sizes, collision
rules, or simulation RNG are changed by rendering or panning.

Styles allocate with `Frame.from_world(world, fill)` so the camera controls output
dimensions. `frame.grid` maps specimen coordinates to terminal positions and back.
`Frame.point` and `Frame.line` use that grid; `Frame.put` and `Frame.text` remain
terminal-coordinate operations for already-rasterized art and UI. Pixel-space
coverage loops use `grid.column`, `grid.row`, and `grid.world`. Standalone drawing
studies can use `with projection(grid): ...`; avoid module-global overrides.

The classic renderer changes detail at coarse/fine scales rather than stretching
finished characters. Stained coverage and raster pigment samples use the same
world-space grid. Frames retain their immutable grid for later tool overlays.
`hit_test(..., grid=...)` and the interactive controller use inverse projection,
including for tiny phages and foreground priority over enclosed cargo.

`check_style(..., camera=camera)` checks purity, fallbacks, determinism, and physical
viewport dimensions at any scale. The gallery and benchmark accept
`--magnification`; repeat the gallery option for a same-specimen comparison:

```sh
python tools/gallery.py --scene crowding --at 12 --style classic --magnification overview --magnification normal --magnification detail --output docs/magnification.svg
python tools/gallery.py --scene complement --at 12 --style classic --style raster --output docs/complement.svg
```

Normal rendering retains its original projection. Startup overview creates a
larger specimen to fill its wider field; detail clips the original specimen and
starts near a free microbe. Continuous zoom and runtime scale switching remain
possible future work. Raster shading remains experimental and can reduce FPS;
measure the desired style, scale, terminal size, and density before optimizing.
