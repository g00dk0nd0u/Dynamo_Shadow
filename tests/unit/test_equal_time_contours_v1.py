import math
import pytest
from shadow_contours import build_equal_time_contours
from shadow_readiness import _build_pipeline_readiness
from shadow_settings import _normalize_settings


def duration(values, nx, ny):
    return {"complete": True, "method": "grid_trapezoidal_time_integration_v1",
            "grid_spec": {"x_count": nx, "y_count": ny, "origin_x_m": 0,
                          "origin_y_m": 0, "resolution_m": 1,
                          "ordering": "row_major_y_then_x"},
            "duration_grid": [{"shadow_duration_minutes": v} for v in values]}


def test_uniform_and_out_of_range_have_no_contours():
    source = duration([10] * 9, 3, 3)
    assert build_equal_time_contours(source, {"equal_time_contour_levels_minutes": [10]})["contour_count"] == 0
    result = build_equal_time_contours(source, {"equal_time_contour_levels_minutes": [20]})
    assert result["complete"] and result["contour_count"] == 0


def test_linear_x_is_straight_open_contour():
    result = build_equal_time_contours(duration([0, 1, 2] * 3, 3, 3),
                                       {"equal_time_contour_levels_minutes": [1.5]})
    assert result["open_contour_count"] == 1
    assert {point["x"] for point in result["contours"][0]["points_m"]} == {1.5}


def test_center_peak_is_closed_finite_without_degenerate_edges():
    result = build_equal_time_contours(duration([0,0,0,0,2,0,0,0,0], 3, 3),
                                       {"equal_time_contour_levels_minutes": [1]})
    assert result["closed_contour_count"] == 1
    for contour in result["contours"]:
        points = contour["points_m"]
        assert all(math.isfinite(p[k]) for p in points for k in ("x", "y"))
        assert all(a != b for a, b in zip(points, points[1:]))
        assert contour["length_m"] > 0


def test_levels_sorted_deduplicated_and_explicit_wins():
    result = build_equal_time_contours(duration([0, 3, 0, 3], 2, 2),
        {"equal_time_contour_levels_minutes": [2, 1, 2], "equal_time_contour_interval_minutes": .25})
    assert result["requested_levels_minutes"] == [1.0, 2.0]


def test_ambiguous_cases_are_deterministic():
    settings = {"equal_time_contour_levels_minutes": [1]}
    for values in ([2,0,0,2], [0,2,2,0]):
        first = build_equal_time_contours(duration(values, 2, 2), settings)
        assert first == build_equal_time_contours(duration(values, 2, 2), settings)
        assert first["contour_count"] == 2


def test_invalid_inputs_block_machine_readably():
    incomplete = build_equal_time_contours({"complete": False})
    assert incomplete["blockers"][0]["failure_code"] == "complete_shadow_duration_required"
    mismatch = build_equal_time_contours(duration([0], 2, 2), {"equal_time_contour_levels_minutes": [1]})
    assert mismatch["blockers"][0]["failure_code"] == "duration_grid_size_mismatch"


def test_missing_grid_metadata_blocks():
    result = build_equal_time_contours({"complete": True,
        "method": "grid_trapezoidal_time_integration_v1", "duration_grid": []})
    assert result["blockers"][0]["failure_code"] == "duration_grid_spec_missing_or_invalid"


@pytest.mark.parametrize(("key", "value"), [
    ("origin_x_m", float("nan")),
    ("origin_y_m", float("inf")),
    ("resolution_m", float("nan")),
    ("resolution_m", float("inf")),
    ("x_count", 2.5),
    ("y_count", True),
])
def test_invalid_grid_metadata_is_blocked(key, value):
    source = duration([0, 1, 0, 1], 2, 2)
    source["grid_spec"][key] = value
    result = build_equal_time_contours(source, {"equal_time_contour_levels_minutes": [0.5]})
    assert result["complete"] is False
    assert result["blockers"][0]["failure_code"] == "duration_grid_spec_missing_or_invalid"


def test_grid_endpoint_overflow_is_blocked():
    source = duration([0, 1, 0, 1, 0, 1], 3, 2)
    source["grid_spec"].update({"origin_x_m": 1e308, "resolution_m": 1e308})
    result = build_equal_time_contours(source, {"equal_time_contour_levels_minutes": [0.5]})
    assert result["complete"] is False
    assert result["blockers"][0]["failure_code"] == "duration_grid_spec_missing_or_invalid"


def test_successful_output_coordinates_and_lengths_are_finite():
    result = build_equal_time_contours(duration([0, 1, 2] * 3, 3, 3),
                                       {"equal_time_contour_levels_minutes": [0.5, 1.5]})
    assert result["complete"] is True
    assert all(math.isfinite(contour["length_m"]) for contour in result["contours"])
    assert all(math.isfinite(point[axis]) for contour in result["contours"]
               for point in contour["points_m"] for axis in ("x", "y"))


class IterableLevels(object):
    def __iter__(self):
        return iter((2, 1, 2))


@pytest.mark.parametrize(("levels", "expected"), [
    ([2, 1], [2.0, 1.0]),
    ((2, 1), [2.0, 1.0]),
    (IterableLevels(), [2.0, 1.0, 2.0]),
])
def test_settings_accept_non_string_sequences_as_python_lists(levels, expected):
    normalized = _normalize_settings({"equal_time_contour_levels_minutes": levels})
    assert normalized["normalized"]["equal_time_contour_levels_minutes"] == expected
    assert isinstance(normalized["normalized"]["equal_time_contour_levels_minutes"], list)
    result = build_equal_time_contours(duration([0, 3, 0, 3], 2, 2),
                                       {"equal_time_contour_levels_minutes": levels})
    assert result["requested_levels_minutes"] == [1.0, 2.0]


@pytest.mark.parametrize("levels", ["1,2", 2])
def test_settings_reject_string_and_scalar_levels(levels):
    normalized = _normalize_settings({"equal_time_contour_levels_minutes": levels})
    assert "equal_time_contour_levels_minutes" in normalized["invalid_keys"]
    result = build_equal_time_contours(duration([0, 3, 0, 3], 2, 2),
                                       {"equal_time_contour_levels_minutes": levels})
    assert result["blockers"][0]["failure_code"] == "invalid_equal_time_contour_settings"


def test_unsupported_duration_method_is_blocked():
    source = duration([0, 1, 0, 1], 2, 2)
    source["method"] = "other_duration_method"
    result = build_equal_time_contours(source, {"equal_time_contour_levels_minutes": [0.5]})
    assert result["complete"] is False
    assert result["blockers"][0]["failure_code"] == "unsupported_shadow_duration_method"


def test_maximum_level_count_blocks():
    result = build_equal_time_contours(duration([0, 3, 0, 3], 2, 2),
        {"equal_time_contour_levels_minutes": [1, 2], "max_equal_time_contour_levels": 1})
    assert result["blockers"][0]["failure_code"] == "max_equal_time_contour_levels_exceeded"


def test_readiness_advances_after_contours():
    result = _build_pipeline_readiness({}, {}, {}, shadow_duration={"complete": True},
                                       equal_time_contours={"complete": True})
    assert result["next_implementation_steps"] == ["site boundary", "5m / 10m distance masks", "5m / 10m geometry preparation", "selected-limit exceedance styling", "legal judgement", "report output", "reverse shadow"]
