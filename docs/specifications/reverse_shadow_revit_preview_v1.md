# Low-rise reverse-shadow Revit preview v1

## Scope and status

This internal adapter displays the pure-Python low-rise reverse-shadow core's
`top_surface_mesh` as lightweight Revit geometry. It targets Revit 2024.3 and
uses native `TessellatedShapeBuilder`. Dynamo standard geometry nodes were
considered but are not suitable for transactionally replacing one owned,
closed DirectShape from this internal mesh. The adapter is not connected to
`Shadow.dyn`, Dynamo Player, or an Analysis Mode yet.

The preview remains coarse initial massing guidance. It is not a unique maximum
volume, does not make a legal judgement, is not permit certified, and requires
final forward equal-time validation. `permit_ready_certified` remains `false`.

## Geometry and Revit API

For each connected triangle component, the adapter opens one closed face set,
adds source top triangles, two vertical triangles per boundary-loop edge, and
reverse-wound bottom triangles. Multiple closed face sets are built by one
`TessellatedShapeBuilder` and ordinarily stored in one DirectShape. The target
is `Solid` and the explicit fallback is `Mesh`; a Mesh result is a complete
preview with a warning.

The bottom elevation is average ground level. Each top elevation is average
ground level plus the core's relative `height_limit_m`; measurement-plane
elevation is not added. Only bounded mesh geometry is used. The adapter neither
interpolates unbounded/null heights nor invents a closing height. A component
containing a zero-height vertex is omitted rather than creating a degenerate
shell; no valid remaining volume is a blocker.

No Material, family, Mass, adaptive component, point element, per-cell
DirectShape, or Revit Boolean geometry is created. Pure-Python validation and
adjacency planning are the narrow fallback logic required to translate the
core mesh into native tessellated face sets; Revit performs the shape build.

## Lifecycle and ownership

The local `reverse_shadow_preview_mode` setting accepts `off` (default),
`replace`, and `clear`. `off` starts no transaction. `replace` validates the
source first, then deletes the old owned preview and creates the new shape in
one SubTransaction, so a write failure rolls back both. `clear` deletes owned
shapes without requiring a source.

- ApplicationId: `Dynamo_Shadow.ReverseShadowPreview`
- ApplicationDataId: `method=low_rise_midday_continuous_sunlight_envelope_v1;output_kind=reverse_shadow_volume`
- Name: `Dynamo_Shadow_ReverseShadowVolume`

Cleanup does not own formal forward-shadow previews, equal-time contour
previews, user DirectShapes, or ordinary Generic Models.

## Compatibility and limitations

The tessellation imports are optional and capability-reported so normal Python
and CI can import the runtime bundle without Revit. Pure-Python/fake API tests
cover the adapter contract, but an actual Revit 2024.3 runtime test is required.
Known v1 limitations include no Player entry point, no Analysis Mode, no
material/style contract, and no automatic final forward validation. The
reverse-shadow minimum spatial resolution remains 1 m.
