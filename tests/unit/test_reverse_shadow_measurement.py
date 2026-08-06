from shadow_reverse_measurement import build_reverse_shadow_measurement_points


def test_closed_contours_are_normalized_and_resampled():
    contours = {"complete": True, "contours": [
        {"distance_m": 10.0, "closed": True, "contour_index": 0, "points_m": [{"x": 0, "y": 0},{"x": 0,"y": 4},{"x": 4,"y": 4},{"x": 4,"y": 0},{"x": 0,"y": 0}]},
        {"distance_m": 5.0, "closed": True, "contour_index": 0, "points_m": [{"x": 0, "y": 0},{"x": 4,"y": 0},{"x": 4,"y": 4},{"x": 0,"y": 4},{"x": 0,"y": 0}]}]}
    result = build_reverse_shadow_measurement_points(contours, 2)
    assert result["complete"] and result["near"]["point_count"] == result["far"]["point_count"] == 8
    assert result["near"]["points"][0]["x_m"] == result["near"]["points"][0]["y_m"] == 0
    assert len({(p["x_m"],p["y_m"]) for p in result["near"]["points"]}) == 8


def test_duplicates_are_removed_across_contours_in_same_zone():
    line = [{"x": 0, "y": 0}, {"x": 4, "y": 0}, {"x": 4, "y": 4}, {"x": 0, "y": 4}, {"x": 0, "y": 0}]
    contours = {"complete": True, "contours": [
        {"distance_m": 5.0, "closed": True, "contour_index": i, "points_m": line} for i in range(2)] +
        [{"distance_m": 10.0, "closed": True, "contour_index": 0, "points_m": line}]}
    result = build_reverse_shadow_measurement_points(contours, 2)
    assert result["near"]["contour_count"] == 2
    assert result["near"]["point_count"] == 8
    assert [p["measurement_point_index"] for zone in ("near", "far")
            for p in result[zone]["points"]] == list(range(result["total_point_count"]))
