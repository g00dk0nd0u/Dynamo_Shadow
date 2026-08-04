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
| Footprint loop extraction | Native CurveLoop first; endpoint stitching fallback | `Face.GetEdgesAsCurveLoops`, `CurveLoop` | Native face edge loops preserving arcs | `Face.EdgeLoops` manual stitching for acquisition failure only | Native acquisition and validation implemented; exact point adapter currently supports Line loops | Follow-up A / #32 |
| Loop validation | Native closure, plane, winding, length, curve sequence, and short-curve checks | `CurveLoop.IsOpen`, `HasPlane`, `GetPlane`, `IsCounterclockwise`, `Flip`, `GetExactLength`, `NumberOfCurves`; `Application.ShortCurveTolerance` | Native validation first | Signed-area orientation only when the native orientation API is unavailable | Implemented; Revit 2024.3 runtime validation remains | Follow-up A / #32 |
| Project latitude/longitude | Explicit settings only | `Document.ActiveProjectLocation`, `ProjectLocation.GetSiteLocation`, `SiteLocation` | Settings first; explicitly selected project location second; Revit comparison third | Explicit settings remain authoritative | Planned read-only diagnostics | Follow-up B / #33 |
| True north | Explicit settings only | `ProjectLocation.GetProjectPosition(XYZ.Zero)`, `ProjectPosition.Angle` | Same source priority; warn on differences | Explicit settings | Planned read-only diagnostics | Follow-up B / #33 |
| Solar position | Auditable NOAA/true-solar-time Python calculation | `View.SunAndShadowSettings`, frame altitude/azimuth/time | NOAA remains primary; Revit is an independent cross-check | Existing NOAA calculation | NOAA diagnostics implemented; cross-check planned | Follow-up B / #33 |
| Diagnostic point projection | Python point-cloud projection | No equivalent adopted for this diagnostic | Retain separately from formal engine | Current implementation | Diagnostic only | #34 comparison |
| Diagnostic convex hull | Python monotonic-chain hull | No formal Revit equivalent selected | Retain as comparison/over-approximation | Current implementation | Diagnostic only; never formal | #34 comparison |
| Formal shadow polygon | Exact Line-loop prototype | `ExtrusionAnalyzer.Create`, `GetExtrusionBase`, `Face.GetEdgesAsCurveLoops` | ExtrusionAnalyzer after volume splitting | Explicit failure; no convex-hull substitution | Implemented prototype; broader Revit 2024.3 validation required | Follow-up C / #34 |
| Multi-volume handling | Native split volumes remain separate | `SolidUtils.SplitVolumes` | Split positive-volume solids before formal analysis | Explicit capability blocker/diagnostic | Implemented; no polygon union | Follow-up C / #34 |
| Time-slice union | Temporary native extrusion adapter | `GeometryCreationUtilities.CreateExtrusionGeometry`, `BooleanOperationsUtils.ExecuteBooleanOperation`, `SolidUtils.SplitVolumes`, `Face.GetEdgesAsCurveLoops` | Union exact formal Line loops once per slice; preserve native solids through extraction | None; explicit blocker | Revit-native prototype; two-caster Revit 2024.3 validation pending | #35 |
| Debug serialization | Sanitized Python dictionaries/JSON | No raw native-object serializer is appropriate | Serialize only explicit scalar/data-model boundaries | Safe string/value normalization | Implemented; unchanged | — |

## Formal per-time-slice union prototype (Issue #35)

Exact formal Line loops are reconstructed as native `CurveLoop` objects and
temporarily extruded by 0.1 m solely as an in-memory planar Boolean adapter.
`BooleanOperationsUtils.ExecuteBooleanOperation` unions caster results once per
true-solar-time slice, `SolidUtils.SplitVolumes` preserves separated components,
and the horizontal base faces are serialized back through exact Line loops.
This avoids double-counting positive-area overlaps and preserves holes and
concave outlines without BoundingBox, convex hull, tessellation, libG, or an
external clipping library. No Revit transaction or document element is created.

The standard API considered is the Revit native solid Boolean stack above.
Dynamo standard geometry nodes were not adopted because they require libG
conversion and would not preserve the formal native path. No custom polygon
clipping fallback exists; Python is limited to contracts, deterministic
ordering, topology/area validation, readiness, and JSON-safe serialization.
Missing capabilities or unprovable Boolean failures explicitly block future
duration accumulation while leaving formal source polygons available.

The supported target is Revit 2024.3 with Dynamo CPython3. The prototype still
requires actual two-caster overlap, contact, containment, hole, concavity,
retry, and disposal validation in that runtime. Duration accumulation and
equal-time contours and their optional DirectShape preview are implemented as technical prototypes; site-boundary masks, legal judgement, and permit certification remain unimplemented.

## ExtrusionAnalyzer constraints

The Issue #34 candidate pipeline is positive-volume `Solid` -> `SolidUtils.SplitVolumes` -> measurement `Plane` -> `ExtrusionAnalyzer.Create` -> `GetExtrusionBase` -> `Face.GetEdgesAsCurveLoops`. It is only planned. The analyzer is expected to be most stable with a single extrusion-like solid. Independent volumes must be split, complex shapes must be allowed to fail with an explicit reason, and the direction sign must be checked in Revit 2024.3 with a simple box rather than copied uncritically from an example. A diagnostic convex hull is not an acceptable formal substitute.

`ExtrusionAnalyzer` implements `IDisposable`. Every analyzer must be released deterministically using `try/finally` and `Dispose()` unless context-manager behavior has been explicitly verified in Revit 2024.3 with Dynamo CPython3. The future implementation must not rely on Python garbage collection.

## Compatibility and source rules

