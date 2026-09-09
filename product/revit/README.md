# RevitShadow development smoke add-in

This directory contains the development-only compiled Revit host used to validate
the compiled Forward pipeline. It is not the production Forward product, has no
ribbon or installer, and has not yet been validated end-to-end on a real Revit
2025 or Revit 2026 machine. `permit_ready_certified` always remains `false`.

## Current compiled Forward scope

`RevitShadow.addin.template` exposes two read-only development commands:

- `RevitShadow.ForwardProjectContextSmokeCommand`
- `RevitShadow.ForwardFullForwardSmokeCommand`

The project-context command exercises the live Revit project-context boundary.
The Full Forward development command connects the currently implemented compiled
pipeline:

```text
project context / selected caster extraction
→ multi-time solar orchestration
→ native formal projection
→ native per-slice union
→ unified shadow-slice snapshot
→ shadow-duration accumulation
→ equal-time contour generation
→ compact diagnostic summary
```

The formal caster contract remains user-selected Revit **Mass** / **Generic
Model** geometry. Native Revit geometry is preserved through projection and
union; BoundingBox, mesh, convex-hull, and libG geometry are not formal
fallbacks. A blocker in a native stage stops the pipeline instead of silently
reducing accuracy or substituting diagnostic geometry.

The Full Forward smoke command is intentionally read-only and does not create
preview or result elements. Its fixed measurement height, latitude, solar
sample range, grid resolution, and contour settings are development smoke-test
constants only; they are not production, ordinance, or legal settings.

Host-neutral CI covers the portable and orchestration contracts without Autodesk
binaries. Code compiled only under `REVIT_API` is excluded from the normal CI
build, so successful CI is not evidence of real-machine Revit 2025/2026 load or
execution. End-to-end real-machine validation remains pending.

Compiled-product support for this smoke package is limited to Revit 2025 and
2026, which use `net8.0-windows`. Build separately against the Autodesk
assemblies shipped with the Revit version that will load the package; matching
target frameworks do not make version-specific builds interchangeable.

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

### Project Context smoke command

`RevitShadow.ForwardProjectContextSmokeCommand` obtains the active view's
`GenLevel`; an unavailable level is an explicit blocker rather than a reason to
select another Level. It invokes the existing project-context extraction path
without duplicating extraction logic.

### Full Forward development smoke command

`RevitShadow.ForwardFullForwardSmokeCommand` also requires the active view to
have a `GenLevel`. It passes the current Revit selection to the existing
integrator, which enforces the Mass / Generic Model caster contract, then runs
the connected compiled pipeline through equal-time contours.

The compact TaskDialog summary reports:

- `available`
- `complete`
- `final completed stage`
- `blocker stage`
- `duration grid point count`
- `contour count`
- blockers
- warnings
- `permit_ready_certified`

A complete Full Forward smoke run is expected to finish with
`final completed stage = equal_time_contours`. A failed stage must be recorded
and investigated from its structured blocker rather than worked around with a
silent fallback.

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
`C:\ProgramData\Autodesk\Revit\Addins\<year>\`.

After restarting Revit, **Add-Ins > External Tools** is expected to contain:

- **Dynamo Shadow Project Context Smoke Test**
- **Dynamo Shadow Full Forward Development Smoke Test**

The package is for development validation only. Real-machine results should
record the Revit year/build, selected caster category/count, active Level, True
North, blockers/warnings, and the final completed stage. None of these smoke
results changes `permit_ready_certified=false`.
