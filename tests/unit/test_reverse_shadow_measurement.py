from shadow_reverse_measurement import build_reverse_shadow_measurement_points


def test_closed_contours_are_normalized_and_resampled():
    contours = {"complete": True, "contours": [
        {"distance_m": 10.0, "closed": True, "contour_index": 0, "points_m": [{"x": 0, "y": 0},{"x": 0,"y": 4},{"x": 4,"y": 4},{"x": 4,"y": 0},{"x": 0,"y": 0}]},
        {"distance_m": 5.0, "closed": True, "contour_index": 0, "points_m": [{"x": 0, "y": 0},{"x": 4,"y": 0},{"x": 4,"y": 4},{"x": 0,"y": 4},{"x": 0,"y": 0}]}]}
    result = build_reverse_shadow_measurement_points(contours, 2)
    assert result["complete"] and result["near"]["point_count"] == result["far"]["point_count"] == 8
    assert result["near"]["points"][0]["x_m"] == result["near"]["points"][0]["y_m"] == 0
    assert len({(p["x_m"],p["y_m"]) for p in result["near"]["points"]}) == 8
