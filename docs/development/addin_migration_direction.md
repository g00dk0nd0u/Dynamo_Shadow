# Add-in migration direction

This note records the current architecture direction after the PR #78 mainline state. It is documentation only: no C# migration, runtime behavior change, schema freeze, Golden fixture work, installer work, licensing work, or product repository split is started here.

## Current role of the Dynamo/Python version

The current Dynamo/Python implementation is the reference implementation for research, review, and Revit-runtime verification of equal-time shadow workflows. Dynamo is the current validation host; it is not yet designated as the final product host.

The current implementation already covers forward-shadow calculation prototypes including Revit geometry extraction, formal time-slice projection, per-time-slice union, duration accumulation, equal-time contours, placed-Area site boundary extraction, site distance masks, 5 m / 10 m contour data, selected limit comparison, and preview of equal-time contours. It is still not permit-certified, and `permit_ready_certified` remains `false`.

## Three-layer direction

### Revit Adapter

The Revit Adapter layer owns Revit-specific work:

- reading selected Mass / Generic Model shadow casters;
- reading exactly one placed Revit Area for the formal site boundary;
- preserving native `Autodesk.Revit.DB.Solid`, `Face`, `Curve`, `CurveLoop`, `Plane`, and `XYZ` where practical;
- formal shadow projection;
- Revit-native Boolean / union processing;
- Revit preview and future Revit write operations;
- Revit internal-unit conversion.

This layer is the only place that should depend on `Autodesk.Revit.DB`.

### Shadow Core

The Shadow Core layer owns calculation logic after Revit data has been converted to canonical, JSON-safe calculation data:

- meter-based site and shadow geometry;
- solar calculation;
- true-solar-time-aware time slices;
- duration accumulation;
- equal-time contour generation;
- site geometry validation;
- distance masks;
- fixed 5 m / 10 m distance contour data;
- selected regulatory limit comparison;
- future reverse-shadow algorithms.

Shadow Core must not import `Autodesk.Revit.DB`, must not hold raw Revit objects, and must not operate on Revit internal units. After the Revit Adapter passes data to Core, the canonical units are meters, degrees, and minutes.

### Dynamo Host

The Dynamo Host layer owns the current execution host:

- `Shadow.dyn`;
- `dynamo_loader.py`;
- `IN[]` / `INPUTS` mapping;
- Dynamo Player inputs;
- `script.py` orchestration;
- top-level `OUT` inspection.

`script.py` is currently the orchestrator. It should remain focused on input orchestration, calls to focused modules, failure handling, and `OUT` construction rather than becoming a calculation module.

## Current module classification

Current Revit Adapter candidates include:

- `shadow_revit_api.py`
- `shadow_geometry.py`
- `shadow_footprint.py`
- `shadow_formal_projection.py`
- `shadow_union.py`
- `shadow_site_area_adapter.py`
- `shadow_preview.py`
- `shadow_contour_preview.py`
- Revit-facing parts of `shadow_units.py`

Current Shadow Core candidates include:

- `shadow_sun.py`
- `shadow_projection.py`
- `shadow_duration.py`
- `shadow_contours.py`
- `shadow_site_geometry.py`
- `shadow_site_masks.py`
- `shadow_site_distance_contours.py`
- `shadow_regulatory_presets.py`
- `shadow_regulatory_comparison.py`
- `shadow_accuracy_presets.py`
- JSON-safe policy, settings, readiness, debug, and utility helpers that do not require Revit API imports

Current Dynamo Host files include:

- `Shadow.dyn`
- `dynamo_loader.py`
- `script.py`

This classification is a migration aid, not a code ownership lock. The important boundary is that Revit API objects and internal units stop at the adapter boundary, while Shadow Core remains portable and meter-based.

## Revit API boundary

The Revit API boundary should be explicit and testable:

- Do not add `Autodesk.Revit.DB` imports to Shadow Core modules.
- Do not pass raw Revit objects into `OUT` or debug JSON.
- Convert Revit internal units before Core calculations.
- Preserve native Revit geometry inside Adapter paths where that improves correctness and Revit 2024.3 compatibility.
- Keep optional Revit imports isolated so normal Python `py_compile` and pure-Python tests run outside Revit.

## Canonical boundary candidate

The current likely canonical calculation-data boundary is at or just after `unified_shadow_slices`.

That boundary is attractive because it is after formal Revit projection and per-time-slice union, while before Shadow Core duration accumulation, contouring, distance masking, comparison, and future reverse-shadow work. It may become the handoff point from a future C# Revit Adapter to a C# Shadow Core, but the final contract should not be frozen yet.

## Why C# migration is not starting now

C# migration is intentionally deferred because the current Revit-runtime behavior and final output contracts are not stable enough to freeze. Starting a C# solution now would risk duplicating unstable Python behavior, locking premature DTO/schema choices, and creating Golden tests before validated examples are available.

The Python/Dynamo version should remain the reference implementation while forward-shadow behavior, display behavior, external comparisons, reverse-shadow requirements, and fixture strategy are still being finalized.

## Conditions to start C# migration

Begin C# migration only after all of the following are true:

1. Forward-shadow behavior is stable in live Revit testing.
2. Revit display for 5 m / 10 m contours is stable.
3. Revit display for exceedance or maximum-shadow points is stable.
4. Comparison results against external specialist software are finalized.
5. Reverse-shadow input and output specifications are finalized.
6. Real examples suitable for fixed Golden fixtures are available.

## Future target shape

A future add-in direction may become:

```text
C# Revit Adapter
  -> canonical calculation data
  -> C# Shadow Core
  -> Revit UI / output
```

At this stage, that is only a recorded design direction. This repository should not add a C# solution, DTO/schema package, product UI, installer, licensing code, report schema, reverse-shadow implementation, or Golden fixture framework until the prerequisites above are satisfied.

## Deferred issue and contract work

Issue status audit is intentionally deferred. Issues will be reviewed separately after documentation sync.

The following are also intentionally deferred because Revit実機 results and final output specifications are not yet settled:

- `core_data_contracts_v1.md`;
- schema-name or schema-version additions across `OUT`;
- dataclasses, `TypedDict`, or JSON Schema;
- contract fixtures or Golden fixtures;
- Golden output tests;
- floating-point canonicalization framework;
- unit-layer module splits;
- `script.py` splitting;
- legal profile schema;
- report schema.
