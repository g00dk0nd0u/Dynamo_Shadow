import shadow_duration as duration
from shadow_performance import (ForwardPerformanceRecorder, get_process_memory_snapshot,
    build_accuracy_performance_summary, select_duration_chunk_size)


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


def test_chunk_invariance_crosses_real_chunk_boundaries():
    rectangle = _polygon([(0, 0), (100, 0), (100, 99), (0, 99)])
    source = {"complete": True, "slices": [
        {"complete": True, "true_solar_time": "08:00", "polygons": [rectangle]},
        {"complete": True, "true_solar_time": "08:30", "polygons": [rectangle]}]}
    settings = {"grid_resolution_m": 1, "analysis_margin_m": 0,
        "max_duration_grid_points": 20000}
    results = [duration.build_shadow_duration(source, settings, chunk_size=size)
        for size in (4096, 8192, 32768)]
    assert results[0]["grid_point_count"] == 10100
    assert results[0]["engine_diagnostics"]["chunk_count"] == 3
    assert results[1]["engine_diagnostics"]["chunk_count"] == 2
    assert results[0]["engine_diagnostics"]["chunk_count"] > 1
    for result in results[1:]:
        assert result["duration_grid"] == results[0]["duration_grid"]
        assert result["maximum_shadow_duration_minutes"] == results[0]["maximum_shadow_duration_minutes"]
        assert result["shadowed_point_count"] == results[0]["shadowed_point_count"]
        assert result["grid_spec"] == results[0]["grid_spec"]


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


def test_stage_clock_excludes_snapshot_overhead_in_deterministic_order():
    events = []
    times = iter((10.0, 20.0, 23.5, 30.0))
    snapshots = iter((100, 200, 300, 400))

    def clock():
        events.append("clock")
        return next(times)

    def snapshot():
        events.append("snapshot")
        value = next(snapshots)
        return {"process_working_set_bytes": value}

    recorder = ForwardPerformanceRecorder(snapshot, clock)
    recorder.begin("stage")
    recorder.end("stage")
    result = recorder.result()
    assert events == ["snapshot", "clock", "snapshot", "clock",
        "clock", "snapshot", "clock", "snapshot"]
    assert result["stages"]["stage"]["elapsed_ms"] == 3500.0
    assert result["stages"]["total"]["process_working_set_before_bytes"] == 100
    assert result["stages"]["total"]["process_working_set_after_bytes"] == 400


def test_platform_memory_snapshot_is_non_fatal_and_separates_sources():
    snapshot = get_process_memory_snapshot()
    assert "physical_memory_telemetry_available" in snapshot
    assert "process_memory_telemetry_available" in snapshot
    assert snapshot["total_physical_memory_bytes"] is None or snapshot["total_physical_memory_bytes"] > 0


def test_accuracy_performance_summary_reuses_compact_existing_telemetry():
    performance = {"memory_at_start": {"available_physical_memory_bytes": 900},
        "memory": {"process_lifetime_peak_working_set_bytes": 800},
        "stages": {"formal_projection": {"elapsed_ms": 1.5}, "total": {
            "elapsed_ms": 9.0, "process_working_set_before_bytes": 100,
            "process_working_set_after_bytes": 200}},
        "workload_summary": {"time_sample_count": 97,
            "logical_grid_point_count": 100000, "active_evaluation_point_count": 20000,
            "selected_active_tile_count": 8, "active_tile_ratio": 0.08,
            "selected_chunk_size": 8192, "storage_mode": "compact_large_v1",
            "compact_buffer_bytes": 160000}}
    result = build_accuracy_performance_summary(
        {"preset_id": "high", "grid_resolution_m": .25,
         "sun_time_step_minutes": 5}, performance,
        {"near": {"maximum_shadow_duration_minutes": 120},
         "far": {"maximum_shadow_duration_minutes": 60}})
    assert result["display_mode"] == "High / 高精度"
    assert result["time_sample_count"] == 97
    assert result["storage_mode"] == "compact_large_v1"
    assert result["grid_resolution_m"] == .25
    assert result["sun_time_step_minutes"] == 5
    assert result["automatic_accuracy_fallback_used"] is False
    assert result["process_lifetime_peak_working_set_bytes_at_end"] == 800
