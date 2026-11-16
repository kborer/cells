# Changelog

## Unreleased

- Add Debian-format packaging and Ubuntu 24.04/26.04 build and installation checks.

## 0.1.0 — 2026-11-16

First release, available on PyPI and GitHub.

- Let immune cells crawl against ordinary slide flow and turn away from screen
  edges instead of accumulating at the right boundary.
- Hide microscope-tool instructions in ambient help and space interactive tools,
  targeting controls, and the species legend into separate groups.

- Fix animation freezing on mouse release: receive release events from curses
  and discard them without applying a second tool action.
- Add opt-in `--interactive` mode with Inspect, Lyse, Feed, and Stir tools, a
  single-line `? help` footer, visible selection, left-click input, and keyboard targeting.
- Add immediate rupture with organelle debris, red-cell ghosts, local fungal cuts,
  assembly-aware viral release, and containment of disrupted phagosome contents.
- Add bounded local stirring and clear-fluid food deposits; restore mouse settings
  on every exit and retain unattended/snapshot behavior.
- Make tool effects immediate without freezing targets; strengthen stirring,
  move particles at the click center, and carry capsids and rupture debris.
- Add tool/terminal/property tests and an illustrated interactive guide.

- Add rare rotifer feeding visits, destructive neutrophil DNA traps, and nutrient
  micropipettes with seeded scheduling, cooldowns, and bounded population effects.
- Pace interactive sightings by unpaused wall time; add `--no-events`, captions,
  and calm-mode exclusion of microscope interventions.
- Review every palette: distinguish all microbial body hues, reserve red/lime
  for red cells/phages, and add coral/lilac/gray rare-event identities.
- Render the help legend in the active palette and add complete color/sighting
  guides and reproducible preview generators.

- Enlarge macrophages by about 18% where space permits, keeping neutrophils
  and compact-terminal fitting unchanged.
- Render phages as compact directional Runic/ASCII glyphs, shrink their
  collision footprint, and use the host outline for infection contact.
- Preserve genome injection, replication, assembly, and lysis with compact phages.

- Adopt Zero-Clause BSD (`0BSD`) for the project, package metadata, and
  contributions, without requiring downstream attribution or copyleft.

- Split models, simulation, rendering, and CLI into `terminal_cells` modules;
  preserve source-checkout entry points.
- Add blood/microbial scenes, calm defaults, light theme, observation captions,
  startup statistics, explicit color/Unicode policies, and JSON diagnostics.
- Keep help, version, snapshots, and diagnostics usable without curses.
- Correct empty `NO_COLOR` handling; support scrolling in short help windows.
- Honor duration expiry even at low display rates.
- Bound catch-up/input work and remove duplicate cell-outline calculations.
- Add fake-terminal and generated resize/lifecycle tests, Ruff checks, benchmarks,
  biology references, terminal guidance, and a manual page.
- Pin release action commits and build tools; check byte-identical wheel rebuilds.


- A Python/curses microscope slide with macrophages, neutrophils, red blood
  cells, nine microbial types, fungal networks, and bacteriophages.
- Staged mitosis, phagocytosis, digestion, budding, longitudinal fission,
  organelle inheritance, and viral infection through lysis.
- Nutrient gathering, fungal highways, selective escape, and population-aware
  arrivals that enter gradually from outside the screen.
- Seeded simulation, pause and speed controls, three color themes, ASCII mode,
  screensaver mode, and headless snapshots.
- Python 3.10+ on Linux and macOS; Windows users can run through WSL.

- Add project URLs, cover all supported Python versions in CI, reject stale
  package builds, and verify archive checksums again before publishing.
