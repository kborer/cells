# Contributing

Biology suggestions, microscope references, screenshots, terminal testing, code,
and documentation are all welcome. Programming experience is not required.
Browse [starter issues](https://github.com/kborer/cells/labels/good%20first%20issue),
or open an issue describing what you would like to improve. A brief discussion
before a large new organism or interaction helps settle scope and visual design.

This is biological illustration: sizes and timing are exaggerated for a terminal.

## Your first change

Use Python 3.10+ on Linux, macOS, or WSL. Runtime code uses only the standard
library; the animated app also needs curses. Fork the repository on GitHub, then:

```sh
git clone https://github.com/YOUR-USERNAME/cells.git
cd cells
git switch -c my-improvement
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pip install --no-deps -e .
cells --seed 42
```

Make a small change, then run the relevant tests below. For a repeatable plain-text
view without curses:

```sh
cells --snapshot --seed 42 --size 100x32 --at 30
```

A seed repeats a history within the same version, terminal size, and sequence of
steps. Resizing and interactive tools change that history.

## Where to make a change

| Task | Start here |
| --- | --- |
| Organism sizes, geometry, state | `terminal_cells/models.py` |
| Movement, capture, reproduction, arrivals | `terminal_cells/world.py` |
| Shapes, organelles, palettes | `terminal_cells/render.py` |
| Rare sightings | `terminal_cells/events.py`, `event_render.py` |
| Experimental tool effects | `terminal_cells/lab.py`, `lab_render.py` |
| Mouse/keyboard tools and footer | `terminal_cells/interaction.py` |
| Command options, help, terminal cleanup | `terminal_cells/cli.py` |
| Packaging and release automation | `pyproject.toml`, `debian/`, `tools/release.py`, `.github/workflows/` |

For a worked example, see [adding an organism](docs/ADDING_ORGANISMS.md).
`cells` and `cells.py` are source-checkout entry points; the installed command uses
`terminal_cells.cli:main`. `terminal_cells/__init__.py` exposes the compatibility API.

## Run the checks you need

Run these from the repository root with the development environment activated:

```sh
# One test module
python -m unittest discover -s tests -p 'test_scale.py' -v

# One specific test
PYTHONPATH=tests python -m unittest test_scale.ScaleTests.test_directional_sprites_remain_one_or_two_characters -v

# Before submitting a code change
ruff check .
ruff format --check .
python -m unittest discover -s tests -v
```

Use `ruff format .` to apply formatting. Documentation-only changes need a link
and command review; run any commands you introduce. Test behavior changes with a
focused regression, advancing simulated time rather than sleeping. Terminal tests
use pseudo-terminals to check input and cleanup. Hypothesis explores generated
update/resize sequences; preserve useful failures as ordinary regression tests.

## Keep these guarantees

- Drawing must not mutate the world or consume random numbers. Use `world.rng`
  for simulation randomness and fixed simulation steps for reproducibility.
- Respect membranes, exclusive ownership during capture, and population caps.
- Preserve ASCII, colorless, and small-terminal behavior.
- Rare sightings use the director's seeded RNG and unpaused wall-time clock,
  independently of simulation speed.
- Experimental tools act immediately, preserve sealed cargo, and restore mouse
  and terminal modes on every exit path.

## Check visual changes

Include a screenshot or short recording, plus the command, seed, size, and
approximate simulation time. Check `--ascii`, `--color never`, light backgrounds,
and a compact terminal when relevant. A reviewer can help with other platforms.

Regenerate only previews affected by your change:

| Change | Command |
| --- | --- |
| Organisms and life cycles | `python tools/preview.py` |
| Rare sightings | `python tools/sightings.py` |
| Palette | `python tools/colors.py` |
| Interactive tools | `python tools/experiments.py` |
| Animated demo | `python tools/demo.py` |
| CLI help/manual | `python tools/manpage.py` |

The GIF generator needs Pillow and uses Noto Sans Runic or FreeMono for phage
symbols when available; `--symbol-font PATH` supplies another Runic-capable font.
`python tools/benchmark.py` reports update/render latency without terminal output;
results depend on the machine and are not universal pass/fail limits.

## Send a pull request or report

Push your branch to your fork and open a focused PR. Explain the problem, resulting
behavior, and checks performed. You do not need release credentials or to run
publishing workflows. Packaging changes have extra checks in the
[release guide](docs/RELEASING.md); archives and wheels must work outside a checkout.

For bugs, describe what you saw. Add `cells --diagnostics`, your terminal app,
command, seed, or a screenshot when available. Unknown details are fine; you can
report an occasional event without reproducing it reliably. Report security
issues using [SECURITY.md](SECURITY.md).

Contributions use the project's [Zero-Clause BSD license](LICENSE) (`0BSD`).
No copyright assignment or separate contributor license agreement is required.
Only submit work you have the right to contribute, and identify third-party
material and its applicable terms.
