import math
from shadow_reverse_low_rise import (_boundary_loops, _cell_crossed_by_boundary,
                                     _atomic_cell_height_limits, _candidate_height, _compile_sun_fan, _constraint,
                                     build_midday_sunlight_interval,
                                     build_sunlight_interval_candidates,
                                     evaluate_adjacent_ray_facet,
                                     _quantize_height)


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


def test_conservative_half_meter_height_quantization_handles_float_boundary():
    assert _quantize_height(12.93, 0.5) == 12.5
    assert _quantize_height(12.50, 0.5) == 12.5
    assert _quantize_height(12.500000000000002, 0.5) == 12.5
    assert _quantize_height(-0.1, 0.5) == 0.0


def test_compiled_fan_matches_on_demand_compilation_and_exact_pruning():
    fan = {"samples": [
        {"sun_azimuth_model_unwrapped_deg": 100.0, "true_solar_minutes": 600,
         "ray_vector_model": {"x": .984807753, "y": -.173648178, "z": 1.0}},
        {"sun_azimuth_model_unwrapped_deg": 110.0, "true_solar_minutes": 615,
         "ray_vector_model": {"x": .939692621, "y": -.342020143, "z": 1.0}}]}
    measurement = {"x_m": 0.0, "y_m": 0.0, "measurement_point_index": 0}
    point = (9.659258263, -2.588190451)
    compiled = _compile_sun_fan(fan)
    assert _constraint(point, measurement, fan, 4.0) == _constraint(
        point, measurement, fan, 4.0, compiled)

    outside = {"x_m": 0.0, "y_m": -10.0, "measurement_point_index": 1}
    candidate = {"sun_ray_fan": fan, "compiled_sun_fan": compiled}
    counts = {"actually_evaluated_constraint_count": 0,
              "azimuth_pruned_constraint_count": 0, "maximum": 10, "limit_exceeded": False}
    pruned = _candidate_height(point, [measurement, outside], candidate, 4.0, .5,
                               evaluation_counts=counts, pruning=True)
    unpruned = _candidate_height(point, [measurement, outside], candidate, 4.0, .5,
                                 pruning=False)
    assert pruned == unpruned
    assert counts["azimuth_pruned_constraint_count"] == 1
    assert counts["actually_evaluated_constraint_count"] == 1


def test_atomic_constraint_evaluation_honors_shared_budget_without_fallback():
    fan = {"samples": [
        {"sun_azimuth_model_unwrapped_deg": 0.0, "true_solar_minutes": 480,
         "ray_vector_model": {"x": 0.0, "y": 0.7, "z": 0.7}},
        {"sun_azimuth_model_unwrapped_deg": 90.0, "true_solar_minutes": 495,
         "ray_vector_model": {"x": 0.7, "y": 0.0, "z": 0.7}}]}
    candidate = {"compiled_sun_fan": _compile_sun_fan(fan), "sun_ray_fan": fan,
                 "sun_facet_count": 1}
    counts = {"actually_evaluated_constraint_count": 0,
              "atomic_constraint_evaluation_count": 0,
              "v2_exact_constraint_evaluation_count": 0,
              "maximum": 0, "limit_exceeded": False}
    limits = _atomic_cell_height_limits((1.0, 0.0), [
        {"x_m": 0.0, "y_m": 0.0, "measurement_point_index": 0}],
        candidate, 4.0, 0.5, counts)
    assert limits == [None]
    assert counts["limit_exceeded"] is True
    assert counts["actually_evaluated_constraint_count"] == 0
