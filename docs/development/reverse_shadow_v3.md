# Reverse shadow v3 design

Reverse v2 allocates all required sunlight to one continuous interval. That is safe but can be
more conservative than Forward's accumulated trapezoidal duration rule. Reverse v3 therefore
uses zone-common safe allowance masks: every building filling an envelope is constrained during
all required cells, while allowed-shadow cells impose no constraint.

A sampled state owns a continuous **trapezoidal sample ownership cell**. End samples own a half
interval and interior samples own the interval between adjacent midpoints. Thus allowed-cell
length exactly equals Forward trapezoidal integration. Adjacent required cells merge at midpoint
boundaries. V2-derived candidates instead retain their exact continuous interval, preserving the
legacy endpoint clamp, quantization, and candidate parity.

A canonical mask has two deliberately distinct geometry variants when it originated from v2:
the pinned v2 candidate preserves the exact source interval, while the general candidate maps the
same mask through ownership-cell boundaries. Mask deduplication therefore never removes the
general geometry variant.

One explicit-time NOAA/true-solar fan is shared by all general patterns; facet index equals atomic
cell index. Per site point, measurement constraints are aggregated into a strictest limit per
cell. A deterministic, geometry-aware proxy uses at most 64 evenly distributed inside grid points
to shortlist at most 32 general patterns per zone. Every exact v2 candidate is pinned outside that
cap, so v3 cannot score worse than the v2 candidate set under the same objective.

This shortlist does not prove a globally unique maximum: it selects a safe coarse envelope among
the fully evaluated candidates. Revit/Dynamo geometry APIs were considered, but are not applicable
to this meter-based pure-Python regulatory search; no Revit Adapter behavior changes. The supported
runtime remains Revit 2024.3/Dynamo 3.3, with normal-Python tests as the custom-core boundary.
Final Forward equal-time validation remains required. The output is not legal judgement or permit
certification. The known `centered_mismatch` fixture is not improved by the current safe shortlist,
so the public production entry point intentionally remains v2 and this work is only part of #95.
An exhaustive per-zone diagnostic finds zero feasible near patterns and zero feasible far patterns
among all canonical one/two-block masks. This is a pattern-family limitation rather than a
shortlist-cap problem; increasing the cap cannot resolve it. A later stage needs a different safe
pattern-family design.

## Issue #101 research diagnostics

The shadow-state replay is a causality diagnostic: it preserves every measurement-point/time
state from the same pure-Python Forward-equivalent prism helper, rather than replacing those
states with a zone-common one/two-block pattern. It constructs an actual site-side point-height
field using the v3 ownership-cell/atomic-facet geometry: a no-shadow sample constrains only its
own measurement point, while a shadow sample permits shadow for that point. A Forward sample
instant and the full ownership cell are not identical temporal semantics, so this limitation is
reported rather than hidden. On `centered_mismatch`, the reconstructed measurement-specific
field has a 4.0 m excess versus 0.5 m for v2/v3. Thus removing the zone-common pattern does not
resolve that mismatch under the current ownership-cell geometry, so
`zone_common_pattern_sufficient_explanation` is false. However, because sample-instant and
ownership-cell semantics differ, separation of temporal-only from spatial/ray-facet causes is not
complete and `temporal_pattern_limitation_only` remains null.

The exact oracle is restricted to explicitly supplied micro grids, finite height choices, few
measurement points, and few time samples. It maximizes bounded geometric volume exactly only
within that finite discrete model, using building-wide OR shadow states and the existing
trapezoidal duration integration. It is not a global optimum for continuous or legal reality;
an explicit state-space guard blocks large searches without heuristic fallback. The
`maximum_height_m` pure-Python contract defaults to 31.0 m, accepts any positive finite value,
and never silently replaces an invalid value.

Production Reverse remains v2. Final Forward equal-time validation remains required. Neither
diagnostic generates legal judgement, ordinance certification, or permit certification.

## Issue #108 reconstruction diagnosis

PR #107 established that removing only the zone-common pattern does not explain
`centered_mismatch`: v2/v3 has 0.5 m excess while its measurement-specific ownership-cell replay
has 4.0 m excess. Issue #108 is a pure-Python cause-decomposition diagnostic, not a production
algorithm. It separately reports the Forward sample-instant finite-cell reconstruction, the
ownership-cell/adjacent-facet reconstruction, the discrete cell/grid result, and triangulated-mesh
evaluation. The corrected sample-instant path uses independent 1 m cells whose centers are offset
from mesh vertices, and enumerates 0.5 m height choices against the Forward-equivalent prism
predicate with an explicit evaluation guard and no coarse fallback. On the grid-aligned
`centered_mismatch` footprint, the exact 36-cell model has 0.0 m excess and fits the original 10 m
building; conversion to the strictest-adjacent-cell vertex mesh introduces 4.5 m excess. Thus the
measured spatial mesh delta is 4.5 m, while the combined difference to the ownership-cell/facet
replay is also 4.0 m and is not attributed to a single temporal or facet cause.

The diagnostic does not assert a cause where the representations cannot be compared
apple-to-apple. In particular, the ownership-cell-only and single-ray-versus-facet deltas remain
null until a common finite-cell facet representation exists; the currently reportable combined
delta is explicitly not a temporal-only attribution. Boundary-cell footprint, triangle
interpolation, and validation-sampling effects remain visible through separate cell/grid and mesh
excess fields. All site, measurement-point, and building-footprint coordinates must be finite.
The height-level count is bounded before its list is materialized, with an explicit blocker and no
automatic coarse fallback. A combined temporal/facet delta is reported only when the ownership
reconstruction is complete and the cell model is exact. Production Reverse remains v2, and final
Forward equal-time validation is required.
