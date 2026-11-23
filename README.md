# cells

A living microscope slide in your terminal. Immune cells chase bacteria, cells
divide, and bacteriophages occasionally cause trouble.

![Animated terminal microscope slide with immune cells, microbes, and red blood cells](docs/demo.gif)

Inspired by [cbonsai](https://gitlab.com/jallbrit/cbonsai) and
[asciiquarium](https://github.com/cmatsuoka/asciiquarium). This is a biological
illustration with exaggerated sizes and timing.

## Install and run

Python 3.10+ on Linux or macOS, with `curses`; Windows users can use WSL.
No third-party runtime dependencies. Install with [pipx](https://pipx.pypa.io/):

```sh
pipx install terminal-cells
cells
```

If `pipx` or `cells` is not found, see [Installation and PATH](docs/TERMINALS.md#installation-and-path).

On Ubuntu 24.04 or 26.04:

```sh
sudo add-apt-repository ppa:bogobogosort/cells
sudo apt update
sudo apt install terminal-cells
cells
```

With Homebrew on macOS or Linux:

```sh
brew install kborer/cells/terminal-cells
cells
```

The package is **terminal-cells**; the command is **cells**. From a source checkout,
run `./cells`. See [Ubuntu packages](docs/UBUNTU.md) for `.deb` downloads and builds,
or [terminal troubleshooting](docs/TERMINALS.md) if colors, glyphs, or curses fail.

## Explore the slide

Use a terminal at least **80×24**; **120×40 or larger** gives organisms more room.
Press **q** to quit, **Space** to pause, **+ / -** to change speed, **r** for a new
slide, and **?** for help and the species legend.

```sh
cells --scene microbial --observe  # Microbes, with lifecycle captions
cells --scene blood               # A blood-inspired community
cells --calm --theme light        # Slower movement on a light background
cells --style microscopy --theme light  # Experimental stained/block presentation
cells --ascii                    # Plain ASCII glyphs
cells --screensaver              # Exit on any key
```

Macrophages, neutrophils, red blood cells, nine microbial forms, fungi, and phages
share the slide. Watch engulfment, mitosis, budding, viral replication, and rare
visitors. Periodic arrivals keep populations varied during long runs.

```sh
cells --interactive
```

Choose **1 Inspect**, **2 Lyse**, **3 Feed**, or **4 Stir**, then click to apply.
Keyboard targeting also works: arrows or hjkl to aim, Tab to select, Enter to
apply. Tools act while the slide keeps moving.

## Learn more

- [Command reference](docs/COMMANDS.md): controls, options, and repeatable snapshots.
- [Biology](docs/BIOLOGY.md): organisms, illustrated life cycles, and simplifications.
- [Interactive tools](docs/INTERACTION.md), [rare sightings](docs/RARE_EVENTS.md),
  and [colors](docs/COLORS.md).
- [Terminal compatibility and troubleshooting](docs/TERMINALS.md).
- [Changelog](CHANGELOG.md) and [releases](https://github.com/kborer/cells/releases/latest).

The GIF uses rendered simulation frames. The [12-second terminal recording](docs/demo.cast)
captures the curses app; replay it with `asciinema play docs/demo.cast` after cloning.

## Contribute

Biology suggestions, microscope references, screenshots, and terminal testing are
welcome; programming experience is not required. For code or documentation changes,
start with the [first-change guide](CONTRIBUTING.md) and
[starter issues](https://github.com/kborer/cells/labels/good%20first%20issue).

[Zero-Clause BSD](LICENSE) (`0BSD`): use, modify, and redistribute for any purpose,
without an attribution requirement.

