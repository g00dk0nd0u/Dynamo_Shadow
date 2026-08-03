from shadow_policies import FORMAL_SHADOW_PROJECTION_POLICY


def test_union_and_duration_policy_matches_current_pipeline():
    policy = FORMAL_SHADOW_PROJECTION_POLICY
    assert policy["union_performed"] is True
    assert policy["duration_accumulation_performed"] is True
    assert "2D union" not in policy["unsupported_initial_scope"]
    assert "duration accumulation" not in policy["unsupported_initial_scope"]
    assert policy["equal_time_contours_generated"] is False
    assert policy["legal_judgement_generated"] is False
    assert policy["permit_ready_certified"] is False
