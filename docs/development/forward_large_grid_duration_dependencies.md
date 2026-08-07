# Forward Large Grid duration-grid dependency investigation

## Scope

This note records the current `duration_grid` dependencies and identifies a safe
boundary for a future memory-efficient Forward Shadow Large Grid path. It does
not propose NumPy, parallel processing, a 0.1 m preset, or a calculation
algorithm change. The existing Small Grid, Fast, and Standard behavior remains
the compatibility baseline.

## Dependency map

```text
unified_shadow_slices
  -> shadow_duration.build_shadow_duration
       -> shadow_duration.duration_grid (also exposed in top-level OUT)
            -> shadow_contours.build_equal_time_contours
            -> shadow_site_masks.build_measurement_masks
            -> shadow_site_distance_contours.build_site_distance_contours
       -> measurement_masks
            -> shadow_regulatory_comparison.build_selected_limit_comparison
            -> shadow_site_result_preview (near/far maximum markers)
       -> equal_time_contours
            -> equal-time contour preview
       -> shadow_debug (summary fields only; not the full grid)
```

Direct production references to the `duration_grid` key are limited to
`shadow_duration.py`, `shadow_contours.py`, `shadow_site_masks.py`, and
`shadow_site_distance_contours.py`, plus policy/settings declarations. The
Dynamo host passes the complete `shadow_duration` result to those consumers and
places it in `OUT`.

Direct regression-test consumers are:

- `tests/unit/test_shadow_duration_v1.py`
- `tests/unit/test_equal_time_contours_v1.py`
- `tests/unit/test_site_area_geometry_masks.py`
- `tests/unit/test_site_distance_contours.py`
- `tests/integration/test_site_result_preview.py`

## Small Grid compatibility contract

The existing materialized Small Grid contract must remain unchanged:

- `method` is `grid_trapezoidal_time_integration_v1`.
- `duration_grid` is a list of dictionaries containing `x_m`, `y_m`, and
  `shadow_duration_minutes`.
- Points use `row_major_y_then_x` ordering.
- `len(duration_grid) == grid_spec.x_count * grid_spec.y_count`.
- `grid_spec` retains `x_count`, `y_count`, `origin_x_m`, `origin_y_m`,
  `resolution_m`, and `ordering`.
- `available`, `complete`, point counts, bounds metadata, maximum duration,
  shadowed-point count, readiness, coverage, blockers, warnings, and
  `permit_ready_certified: false` retain their current meanings.
- A core-grid limit failure retains an empty `duration_grid` and the
  `max_duration_grid_points_exceeded` blocker.
- A boundary-expanded-grid limit failure may preserve a complete core result,
  but keeps `boundary_evaluation_coverage_complete: false` and blocks
  boundary-dependent consumers.
- No automatic accuracy fallback is introduced.

This is also an external compatibility surface because the complete
`shadow_duration` dictionary is exposed in top-level Dynamo `OUT`.

## Coordinate reconstruction

Grid coordinates can be reconstructed exactly from `grid_spec` and a row-major
index:

```text
x = origin_x_m + (index % x_count) * resolution_m
y = origin_y_m + (index // x_count) * resolution_m
```

Equal-time contour generation already reconstructs coordinates this way and
reads only `shadow_duration_minutes` from each duration-grid item. A Large Grid
internal representation therefore does not need to allocate an `x_m` and `y_m`
dictionary entry for every point. Small Grid must continue emitting them.

## Consumer requirements

### Streaming consumers

**Measurement masks** are naturally one-pass. Each point is validated,
classified against the site polygon, counted, and considered for the near/far
maximum with deterministic coordinate tie-breaking. No neighboring or previous
grid value is required.

**Regulatory comparison** does not consume the full grid. It needs the
aggregated near/far maxima and points, plus duration completion, boundary
coverage, method, spatial resolution, and temporal step metadata.

**Debug output** consumes summary fields only. It does not serialize or inspect
the full duration grid.

**Preview** does not directly consume the duration grid. Site-result preview
uses the aggregated mask maxima, and equal-time preview uses generated contour
polylines.

