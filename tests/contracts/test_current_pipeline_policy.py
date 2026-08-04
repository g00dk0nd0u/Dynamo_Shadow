from shadow_policies import EQUAL_TIME_CONTOUR_POLICY, FORMAL_SHADOW_PROJECTION_POLICY


def test_current_pipeline_policy_includes_equal_time_contours():
    policy = FORMAL_SHADOW_PROJECTION_POLICY
    assert policy["union_performed"] is True
    assert policy["duration_accumulation_performed"] is True
    assert policy["equal_time_contours_generated"] is True
    assert "2D union" not in policy["unsupported_initial_scope"]
    assert "duration accumulation" not in policy["unsupported_initial_scope"]
    assert "equal-time contours" not in policy["unsupported_initial_scope"]
    assert EQUAL_TIME_CONTOUR_POLICY["method"] == "marching_squares_linear_interpolation_v1"
    assert EQUAL_TIME_CONTOUR_POLICY["legal_judgement_generated"] is False
    assert EQUAL_TIME_CONTOUR_POLICY["permit_ready_certified"] is False
    assert policy["legal_judgement_generated"] is False
    assert policy["permit_ready_certified"] is False
