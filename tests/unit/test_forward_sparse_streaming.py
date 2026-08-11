from shadow_contours import build_equal_time_contours
from shadow_duration import build_shadow_duration
from shadow_site_distance_contours import build_site_distance_contours
from shadow_site_masks import build_measurement_masks


def polygon(points, role="outer", component=0):
    return {"role": role, "component_index": component,
            "points_m": [{"x": x, "y": y} for x, y in points]}


def slices(polygons):
    return {"complete": True, "slices": [
        {"complete": True, "true_solar_time": "08:00", "polygons": polygons},
        {"complete": True, "true_solar_time": "08:17", "polygons": polygons},
        {"complete": True, "true_solar_time": "08:51", "polygons": polygons},
    ]}


def site():
    return {"complete": True, "method": "fixture", "outer_loop": [
        {"x_m": -20, "y_m": -20}, {"x_m": 20, "y_m": -20},
        {"x_m": 20, "y_m": 20}, {"x_m": -20, "y_m": 20}]}


def test_sparse_tiles_match_dense_with_components_hole_boundaries_and_diagonal():
    shapes = [
        polygon([(-8,-4), (2,-4), (2,5), (-8,5)]),
        polygon([(-4,-1), (0,-1), (0,2), (-4,2)], "inner"),
        polygon([(7,-8), (8,-8), (15,8), (14,8)], component=1),
    ]
    settings = {"grid_resolution_m": 1, "analysis_margin_m": 3}
    dense = build_shadow_duration(slices(shapes), settings, sparse_tiles=False)
    for tile_size in (16, 32, 64):
        sparse = build_shadow_duration(slices(shapes), settings, sparse_tiles=True,
                                       tile_size_cells=tile_size)
        assert sparse["duration_grid"] == dense["duration_grid"]
        assert sparse["maximum_shadow_duration_minutes"] == dense["maximum_shadow_duration_minutes"]
        assert sparse["shadowed_point_count"] == dense["shadowed_point_count"]
        for a, b in zip(dense["duration_grid"], sparse["duration_grid"]):
            if a["shadow_duration_minutes"] > 0:
                assert b["shadow_duration_minutes"] > 0


def test_large_grid_compact_field_drives_streaming_consumers():
    tiny = [polygon([(0,0), (2,0), (2,2), (0,2)])]
    public, field = build_shadow_duration(
        slices(tiny), {"grid_resolution_m": 1, "analysis_margin_m": 250},
        return_internal=True)
    assert public["grid_point_count"] == 253009
    assert public["storage_mode"] == "compact_large_v1"
    assert public["duration_grid_materialized"] is False
    assert public["duration_grid"] == []
    assert field.logical_point_count == 253009
    assert public["engine_diagnostics"]["compact_buffer_bytes"] == 253009 * 8
    contours = build_equal_time_contours(public, {"equal_time_contour_levels_minutes": [10]}, field)
    masks = build_measurement_masks(public, site(), duration_field=field)
    distances = build_site_distance_contours(public, site(), duration_field=field)
    assert contours["complete"] and contours["scalar_copy_materialized"] is False
    assert masks["complete"] and masks["streaming"] is True
    assert distances["complete"] and distances["row_streaming"] is True
    assert sum(masks["zone_counts"].values()) == 253009


def test_high_precision_large_grid_keeps_requested_accuracy_on_compact_path():
    tiny = [polygon([(0,0), (2,0), (2,2), (0,2)])]
    high_slices = {"complete": True, "slices": [
        {"complete": True, "true_solar_time": value, "polygons": tiny}
        for value in ("08:00", "08:05", "08:10")]}
    public, field = build_shadow_duration(
        high_slices, {"grid_resolution_m": .25, "sun_time_step_minutes": 5,
                       "analysis_margin_m": 63, "max_duration_grid_points": 1000000},
        selected_accuracy_preset="high", return_internal=True)
    assert public["complete"] is True
    assert public["storage_mode"] == "compact_large_v1"
    assert public["spatial_resolution_m"] == .25
    assert public["temporal_step_minutes"] == 5
    assert public["engine_diagnostics"]["automatic_accuracy_fallback_used"] is False
    assert field.logical_point_count == public["grid_point_count"]


