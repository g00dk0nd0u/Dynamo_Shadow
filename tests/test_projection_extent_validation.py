import pytest

from shadow_formal_projection import _validate_projection_extents


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
