# Extension contract

Experiments can share the simulation without sharing artwork. The current
supported paths are listed below. During the 0.x series these interfaces may
still evolve; changes should be explicit in the changelog, preserve compatibility
where practical, and update their contributor examples and contract tests.

| Extension | Supported entry points | Ownership |
| --- | --- | --- |
| Simulation frontend | `World(...)`, `update(dt=STEP, events=True)`, `resize(columns, rows)`, `advance_events(seconds)` | Frontend owns clock, input, and terminal lifecycle |
| Presentation | `PresentationStyle`, `RenderOptions.resolve()`, `get_style()`, `STYLES` in `styles.py` | A trusted built-in style reads the world and returns a fresh `Frame` |
| Terminal drawing | `Frame`, `Pixel`, `Ink`, palettes in `frame.py` | Styles draw; `TerminalRenderer` handles output and color-pair fallback |
| Capabilities | `RenderCapabilities` in `capabilities.py` | Backend reports actual output support; style honors negotiated options |
| Membrane geometry | `Cell.outline(angle, now)`, `Cell.extent()`, `microbe_axes()`, `disc_axes()`, `cell_contains()` | Geometry stays consistent with collision boundaries |
| Collision queries | `World.obstacles()` and `World.is_blocked()` | Read-only queries in specimen coordinates; padding expands obstacles |
| Selection | `geometry.targets()`, `hit_test(world, col, row)`, `Target` | Shared foreground order and terminal-cell picking |
| Microbial defaults | `catalog.MICROBES`, frozen `MicrobeSpec` | Keyed biological defaults; styles own their art and ink mappings |
| Comparison fixtures | `scenes.SCENES`, `make_scene()` | Independent, staged developer worlds with real fixed-step updates |
| Contributor checks | `style_checks.check_style()` and `check_world_retention()` | Opt-in checks; never part of the animation loop |

World x/y positions use specimen coordinates. Terminal rows multiply by `ASPECT`
to get specimen y; frame dimensions are world width by world height / ASPECT.
`hit_test()` takes terminal columns and rows. `nuclear_bodies()`, `nuclear_mask()`,
and `nuclear_contains()` describe intact nuclear foreground; the mask/contains
functions use terminal raster coordinates. Mitotic structures have their own
lifecycle drawing and do not participate in captured-cargo picking.

`obstacles(x, y, padding=0, exempt=None, red=True, visitors=True)` yields
`(normal_x, normal_y, penetration)` for each intersected body. `exempt` is an
immune-cell ID. `is_blocked()` answers the same query as a boolean. These preserve
the existing radial collision approximation; they are not a general polygon
physics API. Selection follows food, hyphae, red cells, phages, free microbes,
immune cells, enclosed cargo, and visitors; intact nuclei cover enclosed cargo.

Read entity state and geometry to draw it. Mutations belong in simulation/tool
code and must respect membrane containment, exclusive capture ownership,
population limits, and seeded randomness. Existing underscored methods remain
implementation details; older `_obstacles` callers still work through a wrapper.
The compatibility exports in `terminal_cells` and `terminal_cells.render` remain
available, but new contributions should import the owning module shown here.

Styles expose `default_fill` and `palette(theme)` so the terminal and comparison
gallery use the same negotiated effects and semantic-color definitions. Each
palette has one (256-color, basic-color) pair per `Ink`, in enum order. Themes
remain `slide`, `amber`, `light`, and `mono` for either style.

Styles report every drawing cache through `cache_info()`, using
`CacheInfo(size, limit)`. Limits must be positive finite integers; styles without
caches return `{}`. Do not cache mutable World instances or return cached frames
that overlays can modify. Declaring these limits is testable cooperation, not
isolation from malicious Python code. Styles are explicitly registered trusted
code; the command line does not load arbitrary modules or plugins.

See [presentation styles](PRESENTATION_STYLES.md) for capability negotiation,
comparison commands, and the microscopy experiment references, and
[adding organisms](ADDING_ORGANISMS.md) for the catalog workflow. Fixtures are
repeatable within the current version; their layouts and sample times may evolve.
Neither serialized worlds nor saved cross-version replays are a supported format.
