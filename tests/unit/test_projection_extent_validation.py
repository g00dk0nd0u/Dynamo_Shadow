import pytest

from shadow_debug import _formal_shadow_polygon_debug_summary
from shadow_formal_projection import (_aggregate_runtime_checks, _runtime_validation_blocker,
                                      _validate_projection_extents)


def extent(source=None, actual=None, ray=None, scale=1.0):
    source = [{"x": 0, "y": 0, "z": 0}, {"x": 0, "y": 0, "z": 10}] if source is None else source
    actual = [{"points_m": [{"x": 0, "y": 0}, {"x": 0, "y": 10 * scale}]}] if actual is None else actual
    return _validate_projection_extents(source, actual, {"x": 0, "y": 1, "z": -1} if ray is None else ray, 1, 0, 1e-6)


@pytest.mark.parametrize("axis", [(-1, 1), (0, 1), (1, 1)])
def test_08_12_16_expected_projection_extent_matches(axis):
    length = (axis[0] ** 2 + axis[1] ** 2) ** .5
    ray = {"x": axis[0] / length, "y": axis[1] / length, "z": -1 / length}
    source = [{"x": 0, "y": 0, "z": 0}, {"x": 0, "y": 0, "z": 10}]
    actual = [{"points_m": [{"x": 0, "y": 0}, {"x": axis[0] / length * 10, "y": axis[1] / length * 10}]}]
    result = _validate_projection_extents(source, actual, ray, 1, 0, 1e-9)
    assert result["extent_validation_attempted"] is True
    assert result["extent_validation_passed"] is True
    assert result["extent_validation_status"] == "passed"


@pytest.mark.parametrize("scale", [.5, 1.5])
def test_over_or_under_sized_polygon_fails_extent_validation(scale):
    result = extent(scale=scale)
    assert result["extent_validation_attempted"] is True
    assert result["extent_validation_passed"] is False
    assert result["extent_validation_status"] == "failed"


@pytest.mark.parametrize("kwargs,reason", [
    ({"source": []}, "source_points_unavailable"),
    ({"actual": []}, "shadow_polygon_points_unavailable"),
    ({"ray": {"x": 0, "y": 0}}, "physical_ray_unavailable_or_invalid"),
])
def test_unavailable_extent_inputs_are_unverified(kwargs, reason):
    result = extent(**kwargs)
    assert result["extent_validation_attempted"] is False
    assert result["extent_validation_passed"] is None
    assert result["extent_validation_status"] == "unverified"
    assert result["extent_validation_reason"] == reason


def check(direction=True, extent_passed=True, extent_attempted=True):
    return {"passed": direction, "reason": "direction_check_passed",
        "direction_validation_reason": "direction_check_passed",
        "direction_validation_attempted": True,
        "direction_validation_passed": direction,
        "extent_validation_attempted": extent_attempted,
        "extent_validation_passed": extent_passed if extent_attempted else None,
        "extent_validation_status": ("passed" if extent_passed else "failed") if extent_attempted else "unverified"}


@pytest.mark.parametrize("checks,status,passed", [
    ([check()], "verified", True),
    ([check(extent_passed=False)], "failed", False),
    ([check(extent_attempted=False)], "unverified", None),
    ([check(), check(extent_passed=False)], "failed", False),
    ([check(), check(extent_attempted=False)], "unverified", None),
    ([], "unverified", None),
])
def test_runtime_check_aggregation_is_tri_state(checks, status, passed):
    result = _aggregate_runtime_checks(checks)
    assert result["runtime_validation_status"] == status
    assert result["passed"] is passed
    assert result["check_count"] == len(checks)
    assert result["checks"] == checks


@pytest.mark.parametrize("item,expected_status,expected_passed,expected_reason", [
    (check(extent_passed=False), "failed", False,
        "one_or_more_runtime_projection_checks_failed"),
    (check(extent_attempted=False), "unverified", None,
        "one_or_more_runtime_projection_checks_unverified"),
    (check(), "verified", True, "all_runtime_projection_checks_verified"),
])
def test_single_check_preserves_aggregate_reason(item, expected_status,
                                                  expected_passed, expected_reason):
    result = _aggregate_runtime_checks([item])
    assert result["passed"] is expected_passed
    assert result["runtime_validation_status"] == expected_status
    assert result["reason"] == expected_reason
    assert result["direction_validation_reason"] == "direction_check_passed"


@pytest.mark.parametrize("aggregate,code", [
    (_aggregate_runtime_checks([check(extent_passed=False)]), "runtime_projection_validation_failed"),
    (_aggregate_runtime_checks([check(extent_attempted=False)]), "runtime_projection_validation_unverified"),
])
def test_runtime_blockers_are_not_mislabelled_as_split_failures(aggregate, code):
    blocker = _runtime_validation_blocker(aggregate, True)
    assert blocker["failure_code"] == code
    assert blocker["failure_code"] != "one_or_more_caster_splits_failed"


def test_debug_summary_uses_explicit_runtime_status():
    slices = []
    for status in ("failed", "unverified"):
        aggregate = _aggregate_runtime_checks([check(
            extent_passed=status != "failed", extent_attempted=status != "unverified")])
        slices.append({"complete": False, "revit_runtime_direction_verified": False,
            "actual_polygon_direction_check": aggregate, "casters": []})
    summary = _formal_shadow_polygon_debug_summary({"slices": slices})
    assert summary["runtime_polygon_direction_failed_count"] == 1
    assert summary["runtime_polygon_direction_unverified_count"] == 1
    assert summary["runtime_projection_extent_failed_count"] == 1
    assert summary["runtime_projection_extent_unverified_count"] == 1
