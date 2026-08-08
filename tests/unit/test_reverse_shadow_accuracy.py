from shadow_reverse_accuracy import resolve_reverse_shadow_accuracy


def test_profiles_are_fixed_independent_and_never_fall_back():
    expected = {
        "rough": (1, 4, 4, 30, .5),
        "standard": (1, 1, 1, 15, .5),
        "high": (1, 1, 1, 15, .5),
    }
    for name, values in expected.items():
        result = resolve_reverse_shadow_accuracy(name)
        actual = (result["site_distance_resolution_m"], result["measurement_point_spacing_m"],
                  result["height_field_grid_resolution_m"], result["sun_time_step_minutes"],
                  result["vertical_height_step_m"])
        assert actual == values
        assert result["vertical_height_quantization"] == "floor_conservative"
        assert result["automatic_accuracy_fallback_used"] is False
    assert resolve_reverse_shadow_accuracy("other")["blockers"][0]["failure_code"] == "invalid_reverse_shadow_accuracy_preset"
