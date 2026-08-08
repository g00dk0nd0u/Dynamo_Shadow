# Forward / Reverse validation v1

## Purpose and scope

This fixed-fixture, pure-Python baseline compares a constant-height vertical prism in the same site, solar conditions, and selected regulatory preset. It reports whether the Forward-equivalent near/far maxima are within the selected numerical limits and whether the entire sampled prism fits the current Reverse v2 top surface. It does not produce a legal judgement or permit certification.

The validator is deliberately named `pure_python_prismatic_forward_equivalent_validator_v1`. Production Forward remains `grid_trapezoidal_time_integration_v1` after Revit-native projection and Boolean union; this validator cannot reproduce that native geometry path. Final parity against Forward on a Revit installation belongs to Issue #97.

## Geometry and integration

At each 0.5 m grid point and 15-minute true-solar-time sample, a finite segment is cast toward the sun from the Article 56-2 measurement plane. Its length is the prism height above that plane multiplied by the existing solar `shadow_length_factor`. Boundary-inclusive segment/polygon intersection supports concave, hole-free footprints and does not use a bounding box as shadow geometry. A prism at or below the measurement plane casts no shadow on that plane.

The implementation reuses the existing solar semantics and the same shared trapezoidal integration helper as production duration accumulation. It also delegates zone maxima to `build_measurement_masks()` and selected-limit status to `build_selected_limit_comparison()`.

## Reverse comparison

Reverse v2 (`low_rise_optimized_continuous_sunlight_envelope_v2`) is invoked unchanged with Standard accuracy. Candidate-footprint vertices, edges, and an interior grid at no more than 0.5 m spacing are evaluated against its actual top-surface triangles by barycentric interpolation. Missing or unbounded surface coverage is never classified as inside.

Classifications are:

- `forward_within_reverse_inside`
- `forward_within_reverse_outside`
- `forward_exceeds_reverse_inside`
- `forward_exceeds_reverse_outside`
- `undetermined`

The frozen `centered_mismatch` fixture reproduces a Forward-equivalent-within / Reverse-v2-outside result without altering either limit or algorithm. Reverse algorithm development remains Issue #95.

## API audit and limitations

**Standard API considered:** Revit `ExtrusionAnalyzer`, native curve loops, and Boolean operations remain the formal production candidates documented by the repository; Dynamo geometry nodes are suitable only for preview/fallback use. **Reason not sufficient here:** the purpose is deterministic Ubuntu CI without Revit or libG. **Custom fallback scope:** only a vertical-prism ray/2D polygon validator and Reverse mesh interpolation. **Supported Revit version:** no Revit dependency; production remains targeted at Revit 2024.3. **Known limitations:** one hole-free polygon, constant prism height, fixed winter-solstice solar semantics, sampled 0.5 m validation, and no claim of exact or certified Forward equivalence.
