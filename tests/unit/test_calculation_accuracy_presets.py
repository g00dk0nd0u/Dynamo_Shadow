import copy

from shadow_accuracy_presets import ACCURACY_PRESETS, overlay_calculation_accuracy_settings, resolve_calculation_accuracy_preset
from shadow_policies import SETTINGS_DIAGNOSTIC_DEFAULTS


def test_three_accuracy_presets_have_expected_resolution_and_step():
    assert ACCURACY_PRESETS == {
        "rough": {"grid_resolution_m": 1.0, "sun_time_step_minutes": 30},
        "standard": {"grid_resolution_m": 0.5, "sun_time_step_minutes": 15},
        "high": {"grid_resolution_m": 0.25, "sun_time_step_minutes": 5},
    }
    assert resolve_calculation_accuracy_preset("rough")["grid_resolution_m"] > 0.5
    assert resolve_calculation_accuracy_preset("high")["sun_time_step_minutes"] == 5


def test_invalid_accuracy_preset_has_machine_readable_blocker():
    result = resolve_calculation_accuracy_preset("ultra")
    assert result["valid"] is False
    assert result["blockers"][0]["failure_code"] == "invalid_calculation_accuracy_preset"


def test_player_overlay_wins_without_mutating_json_settings():
    settings = {"grid_resolution_m": 2.0, "sun_time_step_minutes": 60, "other": 1}
    original = copy.deepcopy(settings)
    overlaid, resolved, *_ = overlay_calculation_accuracy_settings(settings, "high")
    assert settings == original
    assert overlaid == {"grid_resolution_m": 0.25, "sun_time_step_minutes": 5, "other": 1}
    assert resolved["preset_id"] == "high"


def test_missing_player_value_preserves_pure_python_defaults_and_settings():
    overlaid, resolved, *_ = overlay_calculation_accuracy_settings({}, None)
    assert overlaid == {} and resolved is None
    assert SETTINGS_DIAGNOSTIC_DEFAULTS["grid_resolution_m"] == 1.0
