# Dynamo Shadow

Dynamo Shadow is a Dynamo/Revit diagnostic prototype for studying workflows related to Japanese Building Standard Law Article 56-2 shadow regulations.

This repository is for research and review. The current Dynamo/Python implementation is a reference prototype, not a permit-ready product, not a released Revit add-in, and not a finalized C# migration target. `permit_ready_certified` remains `false`.

## Current implementation status

Implemented prototype capabilities include:

- Multiple selected Mass / Generic Model shadow caster proxies.
- Revit geometry extraction and footprint extraction prototype.
- NOAA solar calculation with true solar time.
- Automatic True North orientation from the active Revit Project Location.
- Formal time-slice shadow projection.
- Per-time-slice Revit-native union.
- Grid/trapezoidal shadow-duration accumulation.
- Equal-time contour generation and equal-time contour DirectShape preview.
- Site boundary extraction from exactly one placed Revit Area.
- Validation for a single outer site-boundary loop with no holes and straight segments only.
- Site distance masks for within 5 m, beyond 5 m through 10 m, and beyond 10 m.
- Near/far maximum shadow duration and maximum point outputs.
- Fixed 5 m / 10 m signed-distance contour polyline data.
- Revit DirectShape preview for fixed 5 m / 10 m contours.
- Revit X-marker preview for near/far maximum-duration points.
- Numeric comparison against the selected regulatory preset.
- Forward Fast / Standard / High Dynamo Player accuracy selection.
- Pure-Python regression tests.
- Low-rise reverse-shadow core and Revit tessellated preview, accessible from the same Dynamo Player graph as forward shadow. The coarse candidate volume still requires final forward equal-time shadow validation.

Not implemented:

- Selected-limit exceedance styling for preview graphics.
- Formal legal pass/fail judgement.
- Automatic municipal ordinance selection.
- Road, water, elevation-difference, or similar relaxations.
- Verification report output.
- C# Revit add-in.
- Product UI.
- Installer.
- Permit certification.

## Dynamo inputs

The single `Shadow.dyn` graph exposes eight Dynamo Player inputs:

1. `Site Boundary Area / 敷地境界エリア`
2. `Building Model / 建物モデル`
3. `Shadow Limits / 日影規制時間`
4. `Average Ground Level / 平均地盤面`
5. `Calculation Accuracy / 計算精度`
6. `Analysis Mode / 解析モード`
7. `Site Latitude / 緯度`
8. `Site Longitude / 経度`

The Python Node has nine ports, `IN[0]` through `IN[8]`, because it also receives an internal settings input. `IN[0]` through `IN[7]` retain their existing meanings; Analysis Mode is append-only at `IN[8]`. Missing mode values default to Forward for legacy compatibility.

Forward and Reverse use the selected Average Ground Level's Revit Level Elevation as their common AGL source after conversion from internal units to meters. The measurement plane remains AGL plus the preset measurement height; the Level itself is not the measurement plane. Settings AGL is used only when no Level is selected. Reverse continues to ignore Building Model, requires a valid Site Boundary and a specific near/far Shadow Limits pair. Reverse Fast uses a 4 m height grid / 4 m measurement spacing / 30-minute step; Reverse Standard uses a 1 m height grid / 1 m measurement spacing / 15-minute step. Reverse High currently retains the same accuracy as Reverse Standard. Reverse height limits use a conservative 0.5 m vertical floor.

## Intended Revit inputs

- `building_elements`: one or more selected Mass or Generic Model proxy elements used as shadow casters.
- `site_boundary`: optional for core shadow duration and equal-time contours; the formal boundary-dependent input is exactly one placed Revit Area selected once in Dynamo Player.
- `level`: the selected Revit Level at the average ground position, shared by Forward and Reverse as the authoritative AGL elevation source.
- `settings`: optional for diagnostics and internal compatibility. Explicit values or selected presets are required for legal-calculation parameters such as average ground level, measurement height, latitude, and longitude. In Revit, True North is read automatically from the active Project Location; no Player angle input is provided.

Project North is the model's drawing orientation, while True North is geographic north. Dynamo_Shadow uses True North for both Forward and Reverse shadow directions. Users must set Revit's True North correctly before running the graph; the adapter reads the setting without creating or modifying Project Locations. Latitude and longitude remain the existing Player inputs.

