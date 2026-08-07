from shadow_reverse_accuracy import resolve_reverse_shadow_accuracy


def test_profiles_are_fixed_and_never_fall_back():
    expected = {"rough": (4, 4, 30), "standard": (2, 2, 15), "high": (1, 1, 15)}
    for name, values in expected.items():
        result = resolve_reverse_shadow_accuracy(name)
        assert (result["measurement_point_spacing_m"], result["height_field_grid_resolution_m"], result["sun_time_step_minutes"]) == values
        assert result["site_distance_resolution_m"] == result["minimum_supported_spatial_resolution_m"] == 1
        assert result["automatic_accuracy_fallback_used"] is False
        assert .5 not in result.values()
    assert resolve_reverse_shadow_accuracy("other")["blockers"][0]["failure_code"] == "invalid_reverse_shadow_accuracy_preset"
