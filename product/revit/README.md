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
belong here. Exact Autodesk references are deferred until host implementation and
must be supplied by the build environment, never committed or distributed. No
working command, manifest, UI, installer, version-certified binary, or certified
legal judgement exists yet.