def test_small_compact_consumers_match_legacy_including_zero_tie_breaks():
    shapes = [polygon([(0,0), (2,0), (2,2), (0,2)])]
    public, field = build_shadow_duration(
        slices(shapes), {"grid_resolution_m": 1, "analysis_margin_m": 20},
        return_internal=True)
    contour_settings = {"equal_time_contour_levels_minutes": [10, 30]}
    legacy_contours = build_equal_time_contours(public, contour_settings)
    compact_contours = build_equal_time_contours(public, contour_settings, field)
    for key in ("requested_levels_minutes", "generated_levels_minutes", "contour_count",
                "closed_contour_count", "open_contour_count", "contours"):
        assert compact_contours[key] == legacy_contours[key]

    zero_site = {"complete": True, "method": "fixture", "outer_loop": [
        {"x_m": -2, "y_m": -2}, {"x_m": 2, "y_m": -2},
        {"x_m": 2, "y_m": 2}, {"x_m": -2, "y_m": 2}]}
    legacy_masks = build_measurement_masks(public, zero_site)
    compact_masks = build_measurement_masks(public, zero_site, duration_field=field)
    assert compact_masks["zone_counts"] == legacy_masks["zone_counts"]
    assert compact_masks["near"] == legacy_masks["near"]
    assert compact_masks["far"] == legacy_masks["far"]
    assert compact_masks["near"]["maximum_shadow_duration_minutes"] == 0
    assert compact_masks["far"]["maximum_shadow_duration_minutes"] == 0

    legacy_distance = build_site_distance_contours(public, zero_site)
    compact_distance = build_site_distance_contours(public, zero_site, duration_field=field)
    for key in ("generated_distances_m", "contour_count", "closed_contour_count",
                "open_contour_count", "contours"):
        assert compact_distance[key] == legacy_distance[key]


def test_tile_boundary_downstream_results_are_invariant():
    moving = {"complete": True, "slices": [
        {"complete": True, "true_solar_time": "08:00", "polygons": [
            polygon([(14,1), (18,1), (18,7), (14,7)])]},
        {"complete": True, "true_solar_time": "08:17", "polygons": [
            polygon([(30,2), (34,2), (34,8), (30,8)])]},
        {"complete": True, "true_solar_time": "08:51", "polygons": [
            polygon([(62,3), (66,3), (66,9), (62,9)])]},
    ]}
    settings = {"grid_resolution_m": 1, "analysis_margin_m": 20,
                "equal_time_contour_levels_minutes": [10]}
    outputs = []
    zero_site = {"complete": True, "method": "fixture", "outer_loop": [
        {"x_m": (0), "y_m": -5}, {"x_m": 10, "y_m": -5},
        {"x_m": 10, "y_m": 15}, {"x_m": 0, "y_m": 15}]}
    for tile_size in (16, 32, 64):
        public, field = build_shadow_duration(moving, settings, return_internal=True,
                                              tile_size_cells=tile_size)
        outputs.append((public["duration_grid"],
                        build_equal_time_contours(public, settings, field)["contours"],
                        build_measurement_masks(public, zero_site, duration_field=field)))
    assert outputs[1] == outputs[0]
    assert outputs[2] == outputs[0]


def test_materialization_limit_is_independent_from_configured_large_limit():
    public, field = build_shadow_duration(
        slices([polygon([(0,0), (2,0), (2,2), (0,2)])]),
        {"grid_resolution_m": 1, "analysis_margin_m": 250,
         "max_duration_grid_points": 1000000}, return_internal=True)
    assert public["grid_point_count"] == 253009
    assert public["duration_grid_materialized"] is False
    assert public["small_grid_materialization_limit"] == 250000
    assert public["large_grid_hard_point_cap"] == 2000000
    assert field.logical_point_count == 253009


def test_large_grid_hard_point_cap_has_dedicated_blocker():
    result = build_shadow_duration(
        slices([polygon([(0,0), (2,0), (2,2), (0,2)])]),
        {"grid_resolution_m": 1, "analysis_margin_m": 710})
    assert result["complete"] is False
    assert result["blockers"][0]["failure_code"] == "large_grid_hard_point_cap_exceeded"


def test_contour_segment_guards_use_conservative_memory_budget():
    public, field = build_shadow_duration(
        slices([polygon([(0,0), (4,0), (4,4), (0,4)])]),
        {"grid_resolution_m": 1, "analysis_margin_m": 3}, return_internal=True)
    public["engine_diagnostics"]["memory_budget_bytes"] = 512
    contour = build_equal_time_contours(
        public, {"equal_time_contour_levels_minutes": [10]}, field)
    guard_site = {"complete": True, "method": "fixture", "outer_loop": [
        {"x_m": 0, "y_m": 0}, {"x_m": 1, "y_m": 0},
        {"x_m": 1, "y_m": 1}, {"x_m": 0, "y_m": 1}]}
    distance = build_site_distance_contours(public, guard_site, duration_field=field)
    assert contour["complete"] is False
    assert contour["blockers"][0]["failure_code"] == "equal_time_contour_segment_budget_exceeded"
    assert distance["complete"] is False
    assert distance["blockers"][0]["failure_code"] == "site_distance_contour_segment_budget_exceeded"
