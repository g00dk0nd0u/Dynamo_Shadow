"""Complete dense portable Forward Vertical Slice v0 parity reference."""
import json
from pathlib import Path

import pytest
from shadow_contours import build_equal_time_contours
from shadow_duration import (
    _compile_slice_polygons,
    _compiled_slice_contains,
    build_shadow_duration,
    integrate_shadow_states_trapezoidal,
)
from shadow_projection import _build_convex_shadow_envelope_v0, _project_point
from shadow_sun import _sun_position_for_true_solar_minutes


FIXTURE = Path(__file__).parents[1] / "fixtures" / "parity" / "forward_portable_parity_v0.json"


def _sample_times(data):
    times = [data["true_solar_start_minutes"]]
    current = times[0] + data["sun_time_step_minutes"]
    while current < data["true_solar_end_minutes"] - 1e-9:
        times.append(current)
        current += data["sun_time_step_minutes"]
    if abs(times[-1] - data["true_solar_end_minutes"]) > 1e-9:
        times.append(data["true_solar_end_minutes"])
    return times


def _time_text(minutes):
    return "{:02d}:{:02d}".format(int(minutes // 60), int(minutes % 60))


def _reference(data):
    times = _sample_times(data)
    slices = []
    for minute in times:
        solar = _sun_position_for_true_solar_minutes(
            minute, data["latitude_deg"], data["solar_declination_deg"], data["true_north_deg"]
        )
        model_direction = solar.get("shadow_direction_model")
        assert model_direction is not None
        assert model_direction.get("basis") == "unit_horizontal_vector_model_xy_axes"
        projection_direction = {
            "x_east": model_direction["x"],
            "y_north": model_direction["y"],
        }
        projected = []
        for point in data["caster"]["footprint_points_m"]:
            projected.append({"x_m": point["x"], "y_m": point["y"],
                              "z_m": data["measurement_plane_elevation_m"]})
            projected.append(_project_point(
                {"x_m": point["x"], "y_m": point["y"], "z_m": data["caster"]["top_z_m"]},
                data["measurement_plane_elevation_m"], projection_direction,
                solar["shadow_length_factor"],
            )["projected_point_m"])
        hull = _build_convex_shadow_envelope_v0(
            projected, data["measurement_plane_elevation_m"]
        )["hull_points_m"]
        slices.append({
            "complete": True,
            "true_solar_time": _time_text(minute),
            "polygons": [{"component_index": 0, "role": "outer", "closed": True,
                          "points_m": [{"x": p["x_m"], "y": p["y_m"]} for p in hull]}],
        })

    duration = build_shadow_duration(
        {"complete": True, "slices": slices},
        {"grid_resolution_m": data["grid_resolution_m"],
         "analysis_margin_m": data["analysis_margin_m"],
         "max_duration_grid_points": data["max_grid_points"],
         "sun_time_step_minutes": data["sun_time_step_minutes"]},
        sparse_tiles=False,
    )
    contours = build_equal_time_contours(
        duration, {"equal_time_contour_levels_minutes": data["contour_levels_minutes"]}
    )
    compiled = [_compile_slice_polygons(item["polygons"]) for item in slices]
    changing = None
    for point in duration["duration_grid"]:
        states = [bool(_compiled_slice_contains(polygons, point["x_m"], point["y_m"]))
                  for polygons in compiled]
        if len(set(states)) > 1 and states[-2] != states[-1]:
            changing = {"x": point["x_m"], "y": point["y_m"], "states": states,
                        "duration_minutes": integrate_shadow_states_trapezoidal(states, times)}
            break
    assert changing is not None
    expected = {
        "sample_times_minutes": times,
        "representative_shadow_slices": [
            {"sample_index": index, "points_m": slices[index]["polygons"][0]["points_m"]}
            for index in (0, len(slices) - 1)
        ],
        "duration": {
            "temporal_step_minutes": duration["temporal_step_minutes"],
            "spatial_resolution_m": duration["spatial_resolution_m"],
            "grid_point_count": duration["grid_point_count"],
            "maximum_shadow_duration_minutes": duration["maximum_shadow_duration_minutes"],
            "shadowed_point_count": duration["shadowed_point_count"],
            "grid_spec": duration["grid_spec"],
            "duration_grid": duration["duration_grid"],
            "changing_state_point": changing,
        },
        "contours": {
            "generated_levels_minutes": contours["generated_levels_minutes"],
            "contour_count": contours["contour_count"],
            "closed_contour_count": contours["closed_contour_count"],
            "open_contour_count": contours["open_contour_count"],
            "items": contours["contours"],
        },
    }
    return expected


def test_fixture_is_derived_from_dense_canonical_python_pipeline():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    actual = _reference(fixture["input"])
    assert actual == fixture["expected"]
    assert actual["sample_times_minutes"] == [600, 670, 740, 800]
    assert actual["duration"]["temporal_step_minutes"] is None
    assert actual["duration"]["grid_spec"]["ordering"] == "row_major_y_then_x"
    assert actual["duration"]["grid_point_count"] < 1000


def test_changing_state_point_explicitly_uses_non_uniform_final_interval():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    point = fixture["expected"]["duration"]["changing_state_point"]
    s0, s1, s2, s3 = [int(value) for value in point["states"]]
    independently_integrated = 70 * (s0 + s1) / 2 + 70 * (s1 + s2) / 2 + 60 * (s2 + s3) / 2
    assert independently_integrated == pytest.approx(point["duration_minutes"], abs=1e-9)
    grid_point = next(item for item in fixture["expected"]["duration"]["duration_grid"]
                      if item["x_m"] == point["x"] and item["y_m"] == point["y"])
    assert grid_point["shadow_duration_minutes"] == pytest.approx(independently_integrated, abs=1e-9)
