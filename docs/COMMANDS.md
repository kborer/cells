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
| `--style classic\|microscopy` | `classic` | Presentation; microscopy is an experimental stained/block style |
| `--theme slide\|amber\|light\|mono` | `slide` | Color palette |
| `--scene mixed\|blood\|microbial` | `mixed` | Community preset |
| `--calm` | Off | 0.5× speed, 10 FPS, and no micropipette; explicit speed/FPS override |
| `--no-events` | Off | Disable rare sightings |
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

The experimental `--style microscopy` uses stained bodies and block contours on
256-color Unicode terminals, with background tints enabled automatically. It falls
back to classic drawing for ASCII, colorless, basic-color, or limited-pair output.
Use `--theme light` on a light terminal background. Classic remains the default.

Snapshots always use ASCII without ANSI escape sequences. `--at` is simulation
time, independent of `--speed`. A seed reproduces simulation steps within the same version at a given
size; resizing and interactive actions change the subsequent history.


For mouse and keyboard microscope tools, see [interaction](INTERACTION.md).
For display problems, see [terminal compatibility](TERMINALS.md).
