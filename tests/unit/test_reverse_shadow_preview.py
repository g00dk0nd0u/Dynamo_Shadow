import copy

import pytest

import shadow_reverse_preview as preview


def _core(offset=0, height=14.0):
    points = [
        {"grid_index": offset + 0, "x_m": 0 + offset * 10, "y_m": 0, "height_limit_m": height},
        {"grid_index": offset + 1, "x_m": 2 + offset * 10, "y_m": 0, "height_limit_m": height},
        {"grid_index": offset + 2, "x_m": 2 + offset * 10, "y_m": 2, "height_limit_m": height},
        {"grid_index": offset + 3, "x_m": 0 + offset * 10, "y_m": 2, "height_limit_m": height},
    ]
    return {"available": True, "complete": True, "method": preview.METHOD,
        "height_field": {"grid_points": points}, "top_surface_mesh": {
            "vertices_source": "height_field.grid_points",
            "triangles": [{"vertex_grid_indices": [offset, offset + 1, offset + 2]},
                          {"vertex_grid_indices": [offset, offset + 2, offset + 3]}],
            "top_surface_boundary_loops": [{"closed": True,
                "vertex_grid_indices": [offset, offset + 1, offset + 2, offset + 3, offset],
                "signed_plan_area_m2": 4.0, "orientation": "counter_clockwise"}]}}


@pytest.mark.parametrize("mode", ["off", "replace", "clear"])
def test_settings_modes(mode):
    assert preview.normalize_reverse_shadow_preview_settings({"reverse_shadow_preview_mode": mode})["mode"] == mode


def test_invalid_setting_disables_preview_with_warning():
    result = preview.normalize_reverse_shadow_preview_settings({"reverse_shadow_preview_mode": "bad"})
    assert result["mode"] == "off" and result["warnings"]


@pytest.mark.parametrize("change,code", [
    (("complete", False), "reverse_shadow_preview_source_incomplete"),
    (("method", "other"), "reverse_shadow_preview_method_unsupported"),
])
def test_source_contract_rejections(change, code):
    source = _core(); source[change[0]] = change[1]
    with pytest.raises(ValueError, match=code):
        preview.plan_reverse_shadow_preview_faces(source, {"average_ground_level_elevation_m": 0})


def test_missing_or_empty_mesh_contract_rejected():
    for source in ({**_core(), "top_surface_mesh": None}, _core()):
        if source.get("top_surface_mesh"): source["top_surface_mesh"]["triangles"] = []
        with pytest.raises(ValueError, match="reverse_shadow_preview_mesh_invalid"):
            preview.plan_reverse_shadow_preview_faces(source, {"average_ground_level_elevation_m": 0})


def test_face_plan_counts_winding_and_ground_elevation():
    plan = preview.plan_reverse_shadow_preview_faces(_core(), {"elevation_m": 4, "average_ground_level_elevation_m": 10})
    component = plan["components"][0]
    assert (plan["top_face_count"], plan["bottom_face_count"], plan["side_face_count"]) == (2, 2, 8)
    assert sum((plan[key] for key in ("top_face_count", "bottom_face_count", "side_face_count"))) == 12
    assert plan["minimum_top_elevation_m"] == plan["maximum_top_elevation_m"] == 24
    assert {v["bottom_z_m"] for v in plan["vertices"].values()} == {10}
    assert component["bottom_faces"][0] == ((0, "bottom"), (2, "bottom"), (1, "bottom"))


def test_clockwise_top_is_normalized_and_degenerate_rejected():
    source = _core(); source["top_surface_mesh"]["triangles"][0]["vertex_grid_indices"] = [0, 2, 1]
    plan = preview.plan_reverse_shadow_preview_faces(source, {"average_ground_level_elevation_m": 0})
    assert plan["top_face_orientation_normalized_count"] == 1
    source = _core(); source["height_field"]["grid_points"][2]["y_m"] = 0
    with pytest.raises(ValueError, match="reverse_shadow_preview_mesh_invalid"):
        preview.plan_reverse_shadow_preview_faces(source, {"average_ground_level_elevation_m": 0})


