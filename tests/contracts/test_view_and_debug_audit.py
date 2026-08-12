import json

from shadow_debug import _build_debug_log_payload
from shadow_preview import _view_diagnostics


class Vector:
    X, Y, Z = 0.0, 1.0, 0.0


class View3D:
    ViewType = "ThreeD"
    UpDirection = Vector()
    def GetOrientation(self):
        raise AssertionError("3D orientation must not be diagnosed as Plan North")


def test_3d_view_is_not_recorded_as_plan_north():
    result = _view_diagnostics(View3D(), 0)
    assert result["active_view_is_3d"] and not result["active_view_is_plan"]
    assert result["plan_north_mode"] is None and result["non_plan_view_warning"]


def test_clip_diagnostics_are_retained_without_coordinate_or_native_payloads():
    analyzer = {"measurement_plane_elevation_m": 4, "source_volume_m3": 100,
        "clipped_volume_m3": 80, "below_plane_volume_removed_m3": 20,
        "clipped_component_count": 1, "clipped_min_z_m": 4, "clipped_max_z_m": 14,
        "retained_side": "positive_z_above_measurement_plane", "disposal_succeeded": True,
        "native_solid": object()}
    formal = {"available": True, "complete": True, "slices": [{"slice_index": 0,
        "true_solar_time": "08:00:00", "complete": True, "casters": [{"polygons": [],
        "analyzers": [analyzer], "blockers": []}]}]}
    payload = _build_debug_log_payload({"success": True, "formal_shadow_polygons": formal})
    text = json.dumps(payload)
    assert payload["formal_shadow_polygon_summary"]["clip_diagnostics"][0]["clipped_volume_m3"] == 80
    assert "native_solid" not in text and "points_m" not in text and "object at 0x" not in text


def test_true_north_runtime_evidence_is_retained_in_sanitized_debug_payload():
    evidence = {
        "true_north_source": "revit_active_project_location",
        "true_north_rotation_deg": -30.0,
        "true_north_rotation_rad": -0.5235987755982988,
        "raw_revit_project_position_angle_rad": -0.5235987755982988,
        "angle_contract": "privacy-safe angle contract",
        "shadow_direction_check_samples": [{
            "input_time": "08:00",
            "shadow_direction_model": {"x": -0.5, "y": 0.8660254038},
        }],
        "project_location_name": "must not be logged",
    }
    payload = _build_debug_log_payload({"success": True, "true_north": evidence})

    assert payload["true_north"] == {
        key: evidence[key] for key in (
            "true_north_source", "true_north_rotation_deg", "true_north_rotation_rad",
            "raw_revit_project_position_angle_rad", "angle_contract",
            "shadow_direction_check_samples",
        )
    }
    assert "project_location_name" not in json.dumps(payload)
