# Changelog

## Unreleased

- Keep endothelial borders, junctions, nuclei, and selection aligned on the
  terminal grid so curved vessel walls retain a consistent cell thickness.
- Let free phages, released capsids, and rupture fragments follow ambient flow;
  retain host-bound attachments and anchored tissue structures.

- Add an opt-in vessel scene with endothelial walls and staged neutrophil rolling,
  adhesion, and junction crossing (#45).
- Add platelet activation, spreading, local fibrin plugs, and bounded resolution
  in the vessel scene (#46).
- Add tissue-side fibroblasts, temporary matrix deposition, and recurring wound
  repair, with shared presentation state, interactive tools, and staged previews (#50).

- Recover obstructed edge arrivals with local navigation and offscreen retries;
  allow bodies in clear fluid to resume normal behavior before a blocked staging point.
- Let duplicate immune cells depart through an edge so missing immune types can
  return without increasing population caps or removing division animations.
- Fix budding footprint accounting, projected fungal picking and Tab selection,
  offscreen destructive selections, and simulation slowdown at low drawing FPS.
- Show compact tool/Inspect feedback on the single footer line and keep style
  legends consistent with capability fallbacks.
- Extend endurance checks to lifecycle progress, diversity, multiple seeds,
  fixed compact slides, overview, and raster detail. Make coverage paths portable.
- Validate release preparation before editing version files, regenerate the
  manual with each version, and check manual freshness in CI and distributions.

## 0.2.0 — 2026-11-24

- Add `--magnification overview|normal|detail` and H/J/K/L panning for wider
  views and bacterial close-ups. Rendering and interactive tools share the same
  camera projection without changing biological sizes or simulation rules (#30).
- Reduce crowding with footprint-aware population limits, initial placement,
  growth, and soft avoidance. Flagella shorten near neighbors; new arrivals
  continue to enter through the edges when space is tight (#23).
- Add complement coating, enhanced immune recognition, and selective bacterial
  pore formation and lysis, with Inspect/observation feedback. Disable this
  illustrative behavior with `--no-complement` (#51).
- Add experimental `--style stained` and `--style raster` presentations. Stained
  fills cell bodies behind the familiar glyphs; raster shades the whole specimen
  on a light slide and can reduce frame rates. Classic remains the default,
  provides limited-terminal fallbacks, and supports optional `--fill` tinting.
- Establish presentation-style and contributor extension interfaces, shared
  geometry and foreground selection, capability negotiation, a keyed microbial
  catalog, and checks for rendering purity, fallbacks, and bounded caches.
- Add staged style-comparison scenes, a repeatable blood smear, SVG galleries,
  and ASCII/Unicode previews. Include shiwng’s seeded half-block/line-art
  comparison as a contributor preview without changing runtime rendering.
- Improve light-theme particle contrast, document pipx/PATH troubleshooting and
  terminal compatibility reports, fix the cbonsai link, and harden terminal-test
  startup and mouse-protocol portability.
- Update pinned development tools and GitHub security actions.

## 0.1.3 — 2026-11-18

- Add subtle near/far contrast to existing background particles, using stable
  size cues and single-character marks without increasing particle counts.
- Complete GitHub release creation after successful production promotion.
- Avoid a startup race in the SIGTERM terminal-cleanup test on slower runners.

## 0.1.2 — 2026-11-17

- Improve terminal readability with thinner curved outlines, quieter cell
  interiors, simpler organelles and shorter flagella in compact windows, lower
  default microbe/debris populations, and more space between immune cells.
- Simplify the README, add a command reference and organism contribution guide,
  ease bug reporting, and refresh installation and maintainer documentation.

## 0.1.1 — 2026-11-17

- Refresh development tools and release provenance, clarify published installation
  options, and add a real terminal recording and Homebrew formula preparation.

- Harden archive validation and malformed mouse-event handling, add security
  scanning, dependency audits, broader generated tests, coverage, and nightly
  endurance checks.
- Generate release manifests and distro versions, promote tested artifacts
  unchanged, prepare reviewable release patches, and assemble complete releases
  with provenance before immutable publication.
- Document security reporting, production approval, PPA preparation, and recovery.

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
