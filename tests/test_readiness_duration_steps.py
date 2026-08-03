from shadow_readiness import _build_pipeline_readiness


def readiness(duration):
    return _build_pipeline_readiness({}, {}, {}, shadow_duration=duration)


def test_duration_complete_starts_with_equal_time_contours():
    result = readiness({"complete": True, "ready_for_equal_time_contour_generation": True})
    assert result["shadow_duration_accumulation_complete"] is True
    assert result["ready_for_equal_time_contour_generation"] is True
    assert result["next_implementation_steps"][0] == "equal-time contour generation"
    assert "shadow duration accumulation" not in result["next_implementation_steps"]


def test_duration_incomplete_starts_with_duration_accumulation():
    result = readiness({"complete": False})
    assert result["next_implementation_steps"][0] == "shadow duration accumulation"
