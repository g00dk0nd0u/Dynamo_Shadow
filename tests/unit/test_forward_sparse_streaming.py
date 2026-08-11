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
