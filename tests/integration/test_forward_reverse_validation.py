import json
import math
from pathlib import Path

import pytest

from shadow_forward_reverse_validation import build_forward_reverse_validation


FIXTURE_DIRECTORY = Path(__file__).parents[1] / "fixtures" / "forward_reverse_validation"
FIXTURE_PATHS = sorted(FIXTURE_DIRECTORY.glob("*.json"))
EXPECTED_PRESETS = {"standard_3_2", "standard_4_2_5", "standard_5_3"}


def _load_fixture(path):
    return json.loads(path.read_text())


@pytest.mark.parametrize("fixture_path", FIXTURE_PATHS, ids=lambda path: path.stem)
def test_fixed_fixture_completes_json_safe_comparison(fixture_path):
    fixture = _load_fixture(fixture_path)
    result = build_forward_reverse_validation(fixture)

    assert result["fixture_id"] == fixture["fixture_id"]
    assert result["delta_summary"]["mismatch_classification"] != "undetermined"
    forward = result["forward_equivalent"]
    assert forward["method"] == "pure_python_prismatic_forward_equivalent_validator_v1"
    assert math.isfinite(forward["near_max_minutes"])
    assert math.isfinite(forward["far_max_minutes"])
    assert forward["near_status"] != "undetermined"
    assert forward["far_status"] != "undetermined"
    reverse = result["reverse_v2"]
    reverse_v3 = result["reverse_v3"]
    assert reverse["method"] == "low_rise_optimized_continuous_sunlight_envelope_v2"
    assert reverse["envelope_fit"]["validation_point_count"] > 0
    assert reverse_v3["method"] == "low_rise_zone_common_shadow_allowance_envelope_v3"
    assert reverse_v3["envelope_fit"]["validation_point_count"] > 0
    assert reverse_v3["bounded_candidate_volume_m3"] >= reverse["bounded_candidate_volume_m3"] - 1e-9
    optimization = reverse_v3["pattern_optimization"]
    assert optimization["near_general_shortlist_count"] <= 32
    assert optimization["far_general_shortlist_count"] <= 32
    assert optimization["near_v2_pinned_candidate_count"] > 0
    assert optimization["far_v2_pinned_candidate_count"] > 0
    json.dumps(result, allow_nan=False)
    assert result["legal_judgement_generated"] is False
    assert result["ordinance_selection_certified"] is False
    assert result["permit_ready_certified"] is False

    if fixture_path.stem == "centered_mismatch":
        assert forward["near_max_minutes"] == 90.0
        assert forward["far_max_minutes"] == 52.5
        assert result["delta_summary"]["mismatch_classification"] == "forward_within_reverse_outside"
        assert reverse["envelope_fit"]["maximum_height_excess_m"] == 0.5
        feasibility = result["general_pattern_fixture_feasibility"]
        assert feasibility["complete"] is True
        assert feasibility["near_feasible_general_pattern_count"] == 0
        assert feasibility["far_feasible_general_pattern_count"] == 0
        assert feasibility["fixture_feasible_under_pattern_family"] is False
        first_summary = (result["forward_equivalent"], reverse, reverse_v3,
                         result["delta_summary"], feasibility)
        del result
        repeated = build_forward_reverse_validation(fixture)
        assert repeated["forward_equivalent"] == first_summary[0]
        assert repeated["reverse_v2"] == first_summary[1]
        assert repeated["reverse_v3"] == first_summary[2]
        assert repeated["delta_summary"] == first_summary[3]
        assert repeated["general_pattern_fixture_feasibility"] == first_summary[4]

    if fixture_path.stem == "concave_l_prism":
        assert reverse["envelope_fit"]["validation_point_count"] > 0
        assert result["delta_summary"]["mismatch_classification"] != "undetermined"


def test_fixed_fixtures_preserve_required_preset_coverage():
    presets = {_load_fixture(path)["preset_id"] for path in FIXTURE_PATHS}
    assert presets.issuperset(EXPECTED_PRESETS)


def test_v3_atomic_constraint_budget_returns_explicit_blocker(monkeypatch):
    import shadow_reverse_low_rise
    monkeypatch.setattr(shadow_reverse_low_rise, "MAX_REVERSE_CONSTRAINT_CHECKS", 0)
    fixture = _load_fixture(FIXTURE_DIRECTORY / "centered_mismatch.json")
    result = build_forward_reverse_validation(fixture)
    reverse_v3 = result["reverse_v3"]
    assert reverse_v3["complete"] is False
    blocker = reverse_v3["blockers"][0]
    assert blocker["failure_code"] == "reverse_shadow_complexity_limit_exceeded"
    assert blocker["limit_type"] == "constraint_checks"
    assert blocker["automatic_accuracy_fallback_used"] is False
