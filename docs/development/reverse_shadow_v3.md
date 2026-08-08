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