Optional APIs are imported independently and exposed through boolean runtime capabilities. Missing APIs must produce a documented fallback or blocker without breaking normal-Python imports or `py_compile`. Revit 2025/2026 documentation alone is insufficient evidence of Revit 2024.3 availability.

Version note: `SolidUtils.SplitVolumes` is part of the Revit 2024.3 target path. `SolidUtils.ComputeIsGeometricallyClosed` and `ComputeIsTopologicallyClosed` are Revit 2026.4+ future-version-only candidates, not Revit 2024.3 target APIs. They may be evaluated only in a separately versioned future path.

Explicit settings have priority over Revit location values. An explicitly selected Revit project-location source is second, and automatic Revit values are comparison-only. Differences must be reported; Revit values must not silently overwrite settings. Revit solar settings are read-only comparison data unless a future requirement explicitly changes that policy.

## Recommended follow-ups

### Follow-up A — Native CurveLoop footprint path (#32)

`Face.GetEdgesAsCurveLoops` acquisition and native `CurveLoop` validation are implemented. The exact point-polygon adapter currently supports Line loops; non-Line loops remain native-recognized but are explicitly blocked from the current point-based formal representation. `Face.EdgeLoops` and manual stitching are fallback only when native acquisition is unavailable, raises, or returns no loops. A native loop validation failure does not trigger geometry reconstruction. Tessellation is diagnostic only and is not a formal curve replacement. Issue #32 remains open for exact curved-loop representation and Revit 2024.3 runtime validation.

### Follow-up B — Project location and solar cross-check (#33)

Add read-only `ProjectLocation` diagnostics, differences from explicit settings, and altitude/azimuth comparison with `SunAndShadowSettings`. Do not mutate project or view state. Before comparison, normalize Revit solar altitude, Revit solar azimuth, and `ProjectPosition.Angle` into the Dynamo_Shadow canonical convention: degrees, clockwise from true north, `0 <= azimuth < 360`, with north/east/south/west at `0/90/180/270`. Identify the raw Revit convention rather than guessing it, convert radians explicitly, and state whether true-north rotation was applied. Test north, east, south, west, and `true_north_deg` values `0`, `90`, and `-90`. The first Revit validation must plan to emit both raw and normalized values to sanitized debug output.

### Follow-up C — ExtrusionAnalyzer shadow prototype (#34)

Continue with controlled Revit validation rather than expanding to general shape support. Validate direction sign with a simple box and the current concave prism, compare `GetExtrusionBase` loops against the diagnostic point-cloud hull, and retain explicit failure reasons.

## Formal time-slice shadow polygon prototype (Issue #34)

Formal shadow polygon generation is implemented as a read-only Revit 2024.3
`ExtrusionAnalyzer` prototype. The supported initial scope is positive-volume,
extrusion-like `DB.Solid` geometry serialized through exact Line-only native
`CurveLoop` endpoints. `SolidUtils.SplitVolumes` processes independent volumes
once per execution; results remain separate and no union is performed.

Native solids travel only through an internal runtime bundle and are never
included in `OUT` or debug JSON. The measurement plane is constructed in Revit
internal units from the configured average-ground plus measurement height, and
the analyzer ray uses the already-rotated model-XY shadow direction. Primary
direction-sign validation remains a required Revit runtime checkpoint; an
opposite-sign probe may diagnose a mismatch but must never be adopted silently.
Every analyzer and acquired curve loop is disposed deterministically. Clipping
retains the positive-Z half space. Independent runtime validation projects every
clipped-Solid Edge endpoint analytically and compares the down-shadow min/max
against `ExtrusionAnalyzer` output; direction and extent validation must both
pass before the runtime direction is marked verified.

The existing point-cloud projection and convex hull remain comparison-only
diagnostics and are never formal fallbacks. Non-Line serialization, arbitrary
complex-solid support, equal-time contours, and legal judgement remain unsupported. This prototype is not
permit-ready or ADS-equivalent.

## Grid duration accumulation v1

**Standard API considered:** Revit Boolean operations remain the primary source
of already-unified time-slice polygons. Revit 2024.3 and Dynamo standard nodes
do not provide the required Japanese-regulation time integration across slices.
**Reason it was not sufficient:** neither exposes point-in-polygon temporal
integration with outer/inner loop semantics. **Custom fallback scope:**
`shadow_duration.py` operates only after the native union has completed, at the
explicit pure-Python calculation-model boundary. It samples the combined bounds
plus margin, supports multiple components and holes, and applies trapezoidal
integration. The grid is bounded by `max_duration_grid_points`. **Supported
Revit version:** Revit 2024.3 with Dynamo CPython3, while pure-Python tests run
without Revit. **Known limitations:** this is a spatial and normally 30-minute
temporal approximation; it does not generate contours or legal judgement and is
never permit-certified.

## DirectShape visual-QA adapter

The optional preview reads only the outer and inner loops from the completed
`unified_shadow_slices` output and converts every segment to a Revit DB `Line`.
It writes one Curve-only `DirectShape` per exact hourly slice. The ordinary
representation is retained for 3D. When available, a
`ViewShapeBuilder(DirectShapeTargetViewType.Plan)` validates each Curve before a
Plan representation is set; any invalid Curve retains only the Default Curve
representation. It never creates a display Solid, Mesh, or
thin extrusion and is never an input to calculation.

Preview DirectShapes use the exact `ApplicationId`
`Dynamo_Shadow.FormalShadowPreview`. Replace and clear modes collect
DirectShapes and delete only that owned set. Graphical overrides are
projection-line colour and weight only in the current active view; the adapter
neither changes the active view nor global styles and creates no material. DirectShape
creation can remain successful when an override is unavailable. The supported
target is Revit 2024.3 with Dynamo CPython3, and runtime visual validation is
still required.
