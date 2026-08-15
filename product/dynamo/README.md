# Compiled Dynamo host proof of load

This directory contains a deliberately small architecture proof, separate from
the canonical Python graph at `runtime/Shadow.dyn`:

```text
DynamoShadow_PoC.dyn -> DynamoShadow.dll -> ShadowCore.dll -> AccuracyPresets
```

`AccuracyPresetNodes.GetGridResolutionMeters` is a public static method, so
Dynamo can expose it as a standard Zero-Touch node by loading the assembly. No
Dynamo, Revit, custom UI, or `NodeModel` reference is needed for this scalar PoC.
The wrapper contains no preset values; it delegates their resolution to
`ShadowCore.AccuracyPresets`.

## Build and manual Revit 2025 test

1. From the repository root, run:

   ```powershell
   dotnet build product/dynamo/DynamoShadow.csproj --configuration Release
   ```

   MSBuild places both required assemblies in the deterministic directory
   `product/dynamo/bin/Release/net8.0/`.
2. Open **Revit 2025**, then open its bundled Dynamo from **Manage > Dynamo**.
3. In Dynamo, choose **File > Import Library**, select
   `product/dynamo/bin/Release/net8.0/DynamoShadow.dll`, and confirm the
   `DynamoShadow.AccuracyPresetNodes.GetGridResolutionMeters` node is available.
   Keep `ShadowCore.dll` beside it; the project-reference build already does so.
4. Open `product/dynamo/DynamoShadow_PoC.dyn`.
5. Leave the String input as `standard` (or enter `standard`) and run the graph.
6. The Watch node must display exactly `0.5`.

If loading fails, return a screenshot containing the complete Dynamo window,
the node warning tooltip, and **Dynamo > Help > About** version information.
Also return Dynamo's log from **Help > Report a Bug > Show Log in Folder** and
the output of `dotnet --info`; remove project/user-identifying text before
sharing.

This is not the final product graph or a public Dynamo package. A final
`DynamoShadow.dyn`, `pkg.json`, and version-specific real-machine validation are
still required, so public release packaging remains blocked. Revit 2026 is the
next validation target for this .NET 8 assembly; Revit 2027 requires a later
.NET 10 host target and validation.
