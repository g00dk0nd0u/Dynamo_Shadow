import math

import shadow_reverse_low_rise as core
from shadow_reverse_preview import plan_reverse_shadow_preview_faces
from shadow_regulatory_presets import resolve_regulatory_shadow_preset
from shadow_settings import _normalize_settings


def _inputs():
    site = {"complete": True, "method": "test_rectangle", "outer_loop": [
        {"x_m": 0, "y_m": 0}, {"x_m": 12, "y_m": 0},
        {"x_m": 12, "y_m": 12}, {"x_m": 0, "y_m": 12}]}
    settings = _normalize_settings({"profile": "standard_8_16", "time_basis": "true_solar_time",
        "solar_parameter_mode": "regulatory_winter_solstice_v1", "site_latitude_deg": 35,
        "true_north_deg": 0, "average_ground_level_elevation_m": 0, "measurement_height_m": 4})
    plane = {"elevation_m": 4, "average_ground_level_elevation_m": 0, "measurement_height_m": 4}
    return site, resolve_regulatory_shadow_preset("standard_3_2"), plane, settings


def _build():
    return core.build_low_rise_reverse_shadow_core(*_inputs(), "standard")


def _assert_safe(value):
    if isinstance(value, dict):
        for item in value.values(): _assert_safe(item)
    elif isinstance(value, list):
        for item in value: _assert_safe(item)
    elif isinstance(value, float): assert math.isfinite(value)
    elif value is not None:
        text = str(value)
        assert "Autodesk.Revit.DB" not in text and not text.startswith(("/", "C:\\"))


def test_standard_top_level_core_has_nonempty_safe_mesh_and_governing_distances():
    result = _build()
    assert result["available"] and result["complete"]
    assert result["height_field"]["bounded_grid_point_count"] > 0
    mesh = result["top_surface_mesh"]
    assert mesh["top_surface_triangle_count"] > 0 and mesh["bounded_candidate_volume_m3"] > 0
    assert mesh["top_surface_boundary_loops"] and all(loop["closed"] for loop in mesh["top_surface_boundary_loops"])
    assert result["zones"]["near"] and result["zones"]["far"]
    assert result["reverse_shadow_accuracy"]["height_field_grid_resolution_m"] == 2
    assert result["reverse_shadow_accuracy"]["sun_time_step_minutes"] == 15
    governed = next(p for p in result["height_field"]["grid_points"] if p["bounded"])
    assert governed["governing_distance_m"] == governed["governing_horizontal_distance_m"]
    assert governed["governing_measurement_line_distance_m"] in (5.0, 10.0)
    assert result["legal_judgement_generated"] is result["ordinance_selection_certified"] is result["permit_ready_certified"] is False
    assert result["final_forward_equal_time_validation_required"] is True
    _assert_safe(result)


def test_asymmetric_site_selects_better_than_centered_and_is_deterministic():
    _, preset, plane, settings = _inputs()
    site = {"complete": True, "method": "test_asymmetric", "outer_loop": [
        {"x_m": 0, "y_m": 0}, {"x_m": 18, "y_m": 0},
        {"x_m": 18, "y_m": 8}, {"x_m": 4, "y_m": 8},
        {"x_m": 4, "y_m": 16}, {"x_m": 0, "y_m": 16}]}
    first = core.build_low_rise_reverse_shadow_core(site, preset, plane, settings, "standard")
    second = core.build_low_rise_reverse_shadow_core(site, preset, plane, settings, "standard")
    optimization = first["reverse_shadow_interval_optimization"]
    assert first["complete"] and optimization["gain_vs_centered"]["volume_m3"] > 0
    assert optimization["selected"] != optimization["centered_baseline"]
    assert optimization["selected"] == second["reverse_shadow_interval_optimization"]["selected"]
    assert optimization["selected"]["bounded_candidate_volume_m3"] >= optimization["centered_baseline"]["bounded_candidate_volume_m3"]-1e-9
    assert first["approximation"]["conservative_endpoint_altitude_clamp"] is True


def test_standard_and_high_complete_with_fixed_resolutions_and_denser_high_output():
    standard = _build()
    high = core.build_low_rise_reverse_shadow_core(*_inputs(), "high")
    assert standard["complete"] and high["complete"]
    assert standard["reverse_shadow_accuracy"]["height_field_grid_resolution_m"] == 2
    assert high["reverse_shadow_accuracy"]["height_field_grid_resolution_m"] == 1
    assert high["complexity"]["height_field_grid_point_count"] > standard["complexity"]["height_field_grid_point_count"]
    assert high["top_surface_mesh"]["top_surface_triangle_count"] > standard["top_surface_mesh"]["top_surface_triangle_count"]
    assert math.isfinite(high["top_surface_mesh"]["bounded_candidate_volume_m3"])
    assert high["legal_judgement_generated"] is high["ordinance_selection_certified"] is high["permit_ready_certified"] is False


def test_no_bounded_points_is_not_complete(monkeypatch):
    monkeypatch.setattr(core, "_constraint", lambda *args: None)
    result = _build()
    assert not result["available"] and not result["complete"]
    assert "reverse_shadow_no_bounded_height_points" in {b["failure_code"] for b in result["blockers"]}


def test_empty_mesh_is_not_complete(monkeypatch):
    monkeypatch.setattr(core, "_cell_crossed_by_boundary", lambda *args: True)
    result = _build()
    assert not result["available"] and not result["complete"]
    assert "reverse_shadow_top_surface_mesh_empty" in {b["failure_code"] for b in result["blockers"]}


def test_complexity_reports_each_exceeded_limit(monkeypatch):
    monkeypatch.setattr(core, "MAX_REVERSE_CONSTRAINT_CHECKS", -1)
    monkeypatch.setattr(core, "MAX_REVERSE_TOP_SURFACE_TRIANGLES", -1)
    result = _build()
    blockers = [b for b in result["blockers"] if b["failure_code"] == "reverse_shadow_complexity_limit_exceeded"]
    assert {b["limit_type"] for b in blockers} == {"constraint_checks", "top_surface_triangles"}
    assert all(b["recommended_preset"] == "rough" for b in blockers)


def test_actual_concave_core_output_plans_preview_while_ignoring_unused_null_points():
    _, preset, plane, settings = _inputs()
    site = {"complete": True, "method": "test_concave", "outer_loop": [
        {"x_m": 0, "y_m": 0}, {"x_m": 12, "y_m": 0},
        {"x_m": 12, "y_m": 4}, {"x_m": 4, "y_m": 4},
        {"x_m": 4, "y_m": 12}, {"x_m": 0, "y_m": 12}]}
    result = core.build_low_rise_reverse_shadow_core(site, preset, plane, settings, "standard")
    assert result["available"] and result["complete"]
    null_indices = {point["grid_index"] for point in result["height_field"]["grid_points"]
                    if point["height_limit_m"] is None}
    referenced = {index for triangle in result["top_surface_mesh"]["triangles"]
                  for index in triangle["vertex_grid_indices"]}
    assert null_indices and null_indices.isdisjoint(referenced)

    plan = plan_reverse_shadow_preview_faces(result, plane)
    assert null_indices.isdisjoint(plan["vertices"])
    assert plan["top_face_count"] > 0
    assert all(math.isfinite(value) for vertex in plan["vertices"].values()
               for value in (vertex["x_m"], vertex["y_m"], vertex["top_z_m"], vertex["bottom_z_m"]))
    assert result["legal_judgement_generated"] is result["ordinance_selection_certified"] is result["permit_ready_certified"] is False
