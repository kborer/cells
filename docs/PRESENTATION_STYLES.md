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
- `World.update`, input, timing, resize, and UI composition remain outside styles.
  Model geometry remains the authority for membranes, capture, and division.

A style returns a new frame matching the world viewport: `round(world.width)`
columns and `round(world.height / ASPECT)` rows. It must not mutate the world,
consume any simulation RNG, write to the terminal, or advance time. Use simulation
coordinates/time for deterministic texture; never use random draws during painting.
A Python protocol expresses this contract, rather than enforcing read-only models.

The session supplies resolved Unicode and fill support on every frame. In
particular, failed curses color-pair allocation can disable fill during a run.
Styles must honor those fallbacks and preserve recognizable ASCII/colorless output.
Snapshots always pass `RenderOptions()` for ASCII without background tints or
escape codes. Color policy and theme are applied by the output backend, not by
changing the world.

## Adding a style

Implement `PresentationStyle.render(world, options)` in a separate module and
register an instance under a unique name in `STYLES`. CLI choices derive from that
registry. The stateless classic adapter is the starting example. Keep any future
caches bounded; do not retain worlds in the shared style instance. Use the common
frame contract so captions, tool cursors, and terminal cleanup continue to work.

Compare seeded output, check that rendering leaves the complete world and RNG
unchanged, exercise lifecycle stages and overlapping bodies, and test resizing,
small terminals, ASCII, no color, and limited color pairs. Benchmark dense scenes
at the normal 30 FPS target. The current hit testing uses model geometry, with a
classic nuclear-occlusion tie-break in `lab.py`; revisit that tie-break if a new
style changes the apparent layering of captured microbes and nuclei.

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
