# Forward Shadow Large Grid memory investigation

## Scope and invariants

This note reviews the current Forward pipeline only. It proposes no production-code
change. The following are invariants for any follow-up implementation:

- duration values, boundary inclusion, row-major coordinates, contour ordering, and
  the current case 5/10 result must remain byte-for-byte/equality-test compatible;
- the current cell-mean branch for ambiguous Marching Squares cells must not change;
- formal shadow generation remains the Revit `ExtrusionAnalyzer` path;
- no NumPy, parallel execution, or new asymptotic decider is considered here.

## Current data flow and principal bottlenecks

The host completes formal projection and native union before duration accumulation,
then runs equal-time contours, measurement masks, and site-distance contours as three
separate consumers of the completed duration grid.

### 1. Duration hot loop: first priority for CPU and allocation reduction

For every one of `nx * ny` points, the hot loop visits every time slice. Each visit
calls `_slice_contains()`, which currently:

1. converts every polygon vertex from dictionaries to fresh `(float, float)` tuples;
2. rebuilds the component dictionary;
3. rebuilds outer and inner lists;
4. only then performs point-in-loop tests.

Thus immutable polygon topology is reconstructed **grid points × time slices** times.
This is avoidable allocation and is likely the dominant CPU cost before Large Grid
storage becomes the dominant memory cost. The point loop also allocates a `states`
list and a duration `sum()` generator per grid point. Finally, each result point is a
three-key dictionary containing two coordinates that are already implicit in the grid
specification. The list of point dictionaries is consequently the dominant retained
duration-grid representation.

### 2. Equal-time contours: duplicate full buffer and segment graph

Contour generation first copies every dictionary duration into a Python-float list.
It then traverses all cells once per level, builds four fresh corner tuples per cell,
and retains every segment for that level before stitching. `_stitch()` temporarily
holds several overlapping representations of the same topology: `unique`, sorted
`edges`, `adjacency`, `unused`, and final `lines`. Its endpoint search also repeatedly
scans adjacency while edges remain. Peak memory is therefore proportional to the
full duration dictionaries plus a full float list plus several Python-object
representations of the largest level's segment graph.

### 3. Boundary-dependent consumers: repeated full-grid work

Measurement masks make another complete pass and recalculate point-to-boundary
distance and inside/outside state. Site-distance contours first materialize all point
tuples and all signed distances, then performs a cell traversal separately for 5 m
and 10 m. The Forward host therefore keeps the duration grid alive through all three
downstream stages.

## Low-risk improvements

The safest first optimization is to compile input geometry once, outside the grid
loop. A compiled slice can contain tuples of components, with separate immutable
outer/inner loops, numeric vertex tuples, edge tuples, and per-loop bounding boxes.
The compiled representation is internal only; it does not alter Revit geometry or
the public output. A bounding-box rejection is safe when it uses the existing
boundary epsilon (or is conservative by that epsilon). The actual `_inside_loop()`
predicate and outer-minus-inner semantics should remain unchanged.

In the same hot loop, trapezoidal weights can be precomputed per state:

`w[0]=dt[0]/2`, `w[-1]=dt[-1]/2`, and
`w[i]=(dt[i-1]+dt[i])/2` for interior slices. Accumulating
`duration += w[i]` only when the compiled slice contains the point removes the
per-point `states` list and generator without changing the mathematical operation.
To protect exact regression values, the first PR should either retain the current
left-to-right arithmetic grouping or explicitly prove equality across the full test
corpus; algebraic equivalence alone is not sufficient for floating-point output.

Other low-risk changes are deriving `x`/`y` from `(origin, index, resolution)` inside
downstream consumers and avoiding their temporary corner/index lists. These reduce
transient allocations, but changing the published list-of-dictionaries contract is
not low risk.

## Can Marching Squares use previous/current rows?

Yes. Cell evaluation only needs values at `(iy, iy+1)`, so the marching stage itself
needs two rows (`2 * nx` values). Coordinates are implicit. This is straightforward
for explicit contour levels.

It is **not yet sufficient to make the complete pipeline streaming**:

- automatically generated levels depend on the global maximum duration;
- `_stitch()` currently needs the complete segment set for a level;
- measurement masks and the selected comparison consume the published duration grid;
- the top-level `OUT` currently includes that grid.

For automatic levels, the practical choices are (a) retain a compact full duration
buffer, (b) calculate duration twice, or (c) spool rows to a temporary store. Option
(a) is simplest and avoids doubling the expensive containment work. Therefore true
row-only duration storage is not required for the first Large Grid improvement.
Two-row contour reading remains worthwhile after a compact buffer boundary exists.

## Multiple levels in one grid traversal

One cell traversal can evaluate all relevant levels while preserving the existing
case logic. With sorted levels, the cell's minimum/maximum duration identifies the
candidate level interval; `_cell_segments()` is then called for only those levels.
This changes complexity from `levels * all cells` to `all cells + crossed-level
work` and does not require an asymptotic-decider change.

However, collecting segments for every level simultaneously can increase peak memory
over the current one-level-at-a-time implementation. A first implementation should
prefer CPU predictability over this optimization. It becomes attractive together
with an incremental stitcher or per-level spill strategy, after compatibility tests
cover deterministic line start, direction, sort order, duplicate removal, and case
5/10.

## Segment and stitch memory

An eventual streaming stitcher can maintain, per level, only open polyline endpoints
plus finalized lines. Each new segment either starts a line, extends one line, joins
two lines, or closes a line. Rows that can no longer reconnect allow finalization.
This can reduce working memory toward contour-frontier size plus final output size.

