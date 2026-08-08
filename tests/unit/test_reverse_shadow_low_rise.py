import math
from shadow_reverse_low_rise import (_boundary_loops, _cell_crossed_by_boundary,
                                     build_midday_sunlight_interval,
                                     build_sunlight_interval_candidates,
                                     evaluate_adjacent_ray_facet)


def test_midday_interval_example():
    value = build_midday_sunlight_interval(480, 960, 180)
    assert value["required_sunlight_minutes"] == 300
    assert (value["sunlight_start_minutes"], value["sunlight_end_minutes"]) == (570, 870)


def test_interval_candidates_include_center_endpoints_and_keep_duration():
    value = build_sunlight_interval_candidates(480, 960, 240, 15)
    intervals = [(item["sunlight_start_minutes"], item["sunlight_end_minutes"])
                 for item in value["candidates"]]
    assert intervals[0] == (480, 720) and intervals[-1] == (720, 960)
    assert (600, 840) in intervals
    assert intervals == sorted(set(intervals))
    assert all(end-start == 240 and start >= 480 and end <= 960 for start, end in intervals)


def test_analytic_facet_45_degrees():
    h = math.sqrt(.5)
    ray0 = {"x": 0, "y": h, "z": h}
    ray1 = {"x": .01, "y": math.sqrt(.5-.0001), "z": h}
    value = evaluate_adjacent_ray_facet((0,0), (0,10), ray0, ray1)
    assert math.isclose(4 + value["delta_z_m"], 14, abs_tol=1e-9)
    assert value["conservative_endpoint_altitude_clamp_applied"]


def test_concave_boundary_crossing_cell_is_detected_but_edge_touch_is_not():
    crossing = [(0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2)]
    assert _cell_crossed_by_boundary(0, 0, 2, 2, crossing)
    square = [(0, 0), (2, 0), (2, 2), (0, 2)]
    assert not _cell_crossed_by_boundary(0, 0, 2, 2, square)


def test_oriented_boundary_loop_is_closed_and_deterministic():
    grid = [{"x_m": 0, "y_m": 0}, {"x_m": 1, "y_m": 0},
            {"x_m": 1, "y_m": 1}, {"x_m": 0, "y_m": 1}]
    loops = _boundary_loops([(0, 1), (1, 2), (2, 3), (3, 0)], grid)
    assert loops[0]["vertex_grid_indices"] == [0, 1, 2, 3, 0]
    assert loops[0]["closed"] and loops[0]["orientation"] == "counter_clockwise"
    assert loops[0]["signed_plan_area_m2"] == 1
