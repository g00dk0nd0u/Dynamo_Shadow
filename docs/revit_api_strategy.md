# Revit-native API strategy

## Decision

The architecture priority is Revit native API first, Dynamo standard nodes second, and custom Python third. This is a migration plan, not a claim that the planned native geometry paths are implemented. Revit API candidates require runtime validation in the primary target, Revit 2024.3 with Dynamo CPython3.

Revit owns native element and geometry access, unit conversion, project-location diagnostics, native solar cross-checks, volume splitting, candidate shadow-outline extraction, and native tolerance checks. Dynamo owns selection and UI inputs, execution flow, Watch output, and optional preview. Python owns Japanese regulatory logic, auditable solar calculations, contracts and normalization, validation and readiness, diagnostics and serialization, and limited fallbacks.

## Architecture decision table

| Subsystem | Current implementation | Relevant Revit/Dynamo standard API | Target primary path | Custom fallback | Current status | Follow-up issue/PR |
|---|---|---|---|---|---|---|
| Dynamo input selection | Standard selection, Level, String, and Watch nodes | Dynamo selection/input/Watch nodes | Keep current nodes | None planned | Implemented; unchanged | — |
| Native element unwrap | `UnwrapElement` / native `DB.Element` | Dynamo `UnwrapElement` | Keep native element | Safe wrapper diagnostics | Implemented; unchanged | — |
| Geometry extraction | `get_Geometry`; instance traversal | `Element.get_Geometry`, `GeometryInstance.GetInstanceGeometry` | Keep native `Solid`/`Face`/`Edge`/`Curve` | `Element.Geometry` only for preview, diagnostics, or explicit fallback experiments | Implemented diagnostics | #32, #34 |
| Unit conversion | `UnitUtils` when available, fixed SI factors otherwise | `UnitUtils.ConvertFromInternalUnits`, `ConvertToInternalUnits`; `UnitTypeId` | `UnitUtils` with Meters/SquareMeters/CubicMeters | Fixed factors only outside Revit or after API failure | Migration planned; behavior unchanged here | Future unit migration PR |
| Footprint loop extraction | Endpoint clustering, segment graph, manual stitching | `Face.GetEdgesAsCurveLoops`, `CurveLoop` | Native face edge loops preserving arcs | Manual stitching for diagnostic/pure-Python fallback | Planned; not implemented; Revit 2024.3 validation required | Follow-up A / #32 |
| Loop validation | Custom closure, winding, intersection diagnostics | `CurveLoop.IsOpen`, `HasPlane`, `GetPlane`, `IsCounterclockwise`, `Flip`, `GetExactLength`, `NumberOfCurves`; `Application.ShortCurveTolerance` | Native validation first | Existing controlled pure-Python checks | Planned; not implemented | Follow-up A / #32 |
| Project latitude/longitude | Explicit settings only | `Document.ActiveProjectLocation`, `ProjectLocation.GetSiteLocation`, `SiteLocation` | Settings first; explicitly selected project location second; Revit comparison third | Explicit settings remain authoritative | Planned read-only diagnostics | Follow-up B / #33 |
| True north | Explicit settings only | `ProjectLocation.GetProjectPosition(XYZ.Zero)`, `ProjectPosition.Angle` | Same source priority; warn on differences | Explicit settings | Planned read-only diagnostics | Follow-up B / #33 |
| Solar position | Auditable NOAA/true-solar-time Python calculation | `View.SunAndShadowSettings`, frame altitude/azimuth/time | NOAA remains primary; Revit is an independent cross-check | Existing NOAA calculation | NOAA diagnostics implemented; cross-check planned | Follow-up B / #33 |
| Diagnostic point projection | Python point-cloud projection | No equivalent adopted for this diagnostic | Retain separately from formal engine | Current implementation | Diagnostic only | #34 comparison |
| Diagnostic convex hull | Python monotonic-chain hull | No formal Revit equivalent selected | Retain as comparison/over-approximation | Current implementation | Diagnostic only; never formal | #34 comparison |
| Formal shadow polygon | Not implemented | `ExtrusionAnalyzer.Create`, `GetExtrusionBase`, `Face.GetEdgesAsCurveLoops` | ExtrusionAnalyzer candidate after volume splitting | Explicit failure; no convex-hull substitution | Planned; simple-box prototype first; Revit 2024.3 validation required | Follow-up C / #34 |
| Multi-volume handling | Per-solid diagnostics; no formal preprocessing | `SolidUtils.SplitVolumes` | Split positive-volume solids before formal analysis | Explicit capability blocker/diagnostic | Planned; not implemented | Follow-up C / #34 |
| Future time-slice union | Not implemented | `BooleanOperationsUtils` is 3D-only and may assist preprocessing | Separate 2D engine decision and controlled tests | Undecided | Not designed or implemented | Future architecture PR |
| Debug serialization | Sanitized Python dictionaries/JSON | No raw native-object serializer is appropriate | Serialize only explicit scalar/data-model boundaries | Safe string/value normalization | Implemented; unchanged | — |

