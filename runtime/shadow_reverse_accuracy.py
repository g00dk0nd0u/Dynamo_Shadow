"""Fixed, pure-Python accuracy profiles for low-rise reverse shadow v1."""

REVERSE_SHADOW_ACCURACY_PRESETS = {
    "rough": (1.0, 4.0, 4.0, 30),
    "standard": (1.0, 2.0, 2.0, 15),
    "high": (1.0, 1.0, 1.0, 15),
}


def resolve_reverse_shadow_accuracy(value):
    preset_id = str(value).strip() if value is not None else ""
    values = REVERSE_SHADOW_ACCURACY_PRESETS.get(preset_id)
    if values is None:
        return {"preset_id": preset_id or None, "valid": False,
                "minimum_supported_spatial_resolution_m": 1.0,
                "automatic_accuracy_fallback_used": False,
                "blockers": [{"failure_code": "invalid_reverse_shadow_accuracy_preset",
                              "preset_id": preset_id or None}]}
    site, measurement, height, minutes = values
    return {"preset_id": preset_id, "valid": True,
            "site_distance_resolution_m": site,
            "measurement_point_spacing_m": measurement,
            "height_field_grid_resolution_m": height,
            "sun_time_step_minutes": minutes,
            "minimum_supported_spatial_resolution_m": 1.0,
            "automatic_accuracy_fallback_used": False, "blockers": []}
