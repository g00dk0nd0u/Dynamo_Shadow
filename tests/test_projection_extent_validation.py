import pytest

from shadow_formal_projection import _aggregate_runtime_checks, _validate_projection_extents
from shadow_debug import _formal_shadow_polygon_debug_summary


@pytest.mark.parametrize("axis", [(-1, 1), (0, 1), (1, 1)])
def test_08_12_16_expected_projection_extent_matches(axis):
    length = (axis[0] ** 2 + axis[1] ** 2) ** .5
    ray = {"x": axis[0] / length, "y": axis[1] / length, "z": -1 / length}
    source = [{"x": 0, "y": 0, "z": 0}, {"x": 0, "y": 0, "z": 10}]
    actual = [{"points_m": [{"x": 0, "y": 0}, {"x": axis[0] / length * 10, "y": axis[1] / length * 10}]}]
    result = _validate_projection_extents(source, actual, ray, 1, 0, 1e-9)
    assert result["extent_validation_passed"]


@pytest.mark.parametrize("scale", [.5, 1.5])
def test_over_or_under_sized_polygon_fails_extent_validation(scale):
    source = [{"x": 0, "y": 0, "z": 0}, {"x": 0, "y": 0, "z": 10}]
    actual = [{"points_m": [{"x": 0, "y": 0}, {"x": 0, "y": 10 * scale}]}]
    result = _validate_projection_extents(source, actual, {"x": 0, "y": 1, "z": -1}, 1, 0, 1e-6)
    assert not result["extent_validation_passed"]


def test_extent_failure_in_multiple_runtime_checks_is_failed_not_unverified():
    checks = [
        {"passed": True, "section_axis_min_m": 0.0, "extent_validation_passed": True},
        {"passed": True, "section_axis_min_m": 0.0, "extent_validation_passed": False},
    ]
    verified, failed = _aggregate_runtime_checks(checks)
    assert verified is False and failed is True
    formal = {"slices": [{"complete": False, "revit_runtime_direction_verified": False,
        "actual_polygon_direction_check": {"passed": False,
            "reason": "one or more runtime polygons failed", "checks": checks},
        "casters": []}]}
    summary = _formal_shadow_polygon_debug_summary(formal)
    assert summary["runtime_polygon_direction_failed_count"] == 1
    assert summary["runtime_polygon_direction_unverified_count"] == 0


def test_missing_extent_result_is_unverified_not_failed():
    assert _aggregate_runtime_checks([{"passed": True, "extent_validation_passed": None}]) == (False, False)
