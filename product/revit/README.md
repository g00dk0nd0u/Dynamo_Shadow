# RevitShadow development smoke add-in

This directory contains the first development-only compiled Revit host. It is a
single read-only `IExternalCommand` that displays the Phase 5B project-context
diagnostic. It is not the full Forward product, has no ribbon or installer, and
has not yet been validated on a real Revit machine. `permit_ready_certified`
always remains `false`.

Phase 5D adds a separate native shadow-caster geometry extraction boundary for
already-resolved Revit **Mass** and **Generic Model** elements. It recursively
reads `GeometryElement` and transformed instance geometry while retaining usable
native `Solid` objects inside the Revit adapter. Bounding boxes are explicitly
not used as shadow geometry, and meshes are not converted into caster geometry.
At the Phase 5D boundary, projection, Boolean operations, duration accumulation,
contours, and preview remained future work. This Revit-enabled path has not been
compiled or executed on a real Revit installation.

Phase 5E-A adds a single-time-slice, read-only formal projection boundary. It
splits native solids, clips them above the measurement plane, optionally splits
the clipped result again, and uses `ExtrusionAnalyzer.Create`,
`GetExtrusionBase`, and `Face.GetEdgesAsCurveLoops` without a convex-hull,
bounding-box, mesh, or libG fallback. Native loops remain in the Revit-layer
result while the companion summary is host-neutral. Phase 5E-B separately adds
per-slice native union. It preserves each projected face loop collection, creates
a temporary 0.1 m extrusion, performs Revit Boolean union with one
reversed-operand retry, splits disconnected volumes, and returns owned
base-face loop copies. There is no polygon fallback or silent Boolean-failure
fallback; area checks use Revit metre/m² conversions. This path remains
unvalidated on a real Revit host.

Phase 5F-B adds the compiled multi-time orchestration boundary through native
per-slice union. It reuses the portable inclusive true-solar-time timeline and
resolved ProjectContext True North rotation, extracts project/caster data once,
and passes each model-coordinate direction to the unchanged native projection
and union stages through the same resolved single-slice tail used by Phase 5F-A.
Stage-tagged warnings remain available in the host-neutral summary. The
aggregate result owns every completed per-slice result and its native union;
any solar or native slice blocker stops processing with its sample index and
keeps the aggregate incomplete. Duration, contours, DirectShape, and permit
certification are not part of this boundary.

Compiled-product support for this package is limited to Revit 2025 and 2026,
which use `net8.0-windows`. Build separately against the Autodesk assemblies
shipped with the Revit version that will load the package; matching target
frameworks do not make version-specific builds interchangeable.

## Host-neutral build and tests

Normal CI does not require Autodesk binaries:

```powershell
dotnet build product/revit/RevitShadow.csproj --configuration Release
dotnet test product/revit-tests/RevitShadow.Tests.csproj --configuration Release
dotnet test product/tests/ShadowCore.Tests.csproj --configuration Release
```

In this mode, code that directly uses the Revit API is excluded from compilation.

## Revit-enabled smoke build

Supply the directory containing both Autodesk-provided `RevitAPI.dll` and
`RevitAPIUI.dll`. Neither binary is copied or committed.

```powershell
dotnet build product/revit/RevitShadow.csproj --configuration Release -p:EnableRevitApi=true -p:RevitApiDir="C:\path\to\Revit"
```

The development command is
`RevitShadow.ForwardProjectContextSmokeCommand`. It obtains the active view's
`GenLevel`; an unavailable level is an explicit blocker rather than a reason to
select another Level. The command uses visibly test-only constants for the
measurement height, latitude, and fallback AGL, then invokes
`ForwardRevitProjectContextDiagnosticV0.Extract` without duplicating extraction
logic.

## Build a manual-install package

From PowerShell, run:

```powershell
product/revit/build-smoke-package.ps1 -RevitApiDir "C:\path\to\Revit" -RevitYear 2025
```

Use `-RevitYear 2026` for a separate Revit 2026 build. `-OutputDirectory` is
optional. The default output is:

```text
dist/RevitShadow/2025-test/
  RevitShadow.dll
  ShadowCore.dll
  RevitShadow.addin
```

The script substitutes the absolute packaged `RevitShadow.dll` path into
`RevitShadow.addin.template`. It builds and packages only; it never writes to
ProgramData. To install later, keep both DLLs at the generated package path and
copy only `RevitShadow.addin` to
`C:\ProgramData\Autodesk\Revit\Addins\<year>\`. After restarting Revit, the
external command is expected under **Add-Ins > External Tools > Dynamo Shadow
Project Context Smoke Test**.

The TaskDialog reports `available`, `complete`, AGL elevation/source,
measurement height/plane, True North, latitude, blockers, warnings, and
`permit_ready_certified`. No Revit API object is displayed or serialized.
