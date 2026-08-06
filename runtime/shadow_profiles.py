"""Immutable regulatory-reference solar time-window profiles."""

SOLAR_PROFILES = {
    "standard_8_16": {
        "regulatory_region_scope": "Japan excluding Hokkaido-specific time window",
        "required_time_basis": "true_solar_time",
        "window_start": "08:00",
        "window_end": "16:00",
        "default_computational_step_minutes": 30,
        "reference_shape_interval_minutes": 60,
    },
    "hokkaido_9_15": {
        "regulatory_region_scope": "Hokkaido",
        "required_time_basis": "true_solar_time",
        "window_start": "09:00",
        "window_end": "15:00",
        "default_computational_step_minutes": 30,
        "reference_shape_interval_minutes": 60,
    },
}


def get_solar_profile(name):
    """Return a defensive copy so callers cannot mutate the shared contract."""
    profile = SOLAR_PROFILES.get(name)
    return dict(profile) if profile is not None else None