def test_disconnected_islands_make_two_components_but_share_output_plan():
    first, second = _core(), _core(10)
    source = copy.deepcopy(first)
    source["height_field"]["grid_points"] += second["height_field"]["grid_points"]
    source["top_surface_mesh"]["triangles"] += second["top_surface_mesh"]["triangles"]
    source["top_surface_mesh"]["top_surface_boundary_loops"] += second["top_surface_mesh"]["top_surface_boundary_loops"]
    assert len(preview.build_reverse_shadow_mesh_components(source)) == 2
    assert len(preview.plan_reverse_shadow_preview_faces(source, {"average_ground_level_elevation_m": 0})["components"]) == 2


def test_zero_height_has_no_valid_volume():
    with pytest.raises(ValueError, match="reverse_shadow_preview_no_valid_volume"):
        preview.plan_reverse_shadow_preview_faces(_core(height=0), {"average_ground_level_elevation_m": 0})


def test_unused_null_unbounded_grid_point_is_ignored():
    source = _core()
    source["height_field"]["grid_points"].append({
        "grid_index": 9999, "x_m": 100, "y_m": 100,
        "bounded": False, "height_limit_m": None})
    plan = preview.plan_reverse_shadow_preview_faces(
        source, {"average_ground_level_elevation_m": 0})
    assert 9999 not in plan["vertices"]


def _ring_core():
    coordinates = [(0, 0), (3, 0), (3, 3), (0, 3),
                   (1, 1), (2, 1), (2, 2), (1, 2)]
    triangles = [(0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
                 (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    return {"available": True, "complete": True, "method": preview.METHOD,
        "height_field": {"grid_points": [
            {"grid_index": index, "x_m": xy[0], "y_m": xy[1], "height_limit_m": 2}
            for index, xy in enumerate(coordinates)]},
        "top_surface_mesh": {
            "triangles": [{"vertex_grid_indices": list(ids)} for ids in triangles],
            "top_surface_boundary_loops": [
                {"closed": True, "vertex_grid_indices": [0, 1, 2, 3, 0],
                 "signed_plan_area_m2": 9, "orientation": "counter_clockwise"},
                {"closed": True, "vertex_grid_indices": [4, 7, 6, 5, 4],
                 "signed_plan_area_m2": -1, "orientation": "clockwise"}]}}


def test_hole_boundary_winding_and_outward_side_normal_are_preserved():
    plan = preview.plan_reverse_shadow_preview_faces(
        _ring_core(), {"average_ground_level_elevation_m": 0})
    component = plan["components"][0]
    assert len(plan["components"]) == 1
    assert (plan["top_face_count"], plan["bottom_face_count"],
            plan["side_face_count"]) == (8, 8, 16)
    # The first hole side follows source edge 4 -> 7 (clockwise loop). Its
    # horizontal outward normal points +X, into the hole, not into the solid.
    assert component["side_faces"][8] == (
        (4, "top"), (4, "bottom"), (7, "bottom"))
    a = plan["vertices"][4]; b = plan["vertices"][7]
    edge_dx, edge_dy = b["x_m"] - a["x_m"], b["y_m"] - a["y_m"]
    horizontal_normal = (2 * edge_dy, -2 * edge_dx)
    assert horizontal_normal[0] > 0 and horizontal_normal[1] == 0


def test_off_and_api_unavailable_preserve_certification(monkeypatch):
    off = preview.build_reverse_shadow_preview(_core(), {"average_ground_level_elevation_m": 0}, {})
    assert not off["attempted"] and not off["permit_ready_certified"]
    monkeypatch.setattr(preview, "DocumentManager", None)
    result = preview.build_reverse_shadow_preview(_core(), {"average_ground_level_elevation_m": 0},
                                                  {"reverse_shadow_preview_mode": "replace"})
    assert not result["available"]
    assert result["blockers"][0]["failure_code"] == "reverse_shadow_preview_api_unavailable"
    assert result["legal_judgement_generated"] is result["ordinance_selection_certified"] is result["permit_ready_certified"] is False
