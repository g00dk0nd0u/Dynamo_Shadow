# Dynamo Shadow

Dynamo Shadow is a Dynamo/Revit diagnostic prototype for studying workflows related to Japanese Building Standard Law Article 56-2 shadow regulations.

This repository is for early-stage research and review. The current pipeline implements prototypes for formal per-solid, per-time-slice shadow polygons, Revit-native union once per time slice, grid/trapezoidal shadow-duration accumulation v1, and pure-Python equal-time contours v1. The formal polygon scope remains limited to extrusion-like solids and Line-loop serialization, and actual model validation in Revit 2024.3 remains required. Formal closed site-boundary extraction, 5 m/10 m measurement lines, road/water/elevation-difference relaxations, and legal judgement remain unimplemented. These prototypes are not legal or permit-ready output, and `permit_ready_certified` remains `false`.

## Current diagnostics

The prototype currently focuses on input and readiness diagnostics, including:

- Selected shadow caster validation for user-defined Mass or Generic Model proxies.
- Optional site boundary input diagnostics, with Revit Property Line / Site Property as the intended primary source.
- Settings normalization for future Article 56-2 workflow inputs.
- Measurement-plane diagnostic checks using explicit settings, not Revit Level elevations.
- Read-only geometry and footprint-candidate diagnostics for selected proxy elements.
- Unit-conversion diagnostics that preserve Revit internal-unit values and add meter-based fields.
- Optional sanitized development debug logs.
- Revit-native per-time-slice union through temporary in-memory extrusion solids; no model elements or transactions are used.
- Optional downstream DirectShape Curve preview of unioned outer and inner boundaries at one measurement-plane Z.

## Preview settings

Preview is visualization-only. The policy default is `preview_mode="off"`; the current `Shadow.dyn` initial setting is `preview_mode="replace"`. The settings JSON input accepts, for example:

```json
{"preview_mode": "off"}
```

```json
{
  "preview_mode": "replace"
}
```

```json
{"preview_mode": "clear"}
```

`replace` removes only prior `Dynamo_Shadow.FormalShadowPreview` DirectShapes before creating one Curve-only DirectShape for each exact hourly profile slice (08:00 through 16:00 for `standard_8_16`). It uses the unioned slice boundaries, so overlaps and internal lines between casters are not displayed. The default representation remains visible as lines in 3D; the Plan representation is also set when the runtime supports it. Projection-line colour and weight are the only graphical overrides. `clear` removes those owned previews without creating replacements.

## Intended Revit inputs

- `building_elements`: one or more selected Mass or Generic Model proxy elements used as shadow caster diagnostics.
- `site_boundary`: optional; intended to come from Revit Property Line / Site Property inputs when boundary-dependent diagnostics are needed.
- `settings`: optional for diagnostics, but future Article 56-2 calculation work requires explicit values such as average ground level, measurement height, latitude, longitude, and true north.

In Dynamo Player, the regulatory shadow preset, calculation accuracy, site latitude, and site longitude are
separate inputs; the retained settings JSON is internal and hidden. The accuracy choices are rough
(0.5 m / 30 minutes), standard (0.5 m / 15 minutes, default), and high (0.25 m / 15 minutes). Player values take
priority over settings JSON, which takes priority over Python diagnostic defaults. The
preset only makes candidate values appearing in Appended Table 4 easier to select; the
actually applicable classification must be confirmed in the relevant municipal ordinance.
`standard_all` is the initial QA display intended for areas such as Tokyo, Osaka, Kyoto,
and Kyushu. The Hokkaido-area choices use 09:00–15:00 and include the 1.5-hour candidate.
Six-hour contours are intentionally excluded from statutory-time presets, while the
technical ability to generate explicitly requested 360–480 minute contours remains.
Longitude does not directly change results in true-solar-time mode.

Existing Walls, Floors, Roofs, equipment, CAD imports, and topography-derived edges are not auto-used as shadow casters or site boundaries.

## Project structure

- `Shadow.dyn` is the Dynamo graph and contains the Python Node bootstrap.
- `dynamo_loader.py` resolves workspace paths, maps Dynamo `IN[]` values to named `INPUTS`, runs `script.py`, and returns diagnostics.
- `script.py` orchestrates imports, fallback behavior outside Dynamo, and top-level `OUT` construction.
- `shadow_duration.py` performs grid sampling and trapezoidal duration accumulation v1.
- `shadow_accuracy_presets.py` resolves the three Player accuracy presets without changing legacy pure-Python defaults.
- `shadow_contours.py` generates deterministic equal-time polylines with Marching Squares and linear edge interpolation.
- `shadow_contour_preview.py` creates and manages the optional equal-time contour DirectShape preview.
- `tests/fixtures/debug_logs/` contains fixed, sanitized samples used by the privacy check; runtime output under `debug_logs/` remains ignored.
- Other `shadow_*.py` modules contain focused policies, utilities, input diagnostics, settings normalization, measurement-plane diagnostics, geometry diagnostics, footprint diagnostics, formal projection and union adapters, unit conversion, debug logging, and readiness checks.
- `docs/` groups user guidance, runtime notes, specifications, and development notes by role.
- `tests/` groups unit, integration, and contract suites; fixed test data remains under `tests/fixtures/`.

## Debug logs

Debug logging is disabled by default. Runtime files are written under the ignored `debug_logs/` directory and must not be committed. Fixed samples needed by tests or repository checks belong under `tests/fixtures/debug_logs/`, must remain small and sanitized, and must not contain local paths, usernames, email addresses, client or project names, personal cloud paths, raw Revit object representations, or large geometry payloads.

## Units

Revit geometry values are preserved as raw internal units, normally feet. Settings and Article 56-2 measurement-plane values are in meters and degrees unless a future specification changes them. Meter conversions are added with explicit `_m`, `_m2`, or `_m3` suffixes; raw fields are not silently replaced.

## Documentation

- Research notes: `docs/development/research_shadow_diagram.md`
- v0 specification: `docs/development/spec_v0.md`
- Revit input modeling guide: `docs/user/revit_input_modeling_guide.md`
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

Complete `unified_shadow_slices` can be sampled on a bounded meter grid and integrated between adjacent slices with the trapezoidal rule. Outer/inner loops and multiple components are supported, and `max_duration_grid_points` stops oversized grids before allocation. The result remains a numerical approximation at the configured temporal step (normally 30 minutes), works without a site boundary, and is not permit-certified; site-boundary-dependent legal judgement remains blocked.


## Equal-time contours v1

`shadow_contours.py` reconstructs the row-major duration grid from `grid_spec`, resolves ambiguous Marching Squares cases deterministically from the cell mean, removes duplicate or zero-length segments, and joins segments into ordered open or closed polylines. Explicit `equal_time_contour_levels_minutes` take priority; otherwise levels use `equal_time_contour_interval_minutes=60`. `max_equal_time_contour_levels=100` bounds output work. These are technical/diagnostic levels, not statutory thresholds, and legal judgement remains unimplemented.