Users select the placed Area body for `site_boundary`, not Area Boundary lines, Area Tags, Property Line segments, Model Lines, Detail Lines, Filled Regions, Floors, Generic Models, CAD imports, Toposolids, or families. Property Line / Site Property inputs are not the current formal site-boundary input.

Existing Walls, Floors, Roofs, equipment, CAD imports, and topography-derived edges are not auto-used as shadow casters or site boundaries.

## Accuracy and regulatory presets

In Dynamo Player, the regulatory shadow preset, calculation accuracy, site latitude, and site longitude are separate inputs; the retained settings JSON is internal and hidden. Forward Fast uses 1.0 m / 30 minutes for rapid initial iteration, Standard uses 0.5 m / 15 minutes for normal design and remains the default, and High uses 0.25 m / 5 minutes for a final high-precision check with increased runtime. Fast is coarse and is not intended for final high-precision review. High does not imply permit certification; `permit_ready_certified` remains `false`.

Player values take priority over settings JSON, which takes priority over Python diagnostic defaults. Regulatory presets only expose candidate values appearing in Appended Table 4; the actually applicable classification must be confirmed against the relevant municipal ordinance. `standard_all` is the initial QA display intended for areas such as Tokyo, Osaka, Kyoto, and Kyushu. Hokkaido-area choices use 09:00–15:00 and include the 1.5-hour candidate. Six-hour contours are intentionally excluded from statutory-time presets, while the technical ability to generate explicitly requested 360–480 minute contours remains. Longitude does not directly change results in true-solar-time mode.

## Preview settings

Preview is visualization-only. The policy default is `preview_mode="off"`; the current `runtime/Shadow.dyn` initial setting is `preview_mode="replace"`. The settings JSON input accepts, for example:

```json
{"preview_mode": "off"}
```

```json
{"preview_mode": "replace"}
```

```json
{"preview_mode": "clear"}
```

`replace` removes prior Dynamo Shadow preview DirectShapes before creating preview geometry. Equal-time contour DirectShape preview is implemented. Site result preview reuses `equal_time_contour_preview_mode` to display fixed 5 m / 10 m DirectShape Curve contours and near/far maximum-point X markers. Preview colors are visual distinctions only and do not indicate legal pass/fail. `clear` removes owned previews without creating replacements.

## Architecture direction

Future development should keep three boundaries clear:

- **Revit Adapter**: reads Revit elements and placed Areas, preserves native Revit geometry where needed, performs formal Revit shadow projection and Revit-native Boolean / union work, owns Revit preview/write behavior, and converts Revit internal units.
- **Shadow Core**: works on meter-based JSON-safe data, performs solar calculation, duration accumulation, equal-time contours, site geometry validation, distance masks, 5 m / 10 m distance contour data, selected limit comparison, and future reverse-shadow algorithms. Shadow Core must not import `Autodesk.Revit.DB` or operate on Revit internal units.
- **Dynamo Host**: consists of `runtime/Shadow.dyn`, `runtime/dynamo_loader.py`, Player inputs, `IN[]` / `INPUTS` mapping, `runtime/script.py` orchestration, and `OUT` inspection.

A future C# Revit add-in is a development direction, not current product scope. The Python/Dynamo implementation should remain the reference implementation until Revit runtime behavior, display outputs, external software comparisons, reverse-shadow specifications, and fixed Golden fixtures are stable enough to justify migration.

## Project structure

- `runtime/` is both the source of truth for development and the complete, directly distributable Dynamo/Revit runtime bundle. No separate `dist` copy is maintained.
- `runtime/Shadow.dyn` is the Dynamo Player graph and contains the Python Node bootstrap.
- `runtime/dynamo_loader.py` is the same-folder loader that maps Dynamo `IN[]` values to named `INPUTS` and runs `runtime/script.py`.
- `runtime/script.py` is the orchestration entry for imports, fallback behavior outside Dynamo, and top-level `OUT` construction.
- `runtime/shadow_*.py` contains the Revit Adapter, Shadow Core, and supporting runtime modules.
- `tests/` contains development-only unit, integration, and contract tests; fixed test data remains under `tests/fixtures/`.
- `tools/` contains development-only repository checks and is not part of the runtime distribution.
- `docs/` contains user guidance, runtime QA notes, specifications, and development notes under their corresponding subdirectories.

