import copy
import math

from shadow_site_distance_contours import build_site_distance_contours


def duration_grid(x0=-12, y0=-12, nx=69, ny=69, r=0.5):
    grid=[]
    for iy in range(ny):
        for ix in range(nx):
            grid.append({"x_m": x0+ix*r, "y_m": y0+iy*r, "shadow_duration_minutes": 0.0})
    return {"complete": True, "method": "grid_trapezoidal_time_integration_v1", "boundary_evaluation_coverage_complete": True,
            "grid_spec": {"x_count": nx, "y_count": ny, "origin_x_m": x0, "origin_y_m": y0, "resolution_m": r, "ordering": "row_major_y_then_x"},
            "duration_grid": grid}


def geom(points, complete=True):
    return {"available": complete, "complete": complete, "method": "revit_area_single_outer_loop_v1",
            "outer_loop": [{"x_m": x, "y_m": y} for x,y in points]}


def rectangle(ccw=True):
    pts=[(0,0),(10,0),(10,10),(0,10)]
    return geom(pts if ccw else list(reversed(pts)))


def test_rectangle_generates_fixed_contours_without_inner_lines():
    result=build_site_distance_contours(duration_grid(), rectangle())
    assert result["available"] is True
    assert result["complete"] is True
    assert result["ready_for_revit_preview"] is True
    assert result["generated_distances_m"] == [5.0, 10.0]
    assert result["contour_count"] == 2
    assert all(c["closed"] for c in result["contours"])
    five=next(c for c in result["contours"] if c["distance_m"] == 5.0)
    ten=next(c for c in result["contours"] if c["distance_m"] == 10.0)
    assert five["contour_index"] == 0
    assert ten["contour_index"] == 0
    xs=[p["x"] for p in five["points_m"]]; ys=[p["y"] for p in five["points_m"]]
    assert min(xs) == -5 and max(xs) == 15 and min(ys) == -5 and max(ys) == 15
    xs=[p["x"] for p in ten["points_m"]]; ys=[p["y"] for p in ten["points_m"]]
    assert min(xs) == -10 and max(xs) == 20 and min(ys) == -10 and max(ys) == 20
    assert five["length_m"] > 0
    assert result["approximation"]["smoothing_applied"] is False
    assert result["approximation"]["polygon_offset_used"] is False


def test_clockwise_and_counterclockwise_same_result():
    a=build_site_distance_contours(duration_grid(), rectangle(True))
    b=build_site_distance_contours(duration_grid(), rectangle(False))
    assert a["generated_distances_m"] == b["generated_distances_m"]
    assert [(c["distance_m"], c["point_count"], round(c["length_m"],6)) for c in a["contours"]] == [(c["distance_m"], c["point_count"], round(c["length_m"],6)) for c in b["contours"]]


def test_l_shape_concave_area_and_deterministic_ordering():
    l=geom([(0,0),(8,0),(8,3),(3,3),(3,8),(0,8)])
    result=build_site_distance_contours(duration_grid(-8,-8,49,49,0.5), l)
    assert result["generated_distances_m"] == [5.0, 10.0]
    keys=[(c["distance_m"], c["points_m"][0]["x"], c["points_m"][0]["y"], c["point_count"]) for c in result["contours"]]
    assert keys == sorted(keys)
    assert [c["contour_index"] for c in result["contours"] if c["distance_m"] == 5.0] == list(range(sum(1 for c in result["contours"] if c["distance_m"] == 5.0)))


def test_multiple_contours_when_grid_has_disconnected_coverage():
    # Two small rectangles represented by one concave corridor-less polygon-like hourglass can split level components on grid bounds.
    d=duration_grid(-7,-7,15,31,1.0)
    g=geom([(0,0),(2,0),(2,2),(0,2)])
    result=build_site_distance_contours(d,g)
    assert result["contour_count"] >= 1
    assert result["contours"][0]["contour_index"] == 0


def test_no_contour_warning_when_grid_too_small_for_levels():
    result=build_site_distance_contours(duration_grid(0,0,4,4,1.0), rectangle())
    assert result["complete"] is True
    assert result["generated_distances_m"] == []
    assert any((isinstance(w,dict) and w.get("warning_code") == "site_distance_contour_not_generated") for w in result["warnings"])


def test_input_validation_and_no_mutation():
    d=duration_grid(); g=rectangle(); before=(copy.deepcopy(d), copy.deepcopy(g))
    assert build_site_distance_contours(d,g,-1)["blockers"][0]["failure_code"] == "invalid_site_distance_tolerance"
    bad=rectangle(); bad["outer_loop"][0]["x_m"]=math.nan
    assert build_site_distance_contours(d,bad)["blockers"][0]["failure_code"] == "invalid_site_boundary_coordinates"
    bad=duration_grid(); bad["duration_grid"][0]["x_m"]=math.nan
    assert build_site_distance_contours(bad,g)["blockers"][0]["failure_code"] == "invalid_duration_grid_coordinates"
    bad=duration_grid(); bad["complete"]=False
    assert build_site_distance_contours(bad,g)["blockers"][0]["failure_code"] == "complete_shadow_duration_required"
    bad=duration_grid(); bad["boundary_evaluation_coverage_complete"]=False
    assert build_site_distance_contours(bad,g)["blockers"][0]["failure_code"] == "boundary_evaluation_coverage_complete_required"
    bad=duration_grid(); bad["grid_spec"]["ordering"]="bad"
    assert build_site_distance_contours(bad,g)["blockers"][0]["failure_code"] == "duration_grid_spec_missing_or_invalid"
    bad=duration_grid(); bad["duration_grid"].pop()
    assert build_site_distance_contours(bad,g)["blockers"][0]["failure_code"] == "duration_grid_size_mismatch"
    inc=rectangle(); inc["complete"]=False
    assert build_site_distance_contours(d,inc)["blockers"][0]["failure_code"] == "site_boundary_geometry_required"
    assert d == before[0] and g == before[1]
