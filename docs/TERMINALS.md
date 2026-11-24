# Terminal compatibility

The animated app targets Linux and macOS with Python 3.10+ and curses. CI tests
Python 3.10 through 3.14 on Ubuntu and macOS, including pseudo-terminal sessions.
See [current CI runs](https://github.com/kborer/cells/actions/workflows/ci.yml).
Native Windows support is not claimed; use WSL.

80×24 is a useful minimum, and 120×40 shows more anatomy. Below 32×12 the
simulation pauses and asks for a larger window. Resizing keeps the slide alive.
Below 110 columns or 36 rows, the renderer shows fewer organelle details and
shorter free-swimming flagella. The underlying organisms and life cycles remain
active. Use `--density 0.7` for additional breathing room or `--density 1.5` for a
busier slide.
Help pauses the simulation; scroll with j/k or arrow keys. Quit with q/Escape.

## Colors and glyphs

- Dark background: `--theme slide` or `--theme amber`.
- Light background: `--theme light`, using darker foreground colors.
- Grayscale: `--theme mono`. Colorless: `--color never`.
- `--color auto` respects a **nonempty** `NO_COLOR`; an empty value does not
  disable color, following [the NO_COLOR convention](https://no-color.org/).
  `--color always` overrides the environment but cannot add hardware support.
- 256-color palettes fall back to eight basic colors where necessary. Limited
  palettes cannot preserve every species distinction; silhouettes still differ.
- `--unicode auto` checks the terminal encoding for UTF. Glyph widths also depend
  on the terminal and font: use `--ascii` (`--unicode never`) if lines appear
  doubled, misaligned, or replaced with boxes. A monospaced font is recommended. Compact phages use Runic `ᛘ` / `ᛦ`
  glyphs vertically; use `--ascii` if your font lacks them. Sideways phages use
  `>-` / `-<` in both modes.
- `--calm` defaults to half speed and 10 FPS and excludes micropipette visits. Explicit speed/FPS options win.
  Motion continues; Space pauses it. No claim of full screen-reader support is
  made for the continuously animated display; snapshots are plain ASCII text.

## Troubleshooting

`cells --diagnostics` prints JSON without initializing curses. Include it in a
bug report along with terminal application, selected font, background, command,
and reproduction seed. The report includes TERM, encoding, dimensions, platform,
and requested capability policies; it does not probe actual color counts or
report hostnames, usernames, filesystem paths, or other environment variables.

If Python cannot import curses, install your distribution's Python curses support
or use `--snapshot`. Help, version, diagnostics, and snapshots do not require it.
An unset/dumb TERM or redirected input/output needs `--snapshot`; choose a TERM
value matching the actual emulator for interactive use. Do not set a fabricated
TERM merely to suppress an error.

Terminal modes are restored on quit, duration expiry, Ctrl-C, and SIGTERM. A
forced SIGKILL cannot run cleanup; the shell's `reset` command can restore a
terminal after an externally killed process. Simulation and input run independently
of `--fps`; lowering the drawing rate does not slow biology. Catch-up work is capped
per simulation tick, so overload slows simulated time rather than accumulating an unbounded
backlog. `--duration` always measures wall time; `--at` measures snapshot simulation
time, independent of speed. Snapshots honor magnification and event enablement,
including calm's restriction on microscope events. Color, fill, and Unicode
effects are disabled in snapshots. They always use
ASCII without terminal escapes. Equal seeds require the same version, dimensions,
and update/resize sequence for reproducibility.

The wheel includes `share/man/man1/cells.1` under its installation prefix. View
the source copy with `man -l docs/cells.1`; pipx does not necessarily expose its
private environment's manual directory on your system MANPATH.

## Terminal compatibility report

Try the checks below in your usual terminal, then copy the checklist into a
report. Mark unknown details or unavailable checks as such. If available, attach
the output of [`cells --diagnostics`](#troubleshooting).

```text
OS and version:
Python version:
Terminal and font:
Cells version:
Terminal size (columns × rows):
Commands used:

- [ ] The slide starts, and q returns to a usable shell.
- [ ] Resizing redraws the slide without leaving old characters on screen.
- [ ] Space pauses the slide, and ? opens readable help.
- [ ] Glyphs line up with --ascii and with --unicode always.
- [ ] Text is readable on dark and light backgrounds (try --theme light).
- [ ] With --interactive, arrows move the target and Enter applies the tool.
      Try a left click if the terminal supports it.

Observed results and any steps to reproduce:
```

## Mouse and keyboard experiments

`--interactive` requests left-click reports and falls back to keyboard targeting
when the terminal does not advertise mouse support. The bottom line shows
`? help`. Use 1–4 to select tools, arrows/hjkl to aim, Tab to select an entity,
and Enter to apply. Mouse capture is opt-in and previous settings are restored
on exit. See [the interaction guide](INTERACTION.md).

## Installation and PATH

If `pipx` or `cells` is not found after installation, check which of these two cases applies.

**`pipx: command not found`**

pipx itself is not installed. Install it by following the [pipx installation guide](https://pipx.pypa.io/latest/how-to/install-pipx.html). On macOS with Homebrew, run `brew install pipx`, then check with `pipx --version`.

**`pipx` works, but `cells: command not found`**

pipx is installed, but its apps folder is not on your PATH yet. Run:

```sh
pipx ensurepath
```

Then open a new terminal window, or log in again. Check with `which cells`; it should print a path such as `~/.local/bin/cells`.

Do not fix these errors with `sudo pip` or by changing the system Python.

These steps were checked on macOS with Homebrew 7.0.14, pipx 1.18.16, and Python 3.13.
