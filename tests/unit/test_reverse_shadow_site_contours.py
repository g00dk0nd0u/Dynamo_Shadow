from shadow_site_distance_contours import build_site_distance_contours_from_site


def _site(points):
    return {"complete": True, "method": "fixture", "outer_loop": [{"x_m": x, "y_m": y} for x, y in points]}


def test_rectangle_and_concave_site_only_contours_are_closed():
    for points in ([(0,0),(10,0),(10,10),(0,10)], [(0,0),(8,0),(8,3),(3,3),(3,8),(0,8)]):
        result = build_site_distance_contours_from_site(_site(points))
        assert result["complete"] and result["generated_distances_m"] == [5.0, 10.0]
        assert result["source"]["grid_source"] == "site_boundary_generated_grid"
        assert result["grid_spec"]["resolution_m"] == 1.0
        assert all(item["closed"] for item in result["contours"])


def test_site_only_grid_guard_does_not_fallback():
    result = build_site_distance_contours_from_site(_site([(0,0),(10,0),(10,10),(0,10)]), maximum_grid_point_count=10)
    assert result["blockers"][0]["failure_code"] == "site_distance_generated_grid_limit_exceeded"
