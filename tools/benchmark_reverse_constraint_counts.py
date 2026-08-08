"""Pure-Python preflight counts for representative rectangular reverse sites."""
import json
import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1] / "runtime"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from shadow_reverse_accuracy import resolve_reverse_shadow_accuracy
from shadow_reverse_low_rise import (MAX_SITE_DISTANCE_GRID_POINTS,
                                     build_sunlight_interval_candidates)
from shadow_reverse_measurement import build_reverse_shadow_measurement_points
from shadow_site_distance_contours import build_site_distance_contours_from_site


def rectangle_preflight(width_m, height_m, preset_id="standard"):
    accuracy = resolve_reverse_shadow_accuracy(preset_id)
    site = {"complete": True, "outer_loop": [
        {"x_m": 0.0, "y_m": 0.0}, {"x_m": float(width_m), "y_m": 0.0},
        {"x_m": float(width_m), "y_m": float(height_m)},
        {"x_m": 0.0, "y_m": float(height_m)}]}
    contours = build_site_distance_contours_from_site(
        site, accuracy["site_distance_resolution_m"], MAX_SITE_DISTANCE_GRID_POINTS)
    measurements = build_reverse_shadow_measurement_points(
        contours, accuracy["measurement_point_spacing_m"])
    near_candidates = build_sunlight_interval_candidates(480, 960, 180, 15)["candidate_count"]
    far_candidates = build_sunlight_interval_candidates(480, 960, 120, 15)["candidate_count"]
    inside = (int(width_m / accuracy["height_field_grid_resolution_m"]) + 1) * (
        int(height_m / accuracy["height_field_grid_resolution_m"]) + 1)
    near_points = len(measurements["near"]["points"])
    far_points = len(measurements["far"]["points"])
    theoretical = inside * (near_candidates * near_points + far_candidates * far_points)
    return {"site_width_m": width_m, "site_height_m": height_m,
            "inside_height_grid_point_count": inside,
            "near_measurement_point_count": near_points,
            "far_measurement_point_count": far_points,
            "near_candidate_count": near_candidates, "far_candidate_count": far_candidates,
            "estimated_raw_constraint_checks": theoretical}


def main():
    print(json.dumps([rectangle_preflight(width, height)
                      for width, height in ((50, 50), (100, 100), (150, 200))], indent=2))


if __name__ == "__main__":
    main()
