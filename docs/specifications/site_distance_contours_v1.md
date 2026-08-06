# Site distance contours v1

## Purpose

Site distance contours v1 generates display-only XY-meter polylines for the fixed 5 m and 10 m distances outside a selected site boundary. It is Issue #37 phase 2 scope only.

## Inputs

The stage reuses existing pipeline outputs:

- `site_boundary_geometry.outer_loop`
- `shadow_duration.grid_spec`
- `shadow_duration.duration_grid` point coordinates
- `shadow_duration.boundary_evaluation_coverage_complete`

No Dynamo Player input is added.

## Signed distance

Each duration-grid point is evaluated against the site boundary using the same point-to-boundary distance meaning as `runtime/shadow_site_masks.py`:

- outside the site: positive distance
- on the site boundary: zero
- inside the site: negative distance

The shadow-duration value itself is not used for distance contour generation.

## Fixed distances

The only generated levels are fixed at 5.0 m and 10.0 m. Arbitrary distance inputs, legal profiles, municipality data, and zoning data are not part of v1.

## Marching Squares

The signed-distance grid is contoured with the existing deterministic Marching Squares helpers used by equal-time contours, including linear interpolation, deterministic ambiguous-cell handling, segment stitching, and deterministic ordering.

## Geometry characteristics

The output may contain multiple loops per distance, including for concave Areas or when the grid/source geometry creates separated contour components. Contours are grid-based approximations. No smoothing, spline conversion, corner rounding, or polygon offset is applied. These polylines are not exact statutory offset curves.

## Revit and legal scope

This stage creates no Revit elements: no Model Curves, Detail Curves, DirectShapes, Filled Regions, labels, or dimensions. The output is display-preparation data only and is not legal judgement, ordinance certification, permit certification, or a report.
