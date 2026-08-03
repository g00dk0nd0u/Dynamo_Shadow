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
