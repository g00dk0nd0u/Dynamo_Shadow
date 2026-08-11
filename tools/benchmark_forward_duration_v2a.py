#!/usr/bin/env python3
"""Informational legacy-style versus v2-A Forward duration benchmark (no timing gate)."""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
import shadow_duration


def _rectangle(size):
    return {"role": "outer", "component_index": 0, "points_m": [
        {"x": 0, "y": 0}, {"x": size, "y": 0},
        {"x": size, "y": size}, {"x": 0, "y": size}]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=100)
    parser.add_argument("--chunk", type=int, default=8192)
    args = parser.parse_args()
    polygon = _rectangle(args.size)
    slices = {"complete": True, "slices": [{"complete": True,
        "true_solar_time": "08:{:02d}".format(minute), "polygons": [polygon]}
        for minute in (0, 15, 30, 45)]}
    settings = {"grid_resolution_m": 1, "analysis_margin_m": 20,
        "max_duration_grid_points": (args.size + 41) ** 2}
    measurements = []
    for pruning in (False, True):
        started = time.perf_counter()
        result = shadow_duration.build_shadow_duration(slices, settings,
            chunk_size=args.chunk, bbox_pruning=pruning)
        measurements.append({"bbox_pruning": pruning,
            "elapsed_ms": (time.perf_counter() - started) * 1000,
            "grid_point_count": result["grid_point_count"], "time_sample_count": 4,
            **result["engine_diagnostics"]})
    print(json.dumps({"informational_only": True, "runs": measurements}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