`BooleanOperationsUtils` must not be assumed to solve 2D time-slice union. No caster union is introduced by this strategy PR.

## ExtrusionAnalyzer constraints

The Issue #34 candidate pipeline is positive-volume `Solid` -> `SolidUtils.SplitVolumes` -> measurement `Plane` -> `ExtrusionAnalyzer.Create` -> `GetExtrusionBase` -> `Face.GetEdgesAsCurveLoops`. It is only planned. The analyzer is expected to be most stable with a single extrusion-like solid. Independent volumes must be split, complex shapes must be allowed to fail with an explicit reason, and the direction sign must be checked in Revit 2024.3 with a simple box rather than copied uncritically from an example. A diagnostic convex hull is not an acceptable formal substitute.

`ExtrusionAnalyzer` implements `IDisposable`. Every analyzer must be released deterministically using `try/finally` and `Dispose()` unless context-manager behavior has been explicitly verified in Revit 2024.3 with Dynamo CPython3. The future implementation must not rely on Python garbage collection.

## Compatibility and source rules

Optional APIs are imported independently and exposed through boolean runtime capabilities. Missing APIs must produce a documented fallback or blocker without breaking normal-Python imports or `py_compile`. Revit 2025/2026 documentation alone is insufficient evidence of Revit 2024.3 availability.

Version note: `SolidUtils.SplitVolumes` is part of the Revit 2024.3 target path. `SolidUtils.ComputeIsGeometricallyClosed` and `ComputeIsTopologicallyClosed` are Revit 2026.4+ future-version-only candidates, not Revit 2024.3 target APIs. They may be evaluated only in a separately versioned future path.

Explicit settings have priority over Revit location values. An explicitly selected Revit project-location source is second, and automatic Revit values are comparison-only. Differences must be reported; Revit values must not silently overwrite settings. Revit solar settings are read-only comparison data unless a future requirement explicitly changes that policy.

## Recommended follow-ups

### Follow-up A — Native CurveLoop footprint path (#32)

Use `Face.GetEdgesAsCurveLoops` first, validate native `CurveLoop` objects, retain arcs, and invoke manual stitching only as fallback. Cover existing L-shaped, box, and multiple-solid cases.

### Follow-up B — Project location and solar cross-check (#33)

Add read-only `ProjectLocation` diagnostics, differences from explicit settings, and altitude/azimuth comparison with `SunAndShadowSettings`. Do not mutate project or view state. Before comparison, normalize Revit solar altitude, Revit solar azimuth, and `ProjectPosition.Angle` into the Dynamo_Shadow canonical convention: degrees, clockwise from true north, `0 <= azimuth < 360`, with north/east/south/west at `0/90/180/270`. Identify the raw Revit convention rather than guessing it, convert radians explicitly, and state whether true-north rotation was applied. Test north, east, south, west, and `true_north_deg` values `0`, `90`, and `-90`. The first Revit validation must plan to emit both raw and normalized values to sanitized debug output.

### Follow-up C — ExtrusionAnalyzer shadow prototype (#34)

Start with a simple-box spike rather than general shape support. Exercise `SolidUtils.SplitVolumes`, validate direction sign in Revit, obtain `GetExtrusionBase` loops through `Face.GetEdgesAsCurveLoops`, compare against the diagnostic point-cloud hull, and record explicit failure reasons.
