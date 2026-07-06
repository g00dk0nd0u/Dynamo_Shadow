# Dynamo Shadow

Dynamo Shadow is a Dynamo/Revit diagnostic prototype for studying workflows related to Japanese Building Standard Law Article 56-2 shadow regulations.

This repository is for early-stage research and review. The current implementation is diagnostic-only: it does not perform formal shadow projection, equal-time contour generation, permit-ready calculation, or legal OK/NG judgement.

## Current diagnostics

The prototype currently focuses on input and readiness diagnostics, including:

- Selected shadow caster validation for user-defined Mass or Generic Model proxies.
- Optional site boundary input diagnostics, with Revit Property Line / Site Property as the intended primary source.
- Settings normalization for future Article 56-2 workflow inputs.
- Measurement-plane diagnostic checks using explicit settings, not Revit Level elevations.
- Read-only geometry and footprint-candidate diagnostics for selected proxy elements.
- Unit-conversion diagnostics that preserve Revit internal-unit values and add meter-based fields.
- Optional sanitized development debug logs.

## Intended Revit inputs

- `building_elements`: one or more selected Mass or Generic Model proxy elements used as shadow caster diagnostics.
- `site_boundary`: optional; intended to come from Revit Property Line / Site Property inputs when boundary-dependent diagnostics are needed.
- `settings`: optional for diagnostics, but future Article 56-2 calculation work requires explicit values such as average ground level, measurement height, latitude, longitude, and true north.

Existing Walls, Floors, Roofs, equipment, CAD imports, and topography-derived edges are not auto-used as shadow casters or site boundaries.

## Project structure

- `Shadow.dyn` is the Dynamo graph and contains the Python Node bootstrap.
- `dynamo_loader.py` resolves workspace paths, maps Dynamo `IN[]` values to named `INPUTS`, runs `script.py`, and returns diagnostics.
- `script.py` orchestrates imports, fallback behavior outside Dynamo, and top-level `OUT` construction.
- `shadow_*.py` modules contain focused policies, utilities, input diagnostics, settings normalization, measurement-plane diagnostics, geometry diagnostics, footprint diagnostics, unit conversion, debug logging, and readiness checks.
- `docs/` contains research notes, specifications, and implementation notes.

## Debug logs

Debug logging is disabled by default. Committed debug logs, when used for review, must stay under `debug_logs/`, remain small, and be sanitized. Logs must not contain local paths, usernames, email addresses, client or project names, personal cloud paths, raw Revit object representations, or large geometry payloads.

## Units

Revit geometry values are preserved as raw internal units, normally feet. Settings and Article 56-2 measurement-plane values are in meters and degrees unless a future specification changes them. Meter conversions are added with explicit `_m`, `_m2`, or `_m3` suffixes; raw fields are not silently replaced.

## Documentation

- Research notes: `docs/research_shadow_diagram.md`
- v0 specification: `docs/spec_v0.md`
- Revit input modeling guide: `docs/revit_input_modeling_guide.md`
- Settings schema: `docs/settings_schema_v1.md`
- Measurement plane notes: `docs/measurement_plane_v1.md`
- Geometry extraction notes: `docs/geometry_extraction_v1.md`
- Footprint extraction notes: `docs/footprint_extraction_v1.md`
- Debug logging notes: `docs/debug_logging_v1.md`
- Unit conversion notes: `docs/unit_conversion_v1.md`
- Contributor and agent rules: `AGENTS.md`

## Scope warning

This repository must not be used as a complete building permit calculation tool. Formal code checks, permit submissions, and regulatory decisions require validated professional tools and confirmation against applicable laws, ordinances, and reviewing authority requirements.
