# RevitShadow product project

This directory is reserved for the future Revit 2024.3 add-in. The intended
dependency direction is `RevitShadow.dll` → `ShadowCore.dll`.

Revit selection, native geometry, internal-unit conversion, UI, and output code
belong here. Autodesk assemblies must be supplied by the local build environment;
they must not be copied into this repository or a public distribution. No working
add-in entry point, manifest, UI, installer, or certified legal judgement exists yet.
