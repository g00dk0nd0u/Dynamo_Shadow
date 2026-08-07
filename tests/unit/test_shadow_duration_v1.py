import shadow_duration as duration


def polygon(points, role="outer", component=0):
    return {"closed": True, "role": role, "component_index": component,
        "points_m": [{"x": x, "y": y} for x, y in points]}


def unified(slices):
    return {"complete": True, "slices": [{"complete": True, "true_solar_time": time, "polygons": polygons}
        for time, polygons in slices]}


RECT = polygon([(0, 0), (2, 0), (2, 2), (0, 2)])


def test_static_rectangle_accumulates_full_interval():
    result = duration.build_shadow_duration(unified([("08:00", [RECT]), ("08:30", [RECT])]),
        {"grid_resolution_m": 1, "analysis_margin_m": 0, "max_duration_grid_points": 100})
    assert result["complete"] and result["maximum_shadow_duration_minutes"] == 30
    assert result["shadowed_point_count"] == 9
    assert result["grid_spec"]["ordering"] == "row_major_y_then_x"
    assert result["grid_spec"]["x_count"] * result["grid_spec"]["y_count"] == len(result["duration_grid"])


def test_entering_or_leaving_point_uses_trapezoidal_half_interval():
    shifted = polygon([(10, 10), (12, 10), (12, 12), (10, 12)])
    result = duration.build_shadow_duration(unified([("08:00", [RECT]), ("08:30", [shifted])]),
        {"grid_resolution_m": 1, "analysis_margin_m": 0, "max_duration_grid_points": 1000})
    origin = next(p for p in result["duration_grid"] if p["x_m"] == 0 and p["y_m"] == 0)
    assert origin["shadow_duration_minutes"] == 15


def test_inner_loop_is_unshadowed_and_multiple_components_are_supported():
    outer = polygon([(0, 0), (4, 0), (4, 4), (0, 4)])
    inner = polygon([(1, 1), (3, 1), (3, 3), (1, 3)], "inner")
    other = polygon([(6, 0), (7, 0), (7, 1), (6, 1)], component=1)
    result = duration.build_shadow_duration(unified([("08:00", [outer, inner, other]), ("08:30", [outer, inner, other])]),
        {"grid_resolution_m": 1, "analysis_margin_m": 0, "max_duration_grid_points": 1000})
    lookup = {(p["x_m"], p["y_m"]): p["shadow_duration_minutes"] for p in result["duration_grid"]}
    assert lookup[(2, 2)] == 0
    assert lookup[(6, 0)] == 30


def test_grid_limit_stops_before_allocation():
    result = duration.build_shadow_duration(unified([("08:00", [RECT]), ("08:30", [RECT])]),
        {"grid_resolution_m": .01, "analysis_margin_m": 0, "max_duration_grid_points": 10})
    assert not result["available"] and result["duration_grid"] == []
    assert result["blockers"][0]["failure_code"] == "max_duration_grid_points_exceeded"
    assert result["requested_grid_point_count"] > result["maximum_grid_point_count"]
    assert result["spatial_resolution_m"] == .01


def _legacy_slice_contains(polygons, x, y):
    groups = {}
    for item in polygons:
        points = [(float(p["x"]), float(p["y"])) for p in item.get("points_m", [])]
        if len(points) < 3:
            continue
        key = item.get("component_index", item.get("classification_group_key", 0))
        groups.setdefault(key, []).append((item.get("role"), points))
    for loops in groups.values():
        outers = [points for role, points in loops if role == "outer"]
        inners = [points for role, points in loops if role == "inner"]
        if (any(duration._inside_loop(x, y, outer) for outer in outers)
                and not any(duration._inside_loop(x, y, inner) for inner in inners)):
            return True
    return False


def test_compiled_slice_containment_matches_legacy_reference():
    polygons = [
        polygon([(0, 0), (4, 0), (4, 4), (0, 4)]),
        polygon([(1, 1), (3, 1), (3, 3), (1, 3)], "inner"),
        polygon([(6, 0), (8, 0), (8, 2), (6, 2)], component=1),
        polygon([(20, 20), (21, 20)]),
        polygon([], component=2),
    ]
    compiled = duration._compile_slice_polygons(polygons)
    samples = [
        (0, 0),       # outer boundary
        (0.000001, 2),
        (-0.000001, 2),
        (1, 2),       # hole boundary
        (2, 2),       # hole interior
        (3.000001, 2),
        (6, 1),       # second component boundary
        (7, 1),       # second component interior
        (8.000001, 1),
        (20, 20),     # invalid short loop must be ignored
    ]
    for x, y in samples:
        assert duration._compiled_slice_contains(compiled, x, y) == _legacy_slice_contains(polygons, x, y)


def test_compilation_keeps_duration_result_contract_unchanged():
    outer = polygon([(0, 0), (4, 0), (4, 4), (0, 4)])
    inner = polygon([(1, 1), (3, 1), (3, 3), (1, 3)], "inner")
    other = polygon([(6, 0), (7, 0), (7, 1), (6, 1)], component=1)
    result = duration.build_shadow_duration(
        unified([("08:00", [outer, inner, other]), ("08:30", [RECT])]),
        {"grid_resolution_m": 1, "analysis_margin_m": 0, "max_duration_grid_points": 1000},
    )
    assert result["duration_grid"][:3] == [
        {"x_m": 0.0, "y_m": 0.0, "shadow_duration_minutes": 30.0},
        {"x_m": 1.0, "y_m": 0.0, "shadow_duration_minutes": 30.0},
        {"x_m": 2.0, "y_m": 0.0, "shadow_duration_minutes": 30.0},
    ]
    assert result["maximum_shadow_duration_minutes"] == 30.0
    assert result["shadowed_point_count"] == 24
    assert result["grid_spec"] == {
        "x_count": 8,
        "y_count": 5,
        "origin_x_m": 0.0,
        "origin_y_m": 0.0,
        "resolution_m": 1.0,
        "ordering": "row_major_y_then_x",
    }
