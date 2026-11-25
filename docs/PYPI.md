# cells

A living microscope slide in your terminal, inspired by the quiet procedural
animation of cbonsai and asciiquarium.

Macrophages and neutrophils pursue microbes, wrap them in membrane cups, and
digest them. Bacterial chains, spirochetes, vibrios, coccal colonies, budding
yeast, and trypanosomes share the slide with red blood cells, branching fungi,
and bacteriophages. Watch mitosis, viral replication and lysis, nutrient
gathering, and swimmers following fungal branches. Occasional arrivals keep
long runs varied. Rare rotifer visitors, neutrophil DNA traps, and nutrient
micropipettes add occasional longer vignettes. Use `--observe` for captions or
`--no-events` to disable them; `--calm` excludes micropipettes.

Complement can coat bacteria for immune recognition or damage susceptible
membranes; `--no-complement` disables it. Use `--magnification overview` for a wider
community or `detail` for bacterial anatomy, with H/J/K/L to pan. Classic art is
the default; `--style stained` adds filled bodies and `--style raster` selects
experimental shaded whole-specimen rendering. Unsupported terminals fall back
to classic artwork and its legend.

This is biological illustration with exaggerated sizes and timing, rather than
a scientific model.

## Installation

Python 3.10+ with the standard-library curses module is required. Linux and
macOS are supported platforms; Windows users should use WSL. There are no
third-party runtime dependencies. Some Linux distributions package curses
separately.

Install a published release in its own environment with pipx:

```sh
pipx install terminal-cells
cells
```

The distribution is named `terminal-cells`; its executable is `cells`.

## Examples

```sh
cells --seed 42
cells --theme amber --speed 0.7
cells --ascii --screensaver
cells --scene microbial --calm
cells --theme light --observe
cells --diagnostics
cells --interactive
cells --snapshot --seed 42 --size 100x32 --at 30
```

Use a terminal of at least 80 columns by 24 rows; 120 by 40 gives the detailed
organisms more space. `--theme mono` selects grayscale, and `NO_COLOR=1`
disables colors in automatic mode; `--color always` overrides it. Use
`--color never` to explicitly disable colors. Snapshots are plain ASCII and work without an interactive
terminal, including Python builds without curses.

Press `q` or Escape to quit, Space to pause, `+`/`-` to change speed, `r` for a
new slide, `s` for observations, and `?` for help with a colored species legend. Screensaver mode exits on any
key. Terminal resizing is supported.

Opt into microscope tools with `--interactive`: 1 Inspect, 2 Lyse, 3 Feed, and
4 Stir. Left-click or use arrows/hjkl, Tab, and Enter. A single bottom line shows
`? help`, the active tool, and brief feedback, leaving the rest of the screen for animation. Tools apply immediately;
keyboard targeting also works when mouse reporting is unavailable.

Released under Zero-Clause BSD (SPDX: `0BSD`). Attribution and copyleft are not
required for downstream use or redistribution.
