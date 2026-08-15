# Future compiled Dynamo package

This directory represents a future DLL-backed Dynamo package. It does not replace
the canonical Python graph at `runtime/Shadow.dyn`, and no compiled product graph
is implemented or publishable yet.

The intended final package is:

```text
DynamoShadow/
├─ bin/
│  └─ ShadowCore.dll
├─ extra/
│  └─ DynamoShadow.dyn
└─ pkg.json
```

The future `DynamoShadow.dyn` will call the compiled core and will not package the
Python calculation source. The existing `runtime/Shadow.dyn` remains unchanged.
