# Forward-validated Reverse cell expansion v1

Issue #108 isolated the `centered_mismatch` loss: the measurement-specific,
sample-instant finite-cell representation had 0.0 m excess, while conversion to
shared vertices and triangles introduced substantial artificial loss. Therefore the
v1 optimization master is **finite site cell × discrete height × Forward sample
state**, not a shared-vertex mesh.

The candidate starts from unchanged Reverse v2. Fully contained square cells take
the conservatively quantized minimum of their four v2 corners, then a deterministic
greedy search considers single-cell 0.5 m increments up to a finite caller-supplied
cap (31 m by default). Whole-building shadow states use logical OR, so overlapping
columns at the same sample instant do not consume duration twice. Durations retain
the Forward trapezoidal integration semantics.

The baseline and every terminal candidate receive a 0.5 m full-domain
Forward-equivalent validation. A violating worst near/far point is added as a new
constraint and optimization restarts from the finite-cell baseline. Stalling,
iteration, evaluation, and spatial-grid guards are explicit blockers; there is no
automatic coarse fallback. A Forward-safe candidate is selected only when it
improves v2 geometric volume; otherwise the result reports v2 parity. This volume is
an optimizer geometry metric, not GFA, FAR, or legal buildable floor area.

The greedy result does not prove a global optimum. A micro-grid exhaustive oracle is
used only in tests to quantify a finite-model gap. Final Forward validation remains
required. Production Reverse remains v2; this QA candidate does not change
`Shadow.dyn`, Dynamo Player inputs, Revit preview, or production selection.

## Standard API audit

- **Standard API considered:** Revit 2024.3 native solids/booleans and Dynamo
  geometry nodes remain the production Forward candidates, but neither exposes the
  discrete sample-state optimization model required by this QA algorithm.
- **Reason it was not sufficient:** those facilities do not optimize a meter-based
  finite height field under per-sample logical constraints.
- **Custom fallback scope:** pure-Python square-column/sample-state QA only; it is
  not a Revit geometry replacement and creates no Revit objects.
- **Supported Revit version:** no Revit API dependency; normal CPython and the
  Revit 2024.3/Dynamo 3.3 host bundle remain import-compatible.
- **Known limitations:** fully contained cells only, greedy optimum not proven, and
  final Forward validation remains mandatory.

The authoritative field admits a cell only when all four v2 corners are bounded and
inside, its center is inside the site, and no site-boundary segment crosses the open
cell interior. Full validation guards both grid-point count and the theoretical
`validation points × samples × cells` shadow-check count before evaluation.

The `centered_mismatch` recovery fixture intentionally uses an explicit 10.0 m
maximum-height cap to test recovery of its original 10.0 m prism. This is not a
default-cap measurement; the public core default remains 31.0 m and accepts any
positive finite caller-supplied cap.
