# Future compiled Dynamo package

This directory represents a future DLL-backed Dynamo package. It does not replace
the canonical Python graph at `runtime/Shadow.dyn`, and no compiled product graph
is implemented or publishable yet.

The intended dependency direction is `DynamoShadow.dyn` → `DynamoShadow.dll`
→ `ShadowCore.dll`. `DynamoShadow.dll` will be the Dynamo-facing compiled host
(Zero-Touch or an equivalent integration layer); the exact hosting mechanism is
not frozen yet.

The intended final package is:

```text
DynamoShadow/
├─ bin/
│  ├─ ShadowCore.dll
│  └─ DynamoShadow.dll
├─ extra/
│  └─ DynamoShadow.dyn
└─ pkg.json
```

The Revit 2025/2026 host generation will use the .NET 8-compatible Dynamo/Revit
environment, while Revit 2027 will use its .NET 10-compatible environment. Future
host assemblies may therefore need separate `net8.0-windows` and
`net10.0-windows` builds; they must not be assumed interchangeable without tests.
`ShadowCore.dll` remains shared.

Future version-aware distributions are expected under
`dist/DynamoShadow/{2025,2026,2027}/`. None of `DynamoShadow.csproj`,
`DynamoShadow.dll`, `DynamoShadow.dyn`, or `pkg.json` exists yet. The future graph
will not package Python calculation source, and `runtime/Shadow.dyn` remains the
unchanged reference graph.
