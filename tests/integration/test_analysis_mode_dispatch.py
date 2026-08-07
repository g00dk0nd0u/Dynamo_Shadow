import shadow_analysis_mode as mode


def test_analysis_mode_resolution_preserves_legacy_forward_default():
    assert mode.resolve_analysis_mode(None) == {
        "mode_id": "forward_shadow", "requested_value": None, "valid": True,
        "legacy_default_used": True, "blockers": []}
    assert mode.resolve_analysis_mode("forward_shadow")["mode_id"] == "forward_shadow"
    assert mode.resolve_analysis_mode("reverse_shadow")["mode_id"] == "reverse_shadow"
    invalid = mode.resolve_analysis_mode("unexpected")
    assert not invalid["valid"]
    assert invalid["blockers"][0]["failure_code"] == "invalid_analysis_mode"


def test_reverse_vertical_slice_uses_real_core_without_building_or_level(monkeypatch):
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
    raw = {"building_elements": None, "site_boundary": object(), "level": object(),
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
    assert result["input_usage"]["level"] == "ignored"
    assert result["calculation_accuracy"]["height_field_grid_resolution_m"] == 2.0
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
