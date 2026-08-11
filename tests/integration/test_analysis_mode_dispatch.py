import shadow_analysis_mode as mode
import shadow_debug
import script


class FakeLevel(object):
    Elevation = 10.0


def test_analysis_mode_resolution_preserves_legacy_forward_default():
    assert mode.resolve_analysis_mode(None) == {
        "mode_id": "forward_shadow", "requested_value": None, "valid": True,
        "legacy_default_used": True, "blockers": []}
    assert mode.resolve_analysis_mode("forward_shadow")["mode_id"] == "forward_shadow"
    assert mode.resolve_analysis_mode("reverse_shadow")["mode_id"] == "reverse_shadow"
    invalid = mode.resolve_analysis_mode("unexpected")
    assert not invalid["valid"]
    assert invalid["blockers"][0]["failure_code"] == "invalid_analysis_mode"


def test_forward_workflow_uses_selected_level_as_average_ground(monkeypatch):
    raw = {
        "building_elements": None, "site_boundary": None, "level": FakeLevel(),
        "settings": {"measurement_height_m": 4, "time_basis": "true_solar_time",
                     "solar_parameter_mode": "regulatory_winter_solstice_v1",
                     "true_north_deg": 0},
        "regulatory_shadow_preset": "standard_all", "site_latitude_deg": 35,
        "site_longitude_deg": 139, "calculation_accuracy_preset": "standard",
        "analysis_mode": "forward_shadow",
    }
    monkeypatch.setattr(script, "INPUTS", raw, raising=False)
    monkeypatch.setattr(script._shadow_utils, "INPUTS", raw, raising=False)
    result = script._build_success()
    assert result["settings_normalized"]["average_ground_level_source"] == "revit_level"
    assert result["settings_normalized"]["normalized"]["average_ground_level_elevation_m"] == 3.048
    assert result["measurement_plane"]["elevation_m"] == 7.048


def test_reverse_vertical_slice_uses_real_core_without_building(monkeypatch):
    site = {"complete": True, "method": "test_rectangle", "outer_loop": [
        {"x_m": 0, "y_m": 0}, {"x_m": 12, "y_m": 0},
        {"x_m": 12, "y_m": 12}, {"x_m": 0, "y_m": 12}], "warnings": []}
    monkeypatch.setattr(mode, "extract_site_boundary_area",
                        lambda value: {"complete": True, "provided": True, "warnings": []})
    monkeypatch.setattr(mode, "build_site_boundary_geometry", lambda value: site)
    monkeypatch.setattr(mode, "clear_forward_previews", lambda: {"complete": True, "results": {}})
    preview_calls = []
    monkeypatch.setattr(mode, "build_reverse_shadow_preview",
                        lambda core, plane, settings: preview_calls.append((core, settings)) or
                        {"complete": True, "available": True, "warnings": []})
    raw = {"building_elements": None, "site_boundary": object(), "level": FakeLevel(),
           "settings": {"solar_parameter_mode": "regulatory_winter_solstice_v1",
                        "time_basis": "true_solar_time", "average_ground_level_elevation_m": 0,
                        "measurement_height_m": 4, "true_north_deg": 0},
           "regulatory_shadow_preset": "standard_3_2", "site_latitude_deg": 35,
           "site_longitude_deg": 139, "calculation_accuracy_preset": "standard",
           "analysis_mode": "reverse_shadow"}
    result = mode.build_reverse_workflow(raw, "INPUTS", lambda value: {"is_none": value is None})
    assert result["success"] and not result["partial_success"]
    assert not result["forward_pipeline_executed"]
    assert result["input_usage"]["building_elements"] == "ignored"
    assert result["input_usage"]["level"] == "used_as_average_ground_level"
    assert result["settings_normalized"]["average_ground_level_source"] == "revit_level"
    assert result["settings_normalized"]["normalized"]["average_ground_level_elevation_m"] == 3.048
    assert result["measurement_plane"]["elevation_m"] == 7.048
    assert result["measurement_plane"]["level_used_as_average_ground_level"] is True
    assert result["measurement_plane"]["level_used_as_measurement_plane"] is False
    assert result["calculation_accuracy"]["height_field_grid_resolution_m"] == 1.0
    assert result["calculation_accuracy"]["sun_time_step_minutes"] == 15
    assert preview_calls and preview_calls[0][1]["reverse_shadow_preview_mode"] == "replace"


def test_reverse_failure_clears_stale_preview(monkeypatch):
    monkeypatch.setattr(mode, "clear_forward_previews", lambda: {"complete": True, "results": {}})
    monkeypatch.setattr(mode, "extract_site_boundary_area",
                        lambda value: {"complete": False, "provided": False, "warnings": []})
    monkeypatch.setattr(mode, "build_site_boundary_geometry",
                        lambda value: {"complete": False, "warnings": []})
    calls = []
    monkeypatch.setattr(mode, "build_reverse_shadow_preview",
                        lambda core, plane, settings: calls.append(settings["reverse_shadow_preview_mode"]) or
                        {"complete": True, "available": True, "warnings": []})
    raw = {key: None for key in ("building_elements", "site_boundary", "level", "settings",
        "regulatory_shadow_preset", "site_latitude_deg", "site_longitude_deg",
        "calculation_accuracy_preset", "analysis_mode")}
    raw.update({"regulatory_shadow_preset": "standard_all",
                "calculation_accuracy_preset": "standard", "analysis_mode": "reverse_shadow"})
    result = mode.build_reverse_workflow(raw, "INPUTS", lambda value: {})
    assert not result["success"]
    assert calls == ["clear"]


