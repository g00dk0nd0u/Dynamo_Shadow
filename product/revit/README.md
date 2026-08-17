# RevitShadow product project

This directory is reserved for the future compiled Revit add-in. Compiled-product
support begins at Revit 2025: Revit 2025 and 2026 use .NET 8, and Revit 2027 uses
.NET 10. Revit 2024 and earlier are not compiled-product targets. The current
Python/Dynamo reference implementation may continue to be validated in Revit
2024.3 independently of this policy.

The intended dependency direction is `RevitShadow.dll` → `ShadowCore.dll`.
Future host builds will be version-aware:

| Revit | Framework | Future API reference |
| --- | --- | --- |
| 2025 | `net8.0-windows` | Revit 2025 `RevitAPI.dll` / `RevitAPIUI.dll` |
| 2026 | `net8.0-windows` | Revit 2026 `RevitAPI.dll` / `RevitAPIUI.dll` |
| 2027 | `net10.0-windows` | Revit 2027 `RevitAPI.dll` / `RevitAPIUI.dll` |

Even where frameworks match, host binaries are not considered interchangeable
without version-specific builds and tests. The future distribution shape is
`dist/RevitShadow/{2025,2026,2027}/`, with each version containing its tested
`RevitShadow.dll`, `ShadowCore.dll`, and `RevitShadow.addin`.

Revit selection, native geometry, internal-unit conversion, UI, and output code
belong here. Autodesk references must be supplied by the build environment and
are never committed or distributed. No manifest, UI, installer,
version-certified binary, or certified legal judgement exists yet.

Phase 5A establishes only the host-neutral project-context boundary for future
compiled Forward work. A readable selected Level is the authoritative Revit
average-ground-level source; a settings value in meters is used only when no
Level is selected. The Article 56-2 measurement-plane elevation is the resolved
average-ground elevation plus the explicit measurement height in meters. The raw
`ActiveProjectLocation` angle is converted from radians to signed degrees without
sign inversion, while latitude remains an explicit Player/settings value.

The default build remains host-neutral and requires no Autodesk installation:

```text
dotnet build product/revit/RevitShadow.csproj --configuration Release
```

To compile the live Revit extractor, explicitly provide the directory containing
the Autodesk-supplied `RevitAPI.dll` (the build fails if it cannot be found):

```text
dotnet build product/revit/RevitShadow.csproj --configuration Release \
  -p:EnableRevitApi=true -p:RevitApiDir=<revit-api-directory>
```

`ForwardRevitProjectContextExtractorV0.Extract` accepts a live `Document`, an
optional already-selected `Level`, fallback AGL, measurement height, and explicit
latitude. It reads the raw Active Project Location angle without sign changes and
uses `UnitUtils.ConvertFromInternalUnits(..., UnitTypeId.Meters)` for a selected
Level. `ForwardRevitProjectContextDiagnosticV0.Extract` exposes the same call as a
small dictionary-only diagnostic boundary suitable for Dynamo or another
reflection/callable harness; it returns no Revit objects.

This path has not yet been validated on Revit 2025, 2026, or 2027. Revit
integration remains incomplete, geometry extraction is out of scope, and
`permit_ready_certified` remains false.
