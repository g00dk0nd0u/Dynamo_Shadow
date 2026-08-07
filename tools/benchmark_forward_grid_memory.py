#!/usr/bin/env python3
"""Benchmark candidate Forward Shadow Grid containers with the stdlib only.

Each measurement starts tracemalloc immediately before constructing one
container.  The reported retained value is the traced size after construction;
peak includes construction temporaries.  Run one case per process when OS-level
isolation is important.
"""
import argparse
from array import array
import gc
import json
import math
from pathlib import Path
import statistics
import sys
import tracemalloc


POINT_COUNTS = (10_000, 40_000, 160_000, 250_000, 1_000_000)


def _shape(count):
    width = int(math.sqrt(count))
    while count % width:
        width -= 1
    return width, count // width


def _current_grid(count):
    width, _ = _shape(count)
    return [
        {
            "x_m": float(index % width),
            "y_m": float(index // width),
            "shadow_duration_minutes": float((index * 17) % 481),
        }
        for index in range(count)
    ]


def _duration_list(count):
    return [float((index * 17) % 481) for index in range(count)]


def _duration_array(typecode, count):
    return array(typecode, (float((index * 17) % 481) for index in range(count)))


def _two_rows(count):
    width, _ = _shape(count)
    return (
        array("d", (float((index * 17) % 481) for index in range(width))),
        array("d", (float(((width + index) * 17) % 481) for index in range(width))),
    )


def _row_chunk(count, chunk_points):
    width, _ = _shape(count)
    size = min(width, chunk_points)
    return [
        {
            "x_m": float(index),
            "y_m": 0.0,
            "shadow_duration_minutes": float((index * 17) % 481),
        }
        for index in range(size)
    ]


BUILDERS = {
    "list_of_dict": _current_grid,
    "duration_list": _duration_list,
    "array_d": lambda count: _duration_array("d", count),
    "array_f": lambda count: _duration_array("f", count),
    "two_row_array_d": _two_rows,
}


def measure(builder, count, repeats):
    samples = []
    for _ in range(repeats):
        gc.collect()
        tracemalloc.start()
        value = builder(count)
        retained, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        samples.append((retained, peak))
        del value
    return {
        "retained_bytes": int(statistics.median(item[0] for item in samples)),
        "peak_bytes": int(statistics.median(item[1] for item in samples)),
    }


def measure_contours(count):
    """Measure the current contour function above an already-retained grid."""
    runtime = Path(__file__).resolve().parents[1] / "runtime"
    sys.path.insert(0, str(runtime))
    from shadow_contours import build_equal_time_contours

    width, height = _shape(count)
    grid = []
    center_x, center_y = (width - 1) / 2.0, (height - 1) / 2.0
    tracemalloc.start()
    for index in range(count):
        x, y = index % width, index // width
        duration = max(0.0, 480.0 - math.hypot(x - center_x, y - center_y) * 3.0)
        grid.append({"x_m": float(x), "y_m": float(y),
                     "shadow_duration_minutes": duration})
    baseline, _ = tracemalloc.get_traced_memory()
    result = build_equal_time_contours({
        "complete": True,
        "method": "grid_trapezoidal_time_integration_v1",
        "duration_grid": grid,
        "grid_spec": {"x_count": width, "y_count": height,
                      "origin_x_m": 0.0, "origin_y_m": 0.0,
                      "resolution_m": 1.0, "ordering": "row_major_y_then_x"},
    }, {"equal_time_contour_levels_minutes": [60.0, 120.0, 180.0, 240.0]})
    retained, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {"point_count": count, "grid_width": width, "grid_height": height,
            "baseline_grid_bytes": baseline,
            "additional_retained_bytes": retained - baseline,
            "additional_peak_bytes": peak - baseline,
            "contour_count": result["contour_count"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--counts", nargs="+", type=int, default=POINT_COUNTS)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--row-chunk-points", type=int, default=1024)
    parser.add_argument("--with-contours", action="store_true")
    args = parser.parse_args()
    if args.repeats < 1 or any(count < 1 for count in args.counts):
        parser.error("counts and repeats must be positive")

    rows = []
    for count in args.counts:
        width, height = _shape(count)
        builders = dict(BUILDERS)
        builders["representative_row_chunk"] = (
            lambda n, size=args.row_chunk_points: _row_chunk(n, size)
        )
        for name, builder in builders.items():
            result = measure(builder, count, args.repeats)
            resident_points = (2 * width if name == "two_row_array_d"
                               else min(width, args.row_chunk_points)
                               if name == "representative_row_chunk" else count)
            result.update({
                "representation": name,
                "point_count": count,
                "grid_width": width,
                "grid_height": height,
                "resident_point_count": resident_points,
                "retained_bytes_per_grid_point": result["retained_bytes"] / count,
                "retained_bytes_per_resident_point": result["retained_bytes"] / resident_points,
            })
            rows.append(result)
    output = {
        "method": "tracemalloc_median",
        "repeats": args.repeats,
        "row_chunk_max_points": args.row_chunk_points,
        "measurements": rows,
    }
    if args.with_contours:
        output["contour_measurements"] = [measure_contours(count) for count in args.counts]
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
