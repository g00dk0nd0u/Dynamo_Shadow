# Forward Shadow Grid memory benchmark

## Scope and method

This is a Pure Python benchmark only; it does not change or validate the
production calculation. `tools/benchmark_forward_grid_memory.py` constructs
each candidate independently and measures retained and peak traced allocations
with `tracemalloc`. The figures below are the median of three runs on CPython
3.12.13, 64-bit Linux. The host had 17 GiB available, so the 1M-point run was
considered safe. NumPy and multiprocessing were not used.

The representative row chunk is the existing three-field dict shape, capped at
1,024 points. The two-row case retains two `array('d')` rows. Coordinates for
duration-only representations are reconstructed from `grid_spec` (origin,
resolution, width, and row-major index), rather than stored at every point.

`tracemalloc` reports Python-traced allocations, not process RSS, allocator
fragmentation, Revit/libG objects, or Dynamo serialization copies. Results are
therefore implementation- and runtime-specific. Peak values were nearly equal
to retained values for all six container constructors.

## Measured results

Retained memory is shown in MiB; bytes/point applies to a full grid. Streaming
rows/chunks are bounded working sets, so their parenthesized value is the actual
resident allocation rather than a meaningful full-grid bytes/point ratio.

| Points | Current list of dict | Duration list | `array('d')` | `array('f')` | Two `array('d')` rows | Representative dict row chunk |
|---:|---:|---:|---:|---:|---:|---:|
| 10k | 2.52 MiB / 264.53 B | 0.31 MiB / 32.52 B | 0.08 MiB / 8.08 B | 0.04 MiB / 4.05 B | 1.88 KiB | 23.66 KiB |
| 40k | 10.10 MiB / 264.78 B | 1.25 MiB / 32.78 B | 0.31 MiB / 8.21 B | 0.16 MiB / 4.11 B | 3.42 KiB | 47.03 KiB |
| 160k | 40.29 MiB / 264.02 B | 4.89 MiB / 32.02 B | 1.27 MiB / 8.29 B | 0.63 MiB / 4.15 B | 6.56 KiB | 93.91 KiB |
| 250k | 63.00 MiB / 264.22 B | 7.68 MiB / 32.22 B | 1.93 MiB / 8.12 B | 0.97 MiB / 4.06 B | 8.20 KiB | 117.50 KiB |
| 1M | 252.20 MiB / 264.45 B | 30.95 MiB / 32.45 B | 7.80 MiB / 8.18 B | 3.90 MiB / 4.09 B | 16.38 KiB | 235.31 KiB |

The current shape therefore costs about **264 bytes/point** on this runtime.
Keeping only durations in a Python list saves about **87.7%**. A full
`array('d')` saves about **96.9%**, while retaining double precision. The x/y
saving cannot be isolated completely from the container change in these cases;
the measured current-to-duration-only-list difference is about 232 bytes/point
and includes the removal of per-point dicts as well as x/y float objects.

## Estimated full-grid memory

These values are linear projections, clearly separated from the measurements
above. They use the 1M measured bytes/point for full-grid containers; 250k is
included as a projection cross-check and is close to its direct measurement.

| Points | Current list of dict | Duration list | `array('d')` | `array('f')` |
|---:|---:|---:|---:|---:|
| 250k | 63.05 MiB | 7.74 MiB | 1.95 MiB | 0.98 MiB |
| 1M | 252.20 MiB | 30.95 MiB | 7.80 MiB | 3.90 MiB |
| 2M | 504.40 MiB | 61.89 MiB | 15.61 MiB | 7.80 MiB |

These are container-only estimates. During a migration, simultaneously holding
the old grid, new buffer, `OUT`/JSON-safe conversion, and contour results can
multiply the process peak.

## `shadow_contours` temporary memory

The benchmark also called the current `build_equal_time_contours` with a smooth
radial synthetic field and four levels (60, 120, 180, 240 minutes). The input
list-of-dict grid was already retained before measuring the incremental peak.

| Points | Input grid baseline | Additional peak | Additional retained result | Contours |
|---:|---:|---:|---:|---:|
| 10k | 2.51 MiB | 0.08 MiB | 0.00 MiB | 0 |
| 40k | 10.08 MiB | 1.11 MiB | 0.49 MiB | 13 |
| 160k | 38.45 MiB | 2.46 MiB | 0.92 MiB | 4 |
| 250k | 59.10 MiB | 3.20 MiB | 0.92 MiB | 4 |

The current contour function first creates a full Python `values` list, which
alone adds roughly 8 bytes/point for references when the existing float objects
are reused. It then creates per-level segment tuples, stitching dictionaries,
sets, adjacency lists, and JSON-safe point dicts. Consequently, contour memory
is data-dependent: a smooth field is modest, while checkerboard/noisy fields or
many levels can create far more segments. The table is representative, not a
worst-case bound and not a 1M/2M estimate.

## Recommendation

The simplest safe Large Grid representation is **one full row-major
`array('d')`, plus the existing compact `grid_spec`**.

* It reduces the measured 1M duration buffer to 7.80 MiB and avoids storing x/y
  per point; x/y remain deterministic from the row-major index.
* Double precision avoids introducing a new numerical-precision decision merely
  to save about 4 MiB per million points. `array('f')` should require a separate
  accuracy/tolerance study before consideration.
* A full buffer supports marching-squares neighbor access and other downstream
  consumers directly. Two-row streaming is not required for the tested sizes.
* Two-row streaming only becomes worthwhile under a much tighter total-memory
  budget or substantially larger grids. It would require redesigning duration
  output, contour level discovery, contour stitching, site-mask/comparison
  consumers, and serialization; its tiny row buffer does not bound those other
  allocations.
* Before any production change, benchmark inside Revit 2024.3 / Dynamo 3.3
  CPython and redesign `shadow_contours` to consume the array without copying it
  into a Python list. Production output-contract compatibility must also be
  decided explicitly.

Reproduce the full container run with:

```bash
python tools/benchmark_forward_grid_memory.py --repeats 3
```

Run the representative contour measurement with:

```bash
python tools/benchmark_forward_grid_memory.py \
  --counts 10000 40000 160000 250000 --with-contours
```