It is not low risk. Rounded keys, duplicate edges, branching/degenerate vertices,
deterministic candidate selection, line orientation, and final sorting all belong to
the observable current result. Replacing `_stitch()` should therefore be deferred
until adversarial compatibility fixtures exist. A smaller intermediate step is to
remove redundant `edges`/`unused` copies within the batch stitcher, but it should be
benchmarked because Python object sharing makes intuition unreliable.

## Streaming measurement masks

Zone counts and near/far maxima are reductions and can be updated as soon as each
duration value is produced. Only the final summaries need retention. This is a good
fit for a row callback/consumer, and it preserves the current tie-break rule if grid
points arrive in the same row-major order.

Integration should be postponed until after geometry compilation because coupling
mask logic into `shadow_duration.py` would blur module boundaries. A simple engine
can expose each completed row to independent consumers; the mask consumer owns its
compiled site edges and reducer state. The existing standalone function should stay
available as the compatibility/reference path during migration.

## Separating site-distance contours from duration values

Site distance depends on the site polygon and grid coordinates, not shadow duration.
The repository already has a site-generated-grid path, but Forward currently derives
coordinates from, validates, and buffers the duration grid. Forward can instead pass
only a grid specification to a site-distance contour builder and stream signed
distance through two rows.

To keep current numerical results, the separated Forward path must use exactly the
chosen duration origin, counts, resolution, tolerance, 10 m boundary expansion, and
coverage/blocker semantics. It must not silently switch to the reverse-shadow helper's
independently rounded extent or its minimum 1 m resolution rule. This separation can
remove full `points` and `signed_values` buffers even before the duration output
contract changes.

## Full `array('d')` buffer versus row streaming

| Design | Retained scalar storage | Advantages | Costs / limitations |
| --- | ---: | --- | --- |
| Current point dictionaries | implementation-dependent, but many Python objects per point | Existing JSON-safe contract | Highest memory; coordinates duplicated; downstream float copy |
| Full `array('d')` durations | exactly 8 bytes per point for values | Random access, cheap two-row indexing, one containment pass, global maximum available, simple compatibility adapter | Materializing legacy point dictionaries for `OUT` restores most memory; requires an internal/public representation boundary |
| Previous/current rows only | `16 * nx` bytes for two double rows, excluding contour output | Lowest duration working set | automatic levels need two passes/spooling; legacy grid and later consumers prevent end-to-end streaming; stitch output can still dominate |

The full double array is the best near-term Large Grid core. It gives predictable
memory and enables all consumers without recomputing polygon containment. Row
streaming becomes necessary only when grids exceed the memory budget of `8 * N` plus
required output/contours, or when the legacy `duration_grid` contract can be replaced
with an explicitly approved compact contract. It should not be introduced merely to
optimize the current 250,000-point ceiling.

## Simplest Large Grid engine proposal

1. Validate slices/settings and select bounds exactly as today.
2. Compile every time slice once into immutable numeric component/loop/edge data,
   retaining existing outer/inner rules and conservative bounding boxes.
3. Traverse points once in row-major order. Compute each duration using the unchanged
   trapezoidal semantics, update maximum/shadowed counts, append only the duration to
   `array('d')`, and optionally notify row consumers.
4. Generate equal-time contours from the compact buffer, initially one level at a
   time with the existing `_cell_segments()` and `_stitch()` behavior.
5. Run measurement reduction as a row consumer or compact-buffer pass.
6. Generate site-distance contours from the same grid specification but independently
   of duration values, using two signed-distance rows.
7. At the outer compatibility boundary, produce the existing `duration_grid` only
   when required. A later contract migration may expose compact data, but must be
   separately approved because `OUT`, diagnostics, tests, and consumers rely on the
   current structure.

This engine changes neither formal Revit projection/union nor calculation methods.
It is a storage and execution-plan change inside the pure-Python core.

## Recommended first production PR

Keep the first PR deliberately narrow:

1. add private polygon/slice compilation in `shadow_duration.py`;
2. move all dictionary-to-float conversion and component/role grouping out of
   `_slice_contains()` and out of the grid hot loop;
3. add conservative loop/component bounding-box rejection;
4. remove the per-point `states` allocation only if exact-result tests demonstrate
   unchanged floating-point values; otherwise leave it for the next PR;
5. preserve the existing `duration_grid`, method names, bounds, blockers, warnings,
   case 5/10 behavior, and orchestration;
6. add regression fixtures covering holes, multiple components, boundary points,
   irregular time intervals, and a moderately large grid, plus a benchmark script
   that is not a pass/fail timing test.

The first PR should **not** introduce `array('d')`, row consumers, a new output
contract, multi-level traversal, or a streaming stitcher. Geometry compilation attacks
the clearest hot-loop defect with the smallest semantic surface.

## Optimizations to defer

- changing the public duration grid to a compact array or omitting coordinates;
- fusing duration, masks, and contours into one module;
- recomputing duration for a true two-row-only pipeline;
- multi-level traversal before segment-memory handling is designed;
- online stitching or union-find topology;
- spatial indexes more complex than conservative loop/component bounding boxes;
- scanline polygon filling, because boundary inclusion and vertex rules are easier to
  change accidentally;
- changes to `_cell_segments()`, especially case 5/10 or the cell-mean decision;
- NumPy, parallelism, and changes to the Revit `ExtrusionAnalyzer` formal path.

## Remaining risks and validation gates

The largest risk is numerical compatibility at polygon boundaries and ambiguous
contour cells, not the array container itself. Follow-up work should compare complete
structured outputs, including order and floating-point values, against the current
engine. Memory measurements must be taken in Dynamo CPython3/Revit as well as normal
CPython because retained `OUT` serialization and host interop may dominate. A Large
Grid feature should also define an explicit memory budget and failure preflight;
raising the current point cap without that budget would only move the failure from a
controlled blocker to host-process exhaustion.
