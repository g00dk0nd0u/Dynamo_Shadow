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