**Site-distance contours** can use two grid rows. Signed distance depends only
on the site polygon and the coordinate reconstructed from `grid_spec`; it does
not depend on shadow duration. The current full `points` and `signed_values`
lists are implementation details rather than a true data requirement.

### Consumers that currently materialize a full scalar field

**Equal-time contours** currently copy all duration values and repeatedly use
random access to four cell corners. The calculation needs adjacent rows, not
per-point dictionaries. A Large Grid implementation can generate Marching
Squares segments from two rows, although segment stitching may still consume
memory proportional to contour complexity.

When contour levels are interval-derived, the current contract derives them
from the observed maximum duration. The safest memory-efficient equivalent is
a deterministic two-pass path: the first pass obtains summary maxima and the
second emits contour segments for the unchanged levels. Explicit levels do not
have this discovery dependency.

No in-repository calculation consumer fundamentally requires a full list of
point dictionaries. The full list remains necessary only for the existing
Small Grid public data contract and for the current, unmodified consumer
implementations.

## Impact of `max_duration_grid_points = 250000`

The setting currently has two related roles:

1. It prevents oversized core-grid allocation and returns
   `max_duration_grid_points_exceeded` before materialization.
2. It independently checks the site-boundary-expanded grid. If only that grid
   exceeds the limit, core duration may remain complete while measurement
   masks, site-distance contours, and selected regulatory comparison remain
   unavailable because boundary coverage is incomplete.

Fast and Standard accuracy presets overlay grid resolution and solar time step;
they do not override `max_duration_grid_points`. The separate site-generated
distance-contour path also has a 250,000-point constant, but it is not the
Forward duration setting.

A future implementation should not silently redefine or remove the existing
limit. It should distinguish the existing Small Grid materialization limit from
an explicitly bounded Large Grid streaming capability, while retaining the
current failure and boundary-degradation semantics for Small Grid.

## Recommended architecture

Keep the current Small Grid path intact and add a separate Large Grid path at
the regular-grid traversal boundary in `shadow_duration.py`:

1. Reuse the current validation, bounds calculation, grid specification, and
   core-versus-boundary preflight semantics.
2. Preserve the current materialized result for Small Grid, including every
   field and point dictionary exposed in `OUT`.
3. For Large Grid, calculate deterministic row-major duration rows without
   constructing a point dictionary per cell.
4. Feed focused row consumers/accumulators for duration summaries,
   measurement masks, equal-time contours, and site-distance contours.
5. Keep regulatory comparison, debug, and preview downstream of their existing
   compact derived contracts.
6. Keep Large Grid selection internal to focused Shadow Core modules. Do not
   add Dynamo Player inputs, Python-node ports, or graph changes.
7. Record an explicit storage/path discriminator for Large Grid rather than
   making an absent full grid look like a failed Small Grid result.

This additive boundary minimizes compatibility risk: Small Grid continues
through its existing list-based interface, while only Large Grid opts into the
memory-efficient interface.

## Files for the implementation PR

Expected focused changes:

- `runtime/shadow_duration.py`
- `runtime/shadow_contours.py`
- `runtime/shadow_site_masks.py`
- `runtime/shadow_site_distance_contours.py`
- `runtime/script.py` only for minimal orchestration wiring
- the corresponding duration, contour, mask, distance-contour, comparison, and
  integration tests
- `runtime/shadow_policies.py` and debug/specification documentation only if a
  new internal limit, storage mode, or summary field is introduced

Files that should normally remain untouched:

- `runtime/Shadow.dyn`
- `runtime/dynamo_loader.py`
- Revit projection, union, footprint, and adapter modules
- preview modules
- calculation accuracy presets and Dynamo Player choices
- reverse-shadow modules

## Remaining risks

- External Dynamo consumers may read `OUT.shadow_duration.duration_grid`, so a
  Large Grid output contract must be additive and explicit rather than silently
  changing the Small Grid shape.
- Two-pass duration evaluation trades CPU time for bounded memory and needs
  equivalence tests against the materialized path.
- Marching Squares row streaming bounds scalar-field memory, but contour
  segment stitching can still grow with output complexity and needs its own
  safety analysis in the implementation PR.
