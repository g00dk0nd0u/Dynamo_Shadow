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
2. Prefer **Revit 2025.0 with bundled Dynamo 3.0.3**, if available, then open
   Dynamo from **Manage > Dynamo**. Revit 2025 updates bundle different Dynamo
   versions, so record the exact Revit and Dynamo versions used. If only a later
   Revit 2025 update is available, record that exact environment and do not
   generalize its result to all Revit 2025 builds.
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

## Phase 2 compiled Forward PoC

`DynamoShadow_Forward_PoC.dyn` is a minimal Phase 2 graph for real-machine
validation of the compiled Forward Vertical Slice v0 only. It is not a final
product graph, and it does not establish permit readiness or certification.

To run it manually:

1. Build `product/dynamo/DynamoShadow.csproj` in Release configuration.
2. Keep the resulting `DynamoShadow.dll` and `ShadowCore.dll` together, then
   import `DynamoShadow.dll` with Dynamo's **File > Import Library** command.
3. Open `product/dynamo/DynamoShadow_Forward_PoC.dyn` and run it manually.
4. Inspect the result dictionary in Watch. A successful future real-machine run
   is expected to show `available = true`, `complete = true`, and the `solar`,
   `shadow_slices`, `duration`, and `contours` fields. This has not yet been
   validated on a real machine.

The graph uses the repository's existing Forward Vertical Slice v0 parity
fixture values without adding another calculation convention. Its returned
`permit_ready_certified` field remains `false`.
