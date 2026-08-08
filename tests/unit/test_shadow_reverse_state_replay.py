import json
from pathlib import Path

from shadow_regulatory_presets import resolve_regulatory_shadow_preset
from shadow_reverse_state_replay import build_shadow_state_replay

FIXTURES = Path(__file__).parents[1] / "fixtures" / "forward_reverse_validation"


def _run(name):
    fixture = json.loads((FIXTURES / name).read_text())
    preset = resolve_regulatory_shadow_preset(fixture["preset_id"])
    points = [(fixture["site_boundary"][0][0] - 5, fixture["site_boundary"][0][1]),
              (fixture["site_boundary"][2][0] + 10, fixture["site_boundary"][2][1])]
    return build_shadow_state_replay(fixture, preset, points)


def test_centered_mismatch_replay_is_deterministic_and_explicit():
    result = _run("centered_mismatch.json")
    assert result == _run("centered_mismatch.json")
    assert len(result["shadow_states"]) == 2
    assert result["forward_shadow_state_count"] == sum(sum(row) for row in result["shadow_states"])
    assert result["inverse_reconstruction_complete"] is False
    assert result["original_building_fits_reconstructed_envelope"] is True
    assert result["maximum_height_excess_m"] == 0
    assert result["temporal_pattern_limitation_only"] is None
    assert result["blockers"]


def test_existing_no_mismatch_fixture_replays_states():
    result = _run("east_west_asymmetric.json")
    assert result["sample_minutes"]
    assert result["maximum_height_m"] == 31.0
    assert result["original_building_fits_reconstructed_envelope"] is True
