# Revit API shadow projection feasibility

## Purpose

This note documents the current design assumption for legal-style shadow projection in this repository: Revit display shadows are not treated as reliable source geometry. The current pipeline intentionally reads Revit geometry and performs diagnostic projection on the Python side.

This is a design note only. It does not implement Revit shadow extraction, ray casting, formal shadow polygons, equal-time contours, grid accumulation, 5m / 10m legal masks, or legal OK/NG judgement.

## Current project approach

The current pipeline uses Revit as the source of selected proxy geometry, not as the source of rendered shadow geometry.

- Revit API input access is used to read user-selected Mass / Generic Model shadow caster proxy elements.
- Revit API geometry access is used for `Solid`, `Face`, `Edge`, and `Curve` diagnostics.
- Revit geometry raw values are treated as Revit internal units and converted to meters for unit-safe diagnostics.
- Python-side diagnostics currently perform:
  - true-solar-time sun-position table generation;
  - shadow direction vector diagnostics;
  - measurement-plane projection diagnostics; and
  - diagnostic projected point cloud output.

The output remains diagnostic-only. It is not a permit-ready shadow calculation and must not be treated as formal legal judgement.

## Why Revit display shadows are not used as source geometry

Revit rendered/display shadows are treated as visual output only in this project. They may be useful for human visual checking, but the current design does not assume that rendered shadows can be extracted as reliable legal geometry.

Do not rely on Revit display shadows as the source for:

- formal shadow polygons;
- equal-time contours;
- 5m / 10m masks; or
- legal OK/NG judgement.

The main reason is auditability. Legal-style shadow projection needs explicit inputs, units, time basis, measurement plane assumptions, projection logic, and validation tolerances. Display shadows are view/rendering results, so using them as calculation geometry would make the pipeline harder to inspect, reproduce, and benchmark.

## Approach comparison

### Approach A: Revit rendered/display shadows

Revit rendered or display shadows can help a reviewer visually compare whether model orientation and sun settings appear plausible. However, they are not accepted in the current pipeline as source geometry for legal-style calculations.

This approach should remain visual-check-only unless future Revit API documentation and validation work show that shadow results can be extracted with sufficient reliability, coordinate clarity, and reproducibility.

### Approach B: Revit API ray/intersection sampling

A future experiment may investigate Revit API ray/intersection style checks if suitable APIs are available in the target Dynamo / Revit environment. Such an experiment may use ray or intersection sampling against selected Mass / Generic Model proxy geometry.

This would likely be grid- or sample-based rather than polygon-first. It should be benchmarked for performance, geometric robustness, transform handling, and agreement with known test cases before it influences any legal-style output.

This note does not implement `ReferenceIntersector`, ray casting, or any sampling workflow.

### Approach C: Current approach: Revit geometry extraction plus Python projection

The current preferred approach is:

1. extract selected proxy geometry from Revit;
2. convert Revit internal-unit geometry diagnostics to meters;
3. compute the sun direction and measurement-plane projection in Python; and
4. expose diagnostic projected point cloud data for inspection.

This approach is preferred for now because it is explicit, inspectable, and controllable. The assumptions can be reviewed in source code and documentation, and future steps can be added incrementally without depending on opaque display/rendering output.

## Recommendation

Keep the current pipeline for now:

```text
Revit API geometry extraction + Python-side diagnostic projection
```

Do not proceed from diagnostic projection to formal shadow polygons, equal-time contours, 5m / 10m masks, grid accumulation, or legal OK/NG judgement until this design assumption is documented, reviewed, and validated.

For the current project stage, keep output diagnostic-only.

## Future review items

Before any formal shadow projection or legal-style output is added, review at least the following items:

- Revit API ray/intersection feasibility in the target Revit / Dynamo versions.
- Revit view and sun settings inspection feasibility.
- True North / Project North handling and sign conventions.
- `GeometryInstance` transform handling for nested or family-based geometry.
- Benchmarking against ADS or other known shadow software.
- Validation using simple known test Mass / Generic Model geometry.

## Implementation guardrails

This note does not authorize implementation of any new calculation feature. In particular, do not implement from this note alone:

- Revit shadow extraction;
- `ReferenceIntersector` or ray casting;
- shadow polygons;
- equal-time contours;
- grid accumulation;
- 5m / 10m legal masks;
- legal OK/NG judgement; or
- Revit element creation.
