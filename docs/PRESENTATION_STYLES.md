# Presentation styles

The simulation is shared; styles determine how it looks. `cells` and
`cells --style classic` use the original glyph renderer. `--fill` remains an
optional classic enhancement, and `--theme` still selects a color palette.
No microscopy style is implemented yet.

## Boundaries

```text
World (models, biology, seeded updates)
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

A style returns a new frame matching the world viewport: `round(world.width)`
columns and `round(world.height / ASPECT)` rows. It must not mutate the world,
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
register an instance under a unique name in `STYLES`. CLI choices derive from that
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

## Planned microscopy experiment

[Issue #35](https://github.com/kborer/cells/issues/35) links visual references and
[a working adaptation in Pocket](https://github.com/gordol/n810-revival/pull/17).
Its `pocket/shell/apps/cells/slide.py` combines stained raster shapes with anatomy
glyphs, stable specimen texture, pale-centered red blood cells, and half/quarter
blocks chosen from a 2-by-4 sample grid per terminal character. Its GUI frontend
and native compositor are separate from our terminal-only scope.

Prototype that as an optional style after this foundation. Start with the shared
semantic-color frame; the current curses backend supports finite 256-color pairs,
not arbitrary RGB pairs. If the experiment needs true color or a larger palette,
extend the shared frame/output contract with explicit capability negotiation and
fallbacks rather than putting terminal escape sequences in a style. Preserve our
full division and ingestion animations. Pocket's six rendered frames per second are not
evidence of performance at our normal frame rate.

Keep `classic` the default while comparing readability and performance. Live style
switching, external plugins, and a pixel GUI are future decisions, not requirements
for the first optional style.

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
size. Available scenes are division, ingestion, infection, overlap, and crowding.
