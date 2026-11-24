# Command reference

Run `cells --help` for the installed version’s options, or `man cells` where
the manual page is on your manpath. Press `?` in the running program for help
and a species legend.

## Keyboard controls

| Key | Action |
| --- | --- |
| `q` / `Esc` | Quit |
| `Space` | Pause / resume |
| `+` / `-` | Adjust simulation speed |
| `r` | New slide (advance the seed) |
| `H` / `J` / `K` / `L` | Pan left / down / up / right within a magnified specimen |
| `s` | Toggle observations, population counts, and mitotic stages |
| `?` | Toggle help; simulation pauses while help is open |
| `j` / `k`, arrows | Scroll help in short windows |
| `Ctrl-L` | Redraw |

Screensaver mode exits on any key. Resizing does not exit it.

## Options

| Option | Default | Purpose |
| --- | --- | --- |
| `--seed INTEGER` | Random | Repeat a slide at the same terminal size |
| `--density 0.25..3` | `1` | Scale populations to terminal area |
| `--speed 0.125..8` | `1` | Simulation speed |
| `--fps 1..60` | `30` | Maximum rendering rate |
| `--style classic\|stained\|raster` | `classic` | Presentation; stained and raster are experimental |
| `--magnification overview\|normal\|detail` | `normal` | Optical scale: 0.5×, 1×, or 3× |
| `--theme slide\|amber\|light\|mono` | `slide` | Color palette |
| `--scene mixed\|blood\|microbial` | `mixed` | Community preset |
| `--calm` | Off | 0.5× speed, 10 FPS, and no micropipette; explicit speed/FPS override |
| `--no-events` | Off | Disable rare sightings |
| `--no-complement` | Off | Disable dissolved complement activity |
| `--color auto\|always\|never` | `auto` | Color policy; auto respects nonempty `NO_COLOR` |
| `--fill` | Off | Tint cell bodies behind their glyphs; needs 256 colors |
| `--unicode auto\|always\|never` | `auto` | Glyph policy; auto checks UTF encoding |
| `--stats` | Off | Show population and lifecycle statistics |
| `--observe` | Off | Caption events and lifecycle stages |
| `--diagnostics` | Off | Print JSON terminal capability report and exit |
| `--ascii` | Off | ASCII glyphs only |
| `--screensaver` | Off | Any key quits |
| `--interactive` | Off | Inspect, Lyse, Feed, and Stir with mouse or keyboard |
| `--duration SECONDS` | Unlimited | Exit after a wall-clock duration |
| `--snapshot` | Off | Print a plain ASCII frame without needing a terminal |
| `--size COLSxROWS` | `80x24` | Snapshot dimensions |
| `--at SECONDS` | `12` | Snapshot simulation time, from 0 through 3600 |

```sh
cells --snapshot --seed 42 --size 100x30 --at 12
```

`--style stained` keeps classic glyph artwork and adds filled human cells with
block contours. `--style raster` instead renders the whole specimen: shaded pink
red cells, pale immune cells, purple nuclei, green microbial shapes and filaments,
and a light slide background. Raster uses a bounded 14-pigment palette and two by
four samples per character. It is an experimental approximation of a stained
specimen, not a scientific microscope simulation.

Both styles request tints automatically on 256-color Unicode terminals. ASCII,
colorless, basic-color, mono-theme, or limited-pair output falls back to classic
drawing. `--theme light` suits a light terminal background for classic/stained;
raster paints its own light field. Classic remains the default. The earlier
unreleased `microscopy` name has been replaced by `stained`.

`--magnification overview` draws a wider specimen with small microbial icons;
`detail` starts a 3× close-up on a free microbe. Uppercase H/J/K/L pan the view.
These are startup presets, not a continuously adjustable zoom. World geometry,
biological sizes, and tool distances stay in specimen units; bodies beyond the
viewport are clipped. Detail reveals additional microbial DNA marks and more
organelle detail. All styles, ASCII snapshots, resizing, and microscope tools use
the same camera mapping. [Scale comparison](magnification.svg).

Complement is a simplified ambient system in mixed/blood scenes, disabled in the
microbial preset. Sparse surface marks aid immune recognition; only explicitly
susceptible bacteria develop pores and lyse. It produces no new phages. Coating
activity is separate from rare visitor scheduling; use `--no-complement` to turn
it off, and `--observe` or Inspect to identify it.

Population density also accounts for microbial footprints. Long chains and large
swimmers use more of the growth budget than small cocci. Births can wait for
space, nearby swimmers gently separate, and obscured tails shorten. `--density`
still permits deliberately crowded scenes. Immigration can make space gradually
by letting a free swimmer leave through an edge.

Snapshots always use ASCII without ANSI escape sequences. `--at` is simulation
time, independent of `--speed`. A seed reproduces simulation steps within the same version at a given
size; resizing and interactive actions change the subsequent history.


For mouse and keyboard microscope tools, see [interaction](INTERACTION.md).
For display problems, see [terminal compatibility](TERMINALS.md).
