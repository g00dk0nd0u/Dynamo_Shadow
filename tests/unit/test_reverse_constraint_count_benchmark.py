from tools.benchmark_reverse_constraint_counts import rectangle_preflight


def test_representative_rectangle_preflight_counts_are_monotonic_and_complete():
    results = [rectangle_preflight(width, height)
               for width, height in ((50, 50), (100, 100), (150, 200))]
    required = {"inside_height_grid_point_count", "near_measurement_point_count",
                "far_measurement_point_count", "near_candidate_count", "far_candidate_count",
                "estimated_raw_constraint_checks"}
    assert all(required <= result.keys() for result in results)
    assert [result["inside_height_grid_point_count"] for result in results] == [2601, 10201, 30351]
    assert all(left["estimated_raw_constraint_checks"] < right["estimated_raw_constraint_checks"]
               for left, right in zip(results, results[1:]))
