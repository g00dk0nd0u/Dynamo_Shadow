"""Pure-Python calculation-accuracy presets and immutable settings overlay."""

from shadow_settings import _coerce_settings_to_dict


ACCURACY_PRESETS = {
    "rough": {"grid_resolution_m": 0.5, "sun_time_step_minutes": 30},
    "standard": {"grid_resolution_m": 0.5, "sun_time_step_minutes": 15},
    "high": {"grid_resolution_m": 0.25, "sun_time_step_minutes": 15},
}


def resolve_calculation_accuracy_preset(value):
    preset_id = str(value).strip() if value is not None else ""
    preset = ACCURACY_PRESETS.get(preset_id)
    if preset is None:
        return {
            "preset_id": preset_id or None,
            "valid": False,
            "blockers": [{
                "failure_code": "invalid_calculation_accuracy_preset",
                "preset_id": preset_id or None,
            }],
        }
    return {
        "preset_id": preset_id,
        "grid_resolution_m": preset["grid_resolution_m"],
        "sun_time_step_minutes": preset["sun_time_step_minutes"],
        "valid": True,
        "blockers": [],
    }


def overlay_calculation_accuracy_settings(settings, value=None):
    """Return a new dict; a missing Player value preserves legacy API defaults."""
    base, input_format, warnings, errors = _coerce_settings_to_dict(settings)
    overlaid = dict(base)
    resolved = None
    if value is not None:
        resolved = resolve_calculation_accuracy_preset(value)
        if resolved["valid"]:
            overlaid["grid_resolution_m"] = resolved["grid_resolution_m"]
            overlaid["sun_time_step_minutes"] = resolved["sun_time_step_minutes"]
    return overlaid, resolved, input_format, warnings, errors
