import json
import math

import pytest

import shadow_formal_projection as formal
from shadow_debug import _build_debug_log_payload


class MockXYZ:
    BasisZ = None
    def __init__(self, x, y, z): self.X, self.Y, self.Z = x, y, z
MockXYZ.BasisZ = MockXYZ(0, 0, 1)


class MockPlaneType:
    calls = []
    @classmethod
    def CreateByNormalAndOrigin(cls, normal, origin):
        cls.calls.append((normal, origin)); return (normal, origin)


def test_direction_uses_model_vector_and_normalizes_2_0_minus_1():
    direction, summary = formal._build_shadow_direction({
        "shadow_direction_model": {"x": 1, "y": 0},
        "shadow_direction_vector": {"x": -1, "y": 0},
        "shadow_length_factor": 2,
    }, xyz_type=MockXYZ)
    length = math.sqrt(5)
    assert (direction.X, direction.Y, direction.Z) == (2 / length, 0, -1 / length)
    assert summary["source"] == "shadow_direction_model"
    assert summary["true_north_rotation_already_applied"] is True


def test_direction_guard_localizes_invalid_and_excessive_factors():
    base = {"shadow_direction_model": {"x": 1, "y": 0}}
    for factor in (float("inf"), 0, -1):
        direction, error = formal._build_shadow_direction(dict(base, shadow_length_factor=factor), 100, MockXYZ)
        assert direction is None
        assert error["failure_code"] == "invalid_shadow_direction_model_or_factor"
    direction, error = formal._build_shadow_direction(dict(base, shadow_length_factor=101), 100, MockXYZ)
    assert direction is None
    assert error["failure_code"] == "shadow_length_factor_exceeds_guard"


def test_measurement_plane_uses_meter_elevation_and_positive_z(monkeypatch):
    monkeypatch.setattr(formal, "_meters_to_internal_length", lambda value: (value * 10, []))
    MockPlaneType.calls.clear()
    plane, diagnostic, error = formal._build_native_measurement_plane({"elevation_m": 4}, MockPlaneType, MockXYZ)
    assert error is None and plane is not None
    normal, origin = MockPlaneType.calls[-1]
    assert (normal.X, normal.Y, normal.Z) == (0, 0, 1)
    assert origin.Z == 40
    assert diagnostic["elevation_internal"] == 40


def test_runtime_native_sentinel_is_not_visited_by_debug_summary():
    class NativeSentinel:
        def __str__(self): raise AssertionError("native sentinel must not be stringified")
    payload = _build_debug_log_payload({
        "success": True,
        "formal_shadow_polygons": {"available": False, "slices": []},
        "runtime_geometry": {"casters": [{"solids": [{"native_solid": NativeSentinel()}]}]},
    })
    encoded = json.dumps(payload)
    assert "native_solid" not in encoded
    assert "runtime_geometry" not in encoded


def test_self_intersection_detection_keeps_concavity_distinct():
    assert formal._self_intersects([(0, 0), (2, 2), (0, 2), (2, 0)]) is True
    assert formal._self_intersects([(0, 0), (2, 0), (1, 1), (2, 2), (0, 2)]) is False


def test_empty_formal_result_never_claims_convex_hull_fallback():
    result = formal._empty_result({"elevation_m": 4}, [{}], {"casters": []})
    assert result["diagnostic_convex_hull_used_as_fallback"] is False
    assert result["union_performed"] is False
    assert result["permit_ready_certified"] is False


def test_api_boundary_reverses_physical_ray_and_wrong_sign_fails():
    physical, info = formal._build_physical_shadow_ray_model({"shadow_direction_model":{"x":0,"y":1},"shadow_length_factor":2}, xyz_type=MockXYZ)
    analyzer, api = formal._build_extrusion_analyzer_direction(physical, MockXYZ)
    passed, check = formal._validate_direction_contract(physical, analyzer, 2, "north")
    wrong, _ = formal._validate_direction_contract(physical, physical, 2, "north")
    assert passed is True and wrong is False
    assert api["conversion"].startswith("negative_of_physical")
    assert check["horizontal_projection_length_per_unit_height"] == 2


def test_box_projection_length_is_height_times_shadow_factor():
    physical, _ = formal._build_physical_shadow_ray_model({"shadow_direction_model":{"x":.6,"y":.8},"shadow_length_factor":2.5}, xyz_type=MockXYZ)
    height=7.0
    projected=height*math.hypot(physical.X,physical.Y)/abs(physical.Z)
    assert projected == pytest.approx(height*2.5)
