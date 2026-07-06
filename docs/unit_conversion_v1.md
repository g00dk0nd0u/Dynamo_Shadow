# Unit conversion diagnostics v1

This project reads Revit geometry values in Revit internal units, normally feet. Legal settings and the Article 56-2 measurement plane are represented in SI meters.

This version adds diagnostics only:

- Raw Revit fields are preserved.
- Converted meter fields are added with `_m`, `_m2`, and `_m3` suffixes.
- Revit `DB.UnitUtils` is preferred when available.
- Normal Python execution outside Revit uses fallback factors:
  - `1 ft = 0.3048 m`
  - `1 ft2 = 0.09290304 m2`
  - `1 ft3 = 0.028316846592 m3`
- `unit_conversion_diagnostics` reports the active conversion backend.

These diagnostics do not mean the tool is ready for legal judgement. Formal footprint polygon generation, `CurveLoop` creation, shadow projection, equal-time contours, and legal judgement remain unimplemented.

## Measurement-plane relation comparisons

Raw/internal z diagnostics must compare Revit internal-unit z values against `measurement_plane.elevation_internal_candidate`. Raw feet must not be compared directly with `measurement_plane.elevation_m`.

Meter diagnostics compare meter-converted z values against `measurement_plane.elevation_m`. Both relation candidates are diagnostic only and are not used for shadow geometry, projection, or legal judgement.

Sanitized debug logs include a compact `unit_conversion_summary` so reviewers can confirm the conversion backend and fallback factors without logging raw Revit objects or full geometry payloads.
