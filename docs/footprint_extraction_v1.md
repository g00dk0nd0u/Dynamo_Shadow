# Footprint extraction diagnostics v1

## Purpose

This stage adds diagnostic-only footprint extraction readiness for the user-selected shadow caster proxy elements. It is intended to inspect whether a future implementation can safely derive footprint information from Revit geometry, not to produce a formal legal footprint.

## Accepted sources

- User-selected Mass proxy elements.
- User-selected Generic Model proxy elements.
- Bottom face candidates and their planar face edge loops.

Walls, Floors, Roofs, Equipment, CAD imports, Toposolid edges, and other existing model elements are not automatically collected as footprint sources.

## What is diagnosed

For each accepted caster, the script inspects bottom face candidates and summarizes edge loop candidates. Each loop reports curve / edge counts, endpoint samples, raw closure candidate, horizontal candidate, raw Z variation, curve types, and whether non-Line curves such as Arc / Spline / Ellipse-like curves are present.

Closure is a raw endpoint comparison only. Horizontal status is based only on readable endpoint Z values. Self-intersection is explicitly not checked.

## What is not generated

This PR does not generate formal footprint polygons, Revit `CurveLoop` objects, offsets, booleans, caster unions, self-intersection checks, site-boundary clipping, own-site exclusion masks, target-area masks, 5m / 10m measurement lines, shadow polygons, equal-time contours, or legal OK/NG judgement.

## Units and measurement plane relation

Footprint geometry diagnostics use Revit `raw_internal_units`. The measurement plane remains the Article 56-2 internal diagnostic data object in meters. Formal Revit unit conversion is not implemented, so any relation between raw footprint loop values and the measurement plane is diagnostic only.

## BoundingBox policy

BoundingBox values may be reported for diagnostic summary or future analysis extent estimation only. BoundingBox is not used as footprint geometry, shadow geometry, or legal judgement geometry.

## Multiple casters and Article 56-2 awareness

Multiple selected casters are diagnosed separately. No temporary unified Revit model is created, and no caster union or polygon boolean is performed in this PR.

Article 56-2 awareness is retained: buildings on the same site should be treated as one building in future duration accumulation. That future same-site handling should happen during logical union / duration accumulation, not by merging Revit elements now.

## Site boundary

`site_boundary` is not required for footprint diagnostics. It will be required later for own-site exclusion, beyond-5m legal range masks, target area masks, and legal judgement preparation.

## Out of scope

This stage does not implement true solar time, sun position / sun vectors, shadow projection, 5m / 10m line generation, legal judgement, shadow duration accumulation, or equal-time contour generation.

## Unit conversion diagnostics

Footprint candidate diagnostics preserve raw endpoint, length, and z fields from Revit internal units and add meter-based review fields such as `endpoints_m_sample`, `total_length_m`, `z_min_m`, and `z_max_m`. These fields are diagnostic only; formal footprint polygons, CurveLoops, booleans, clipping, 5m/10m judgement, and legal judgement remain unimplemented.
