import json

import pytest

from shadow_duration import integrate_shadow_states_trapezoidal
from shadow_regulatory_presets import resolve_regulatory_shadow_preset
from shadow_reverse_allowance_patterns import (
    MAX_REVERSE_ALLOWANCE_PATTERN_CANDIDATES,
    build_pattern_from_continuous_sunlight_interval,
    generate_shadow_allowance_patterns,
)
from shadow_reverse_low_rise import build_sunlight_interval_candidates


PRESET_IDS = ("standard_3_2", "standard_4_2_5", "standard_5_3")


def _minutes(value):
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def _generate(preset_id, zone):
    preset = resolve_regulatory_shadow_preset(preset_id)
    return generate_shadow_allowance_patterns(
        _minutes(preset["true_solar_start_time"]),
        _minutes(preset["true_solar_end_time"]),
        preset[zone + "_limit_minutes"], 15)


@pytest.mark.parametrize("preset_id", PRESET_IDS)
@pytest.mark.parametrize("zone", ("near", "far"))
def test_all_candidates_are_safe_unique_complete_and_json_safe(preset_id, zone):
    result = _generate(preset_id, zone)
    assert result["available"] and result["complete"]
    assert result["automatic_accuracy_fallback_used"] is False
    assert result["legal_judgement_generated"] is False
    assert result["ordinance_selection_certified"] is False
    assert result["permit_ready_certified"] is False
    keys = []
    for candidate in result["candidates"]:
        duration = integrate_shadow_states_trapezoidal(
            candidate["shadow_allowed_states"], candidate["sample_minutes"])
        assert duration == candidate["allowed_shadow_duration_minutes"]
        assert duration <= candidate["selected_limit_minutes"] + 1e-9
        assert candidate["sunlight_required_states"] == [
            not state for state in candidate["shadow_allowed_states"]]
        keys.append(tuple(candidate["shadow_allowed_states"]))
    assert len(keys) == len(set(keys))
    json.dumps(result)


def test_v2_baseline_and_both_candidate_families_are_present():
    result = _generate("standard_4_2_5", "near")
    baseline = next(candidate for candidate in result["candidates"]
                    if candidate["pattern_id"] == result["v2_baseline_pattern_id"])
    assert baseline["v2_baseline"]
    assert baseline["generation_family"] == "v2_baseline"
    assert result["one_block_candidate_count"] > 0
    assert result["two_block_candidate_count"] > 0
    for candidate in result["candidates"]:
        blocks = candidate["sunlight_required_blocks"]
        if len(blocks) == 2:
            assert blocks[0]["end_index"] + 1 < blocks[1]["start_index"]


def test_generation_is_fully_deterministic():
    assert _generate("standard_3_2", "far") == _generate("standard_3_2", "far")


def test_candidate_guard_is_an_explicit_blocker_without_fallback():
    result = generate_shadow_allowance_patterns(480, 960, 240, 15, maximum_candidate_count=10)
    assert not result["available"] and not result["complete"]
    assert result["candidates"] == []
    assert result["automatic_accuracy_fallback_used"] is False
    assert result["blockers"][0]["failure_code"] == (
        "reverse_shadow_allowance_pattern_candidate_limit_exceeded")


def test_trapezoidal_endpoint_semantics_not_shadow_sample_count():
    samples = [480, 495, 510]
    assert integrate_shadow_states_trapezoidal([True, False, False], samples) == 7.5
    assert integrate_shadow_states_trapezoidal([False, True, False], samples) == 15.0
    result = generate_shadow_allowance_patterns(480, 510, 7.5, 15)
    assert any(candidate["shadow_allowed_states"] == [True, False, False]
               for candidate in result["candidates"])
    assert all(sum(candidate["shadow_allowed_states"]) * 15 != 7.5 or
               candidate["allowed_shadow_duration_minutes"] == 7.5
               for candidate in result["candidates"])


def test_invalid_candidates_and_inputs_are_not_returned():
    result = generate_shadow_allowance_patterns(960, 480, 240, 15)
    assert not result["complete"] and result["candidates"] == []
    with pytest.raises(ValueError):
        build_pattern_from_continuous_sunlight_interval(480, 960, 400, 700, 15, 240)


def test_representative_v2_interval_has_matching_required_sunlight_semantics():
    v2 = build_sunlight_interval_candidates(480, 960, 240, 15)
    interval = next(item for item in v2["candidates"]
                    if item["sunlight_start_minutes"] == 600)
    pattern = build_pattern_from_continuous_sunlight_interval(
        480, 960, interval["sunlight_start_minutes"], interval["sunlight_end_minutes"],
        15, 240)
    required_samples = [minute for minute, required in zip(
        pattern["sample_minutes"], pattern["sunlight_required_states"]) if required]
    assert required_samples[0] == interval["sunlight_start_minutes"]
    assert required_samples[-1] == interval["sunlight_end_minutes"] - 15
    assert integrate_shadow_states_trapezoidal(
        pattern["sunlight_required_states"], pattern["sample_minutes"]) == 240
    assert pattern["allowed_shadow_duration_minutes"] == 240


def test_public_default_candidate_guard_is_explicit_and_positive():
    assert MAX_REVERSE_ALLOWANCE_PATTERN_CANDIDATES == 50000
