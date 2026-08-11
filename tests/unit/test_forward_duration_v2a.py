import shadow_duration as duration
from shadow_performance import ForwardPerformanceRecorder, select_duration_chunk_size


def _polygon(points, role="outer", component=0):
    return {"role": role, "component_index": component,
        "points_m": [{"x": x, "y": y} for x, y in points]}


def _unified():
    outer = _polygon([(0, 0), (6, 0), (6, 5), (0, 5)])
    hole = _polygon([(2, 1), (4, 1), (4, 3), (2, 3)], "inner")
    other = _polygon([(8, 0), (9, 0), (9, 1), (8, 1)], component=1)
    shifted = _polygon([(1, 0), (7, 0), (7, 5), (1, 5)])
    samples = [("08:00", [outer, hole, other]), ("08:17", [outer, hole, other]),
        ("08:49", [shifted]), ("09:30", [outer, hole, other])]
    return {"complete": True, "slices": [{"complete": True, "true_solar_time": time,
        "polygons": polygons} for time, polygons in samples]}


SETTINGS = {"grid_resolution_m": 1, "analysis_margin_m": 0,
    "max_duration_grid_points": 1000}


def test_chunk_and_bbox_invariance_preserves_small_grid_contract():
    baseline = duration.build_shadow_duration(_unified(), SETTINGS, chunk_size=4096,
        bbox_pruning=False)
    for size in (4096, 8192, 32768):
        result = duration.build_shadow_duration(_unified(), SETTINGS, chunk_size=size)
        assert result["duration_grid"] == baseline["duration_grid"]
        assert result["maximum_shadow_duration_minutes"] == baseline["maximum_shadow_duration_minutes"]
        assert result["shadowed_point_count"] == baseline["shadowed_point_count"]
        assert result["grid_spec"]["ordering"] == "row_major_y_then_x"
        assert result["engine_diagnostics"]["compact_buffer_type"] == "array('d')"
        assert result["engine_diagnostics"]["per_point_states_list_used"] is False
    lookup = {(p["x_m"], p["y_m"]): p["shadow_duration_minutes"]
        for p in baseline["duration_grid"]}
    assert lookup[(0.0, 0.0)] > 0.0  # polygon boundary remains included
    assert lookup[(3.0, 2.0)] < lookup[(1.0, 2.0)]  # hole semantics remain active


def test_legacy_states_reference_parity_for_irregular_intervals():
    source = _unified()
    result = duration.build_shadow_duration(source, SETTINGS, chunk_size=8192)
    minutes = [duration._minutes(item["true_solar_time"]) for item in source["slices"]]
    compiled = [duration._compile_slice_polygons(item["polygons"])
        for item in source["slices"]]
    expected = []
    for point in result["duration_grid"]:
        states = [duration._compiled_slice_contains(item, point["x_m"], point["y_m"], False)
            for item in compiled]
        expected.append(duration.integrate_shadow_states_trapezoidal(states, minutes))
    assert [point["shadow_duration_minutes"] for point in result["duration_grid"]] == expected


def test_memory_aware_chunk_policy_low_medium_high_and_invalid():
    gib = 1024 ** 3
    assert select_duration_chunk_size({"telemetry_available": True,
        "available_physical_memory_bytes": gib // 2})["selected_chunk_size"] == 4096
    assert select_duration_chunk_size({"telemetry_available": True,
        "available_physical_memory_bytes": 2 * gib})["selected_chunk_size"] == 8192
    assert select_duration_chunk_size({"telemetry_available": True,
        "available_physical_memory_bytes": 8 * gib})["selected_chunk_size"] == 32768
    fallback = select_duration_chunk_size({"telemetry_available": False,
        "available_physical_memory_bytes": None})
    assert fallback["selected_chunk_size"] == 8192
    assert fallback["fallback_used"] is True


def test_telemetry_failure_is_non_fatal_and_json_safe():
    def fail():
        raise RuntimeError("telemetry unavailable")
    recorder = ForwardPerformanceRecorder(fail)
    recorder.begin("shadow_duration")
    recorder.end("shadow_duration")
    diagnostic = recorder.result()
    assert diagnostic["stages"]["shadow_duration"]["elapsed_ms"] >= 0
    assert diagnostic["stages"]["shadow_duration"]["process_working_set_after_bytes"] is None