def test_cleanup_failure_keeps_core_result_and_suppresses_replace(monkeypatch):
    monkeypatch.setattr(mode, "clear_forward_previews", lambda: {"complete": False, "results": {}})
    monkeypatch.setattr(mode, "extract_site_boundary_area",
                        lambda value: {"complete": True, "provided": True, "warnings": []})
    site = {"complete": True, "outer_loop": [
        {"x_m": 0, "y_m": 0}, {"x_m": 12, "y_m": 0},
        {"x_m": 12, "y_m": 12}, {"x_m": 0, "y_m": 12}], "warnings": []}
    monkeypatch.setattr(mode, "build_site_boundary_geometry", lambda value: site)
    preview_modes = []
    monkeypatch.setattr(mode, "build_reverse_shadow_preview",
                        lambda core, plane, settings: preview_modes.append(
                            settings["reverse_shadow_preview_mode"]) or
                        {"complete": True, "available": True, "warnings": []})
    raw = {"building_elements": None, "site_boundary": object(), "level": None,
           "settings": {"solar_parameter_mode": "regulatory_winter_solstice_v1",
                        "time_basis": "true_solar_time", "average_ground_level_elevation_m": 0,
                        "measurement_height_m": 4, "true_north_deg": 0},
           "regulatory_shadow_preset": "standard_3_2", "site_latitude_deg": 35,
           "site_longitude_deg": 139, "calculation_accuracy_preset": "standard",
           "analysis_mode": "reverse_shadow"}
    result = mode.build_reverse_workflow(raw, "INPUTS", lambda value: {})
    assert result["success"] and result["partial_success"]
    assert preview_modes == ["clear"]
    assert "analysis_mode_opposite_preview_cleanup_incomplete" in result["warnings"]


def test_reverse_unexpected_exception_never_enters_forward_failure_path(monkeypatch):
    raw = {"analysis_mode": "reverse_shadow", "settings": {}}
    monkeypatch.setattr(script, "_read_inputs", lambda: (raw, "INPUTS"))
    monkeypatch.setattr(script, "build_reverse_workflow",
                        lambda *args: (_ for _ in ()).throw(RuntimeError("reverse failed")))
    monkeypatch.setattr(script, "_build_success",
                        lambda *args: (_ for _ in ()).throw(AssertionError("forward called")))
    result = script._dispatch_analysis_mode()
    assert not result["success"]
    assert result["error_code"] == "reverse_shadow_workflow_unhandled_exception"
    assert result["analysis_mode"]["mode_id"] == "reverse_shadow"
    assert result["forward_pipeline_executed"] is False


def test_reverse_dispatch_writes_compact_debug_log(monkeypatch, tmp_path):
    settings = {"normalized": {"debug_log_enabled": True, "debug_log_dir": "debug_logs",
                               "debug_log_filename": "reverse.json"}}
    core = {"available": True, "complete": True, "method": "reverse-test",
            "reverse_shadow_accuracy": {"preset_id": "standard"},
            "complexity": {"height_field_grid_point_count": 9},
            "approximation": {"height_field_grid_resolution_m": 2},
            "height_field": {"grid_points": [{"x_m": 1}] * 50},
            "top_surface_mesh": {"top_surface_triangle_count": 2,
                                 "bounded_candidate_plan_area_m2": 4,
                                 "bounded_candidate_volume_m3": 8,
                                 "triangles": [{"vertex_grid_indices": [0, 1, 2]}] * 50},
            "blockers": [], "warnings": []}
    preview = {"available": True, "complete": True, "mode": "replace",
               "geometry_type": "tessellated_solid", "connected_component_count": 1,
               "source_top_triangle_count": 2, "top_face_count": 2, "side_face_count": 4,
               "bottom_face_count": 2, "created_element_count": 1,
               "deleted_element_count": 0, "blockers": [], "warnings": []}
    raw = {"analysis_mode": "reverse_shadow", "settings": settings["normalized"]}
    monkeypatch.setattr(script, "_read_inputs", lambda: (raw, "INPUTS"))
    monkeypatch.setattr(script, "build_reverse_workflow", lambda *args: {
        "success": True, "partial_success": False,
        "analysis_mode": mode.resolve_analysis_mode("reverse_shadow"),
        "forward_pipeline_executed": False, "settings_normalized": settings,
        "reverse_shadow": core, "reverse_shadow_preview": preview,
        "legal_judgement_generated": False, "ordinance_selection_certified": False,
        "permit_ready_certified": False, "warnings": []})
    monkeypatch.setattr(shadow_debug, "_get_debug_base_dir", lambda: (str(tmp_path), None))
    monkeypatch.setattr(script, "_write_debug_log_if_enabled", shadow_debug._write_debug_log_if_enabled)
    result = script._dispatch_analysis_mode()
    assert result["debug_log"].get("enabled") is True
    assert result["debug_log"].get("attempted") is True
    assert result["debug_log"].get("written") is True
    payload = __import__("json").loads((tmp_path / "debug_logs" / "reverse.json").read_text())
    assert payload["analysis_mode"]["mode_id"] == "reverse_shadow"
    assert payload["reverse_shadow_summary"]["top_surface_triangle_count"] == 2
    assert payload["reverse_shadow_preview_summary"]["created_element_count"] == 1
    text = __import__("json").dumps(payload)
    assert "grid_points" not in text and '"triangles"' not in text
    assert "Autodesk.Revit.DB" not in text