To run the graph, open `runtime/Shadow.dyn` with Dynamo Player. The `runtime/` directory alone may be copied for distribution and renamed after copying; keep `Shadow.dyn`, the loader, the script, and every local module together in that one directory. Future forward-shadow and reverse-shadow workflows should share this runtime bundle and common modules rather than creating duplicate distributions.

## Debug logs

Debug logging is disabled by default. Runtime files are written to `debug_logs/latest_debug.json` inside the copied `runtime/` bundle (relative to `Shadow.dyn`, not the process working directory) and must not be committed. The repository-root `debug_logs/` directory is not a runtime output location. Fixed samples needed by tests or repository checks belong under `tests/fixtures/debug_logs/`, must remain small and sanitized, and must not contain local paths, usernames, email addresses, client or project names, personal cloud paths, raw Revit object representations, or large geometry payloads.

## Units

Revit geometry values are preserved as raw internal units, normally feet, inside Revit Adapter diagnostics. Settings and Article 56-2 measurement-plane values are in meters and degrees unless a future specification changes them. Meter conversions are added with explicit `_m`, `_m2`, or `_m3` suffixes; raw fields are not silently replaced. After the adapter-to-core boundary, calculation data should use meters, degrees, and minutes.

## Tests

At the latest confirmed main for this documentation sync, the repository-wide pure-Python test suite had 367 passing tests. This count is a confirmation snapshot, not a permanent specification.

## Documentation

- Architecture and add-in migration direction: `docs/development/addin_migration_direction.md`
- Research notes: `docs/development/research_shadow_diagram.md`
- v0 specification: `docs/development/spec_v0.md`
- Revit input modeling guide: `docs/user/revit_input_modeling_guide.md`
- Site boundary Area setup: `docs/user/site_boundary_area_setup.md`
- Settings schema: `docs/specifications/settings_schema_v1.md`
- Measurement plane notes: `docs/specifications/measurement_plane_v1.md`
- Geometry extraction notes: `docs/development/geometry_extraction_v1.md`
- Footprint extraction notes: `docs/specifications/footprint_extraction_v1.md`
- Debug logging notes: `docs/runtime/debug_logging_v1.md`
- Unit conversion notes: `docs/specifications/unit_conversion_v1.md`
- Contributor and agent rules: `AGENTS.md`

## Scope warning

This repository must not be used as a complete building permit calculation tool. Formal code checks, permit submissions, and regulatory decisions require validated professional tools and confirmation against applicable laws, ordinances, and reviewing authority requirements.

## Direction verification status

The serialized formal-slice contract distinguishes the downward `physical_shadow_ray_model` from the reversed `extrusion_analyzer_input_direction` required to analyze an extrusion from the measurement plane toward the caster. Pure-Python checks cover the 08:00 northwest, 12:00 north, and 16:00 northeast reference directions, true-north rotation, opposite-sign rejection, and the analytical `height * shadow_length_factor` projection length. Revit runtime verification additionally compares clipped-Solid edge endpoint projections with the extracted polygon extents; both direction and extent checks must pass. Active-view up direction is diagnostic only and must not be confused with calculated true north.

The required Revit runtime check uses true north 0 degrees, a simple box above a 4 m measurement plane, and confirms: noon extends toward model +Y; 08:00/16:00 extend symmetrically northwest/northeast; all nine hourly lines appear in plan; and no 3D thickness exists. This prototype remains `permit_ready_certified=false`.

## Shadow duration accumulation v1

Complete `unified_shadow_slices` can be sampled on a bounded meter grid and integrated between adjacent slices with the trapezoidal rule. Outer/inner loops and multiple components are supported, and `max_duration_grid_points` stops oversized grids before allocation. The result remains a numerical approximation at the configured temporal step, works without a site boundary, and is not permit-certified.

## Equal-time contours v1

`runtime/shadow_contours.py` reconstructs the row-major duration grid from `grid_spec`, resolves ambiguous Marching Squares cases deterministically from the cell mean, removes duplicate or zero-length segments, and joins segments into ordered open or closed polylines. Explicit `equal_time_contour_levels_minutes` take priority; otherwise levels use `equal_time_contour_interval_minutes=60`. `max_equal_time_contour_levels=100` bounds output work. These are technical/diagnostic levels, not statutory thresholds, and legal judgement remains unimplemented.
