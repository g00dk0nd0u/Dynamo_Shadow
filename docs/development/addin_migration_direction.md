# Add-in migration direction

This note records the architecture direction for incremental product development. Product infrastructure and gradual C# semantic porting may now begin, but this does not change the current Python runtime, freeze its schemas, or claim that a distributable product exists.

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

- `runtime/Shadow.dyn`;
- `runtime/dynamo_loader.py`;
- `IN[]` / `INPUTS` mapping;
- Dynamo Player inputs;
- `runtime/script.py` orchestration;
- top-level `OUT` inspection.

`runtime/script.py` is currently the orchestrator. It should remain focused on input orchestration, calls to focused modules, failure handling, and `OUT` construction rather than becoming a calculation module.

## Current module classification

Current Revit Adapter candidates include:

- `runtime/shadow_revit_api.py`
- `runtime/shadow_geometry.py`
- `runtime/shadow_footprint.py`
- `runtime/shadow_formal_projection.py`
- `runtime/shadow_union.py`
- `runtime/shadow_site_area_adapter.py`
- `runtime/shadow_preview.py`
- `runtime/shadow_contour_preview.py`
- Revit-facing parts of `runtime/shadow_units.py`

Current Shadow Core candidates include:

- `runtime/shadow_sun.py`
- `runtime/shadow_projection.py`
- `runtime/shadow_duration.py`
- `runtime/shadow_contours.py`
- `runtime/shadow_site_geometry.py`
- `runtime/shadow_site_masks.py`
- `runtime/shadow_site_distance_contours.py`
- `runtime/shadow_regulatory_presets.py`
- `runtime/shadow_regulatory_comparison.py`
- `runtime/shadow_accuracy_presets.py`
- JSON-safe policy, settings, readiness, debug, and utility helpers that do not require Revit API imports

Current Dynamo Host files include:

- `runtime/Shadow.dyn`
- `runtime/dynamo_loader.py`
- `runtime/script.py`

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

## Incremental C# migration is now approved

The Dynamo/Python implementation remains the behavioral source of truth. C# work must follow it module by module: change and test Python first, port the corresponding behavior, then run C# and representative Python/C# parity tests. Python must not be changed merely to make a C# port easier, and releases must stop when parity is known to be broken.

Initial work should establish portable `ShadowCore` build/test infrastructure and product boundaries rather than bulk-translating `runtime/shadow_*.py`. Portable, JSON-safe calculation modules are candidates for gradual semantic ports; Revit API code remains isolated in the Revit Adapter. The current module classification above remains the starting point rather than a requirement to map every Python module into C#.

The compiled-product support target begins at Revit 2025. Revit 2025/2026 host builds use .NET 8, while Revit 2027 host builds use .NET 10. One portable `netstandard2.0` `ShadowCore` assembly remains shared, but Revit and Dynamo host binaries may require framework- and Revit-version-specific builds and tests. Exact Autodesk API references are deferred until real host implementation; the final adapter/host assembly decomposition remains unfrozen. Python is canonical for portable calculation behavior and contracts, not necessarily for obsolete Revit 2024-specific host workarounds. The existing Python reference environment remains Revit 2024.3.

## Readiness gates for broader migration

The following remain gates for broad migration and product claims, not blockers to focused infrastructure or small semantic ports:

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

The repository may now contain the C# solution and projects needed to develop that shape incrementally. A future compiled Dynamo Package and Revit add-in remain separate product artifacts from `runtime/Shadow.dyn`; neither is currently distributable. Product UI, installer, licensing, report schemas, bulk reverse-shadow migration, and premature contract freezes remain deferred.

Formal legal judgement and permit certification are not implemented. `permit_ready_certified` must remain `false` until a separate certification workflow is explicitly implemented.

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
- `runtime/script.py` splitting;
- legal profile schema;
- report schema.
