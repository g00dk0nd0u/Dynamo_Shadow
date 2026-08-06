"""Test-only dense solar reference for the production 15-minute envelope."""
import math

from shadow_reverse_accuracy import REVERSE_SHADOW_ACCURACY_PRESETS
from shadow_reverse_low_rise import _constraint
from shadow_settings import _normalize_settings
from shadow_sun import build_true_solar_sun_ray_fan


def _winter_solstice_settings():
    return _normalize_settings({
        "profile": "standard_8_16",
        "time_basis": "true_solar_time",
        "solar_parameter_mode": "regulatory_winter_solstice_v1",
        "site_latitude_deg": 35.0,
        "true_north_deg": 0.0,
        "average_ground_level_elevation_m": 0.0,
        "measurement_height_m": 4.0,
    })


def test_15_minute_envelope_does_not_exceed_test_only_dense_reference():
    settings = _winter_solstice_settings()
    production = build_true_solar_sun_ray_fan(settings, 570, 870, 15)
    dense_reference = build_true_solar_sun_ray_fan(settings, 570, 870, 1)
    assert production["complete"] and dense_reference["complete"]

    measurements = ({"x_m": 0.0, "y_m": 0.0},
                    {"x_m": 12.0, "y_m": -7.0},
                    {"x_m": -9.0, "y_m": 15.0})
    reference_by_time = {sample["true_solar_minutes"]: sample
                         for sample in dense_reference["samples"]}
    comparisons = []
    for measurement in measurements:
        for minute in (600, 660, 720, 780, 840):
            horizontal = reference_by_time[minute]["sun_horizontal_model"]
            site_point = (measurement["x_m"] + 20.0 * horizontal["x"],
                          measurement["y_m"] + 20.0 * horizontal["y"])
            coarse = _constraint(site_point, measurement, production, 4.0)
            dense = _constraint(site_point, measurement, dense_reference, 4.0)
            assert coarse is not None and dense is not None
            assert math.isfinite(coarse["height"]) and math.isfinite(dense["height"])
            assert coarse["height"] <= dense["height"] + 1e-9
            comparisons.append((coarse["height"], dense["height"]))

    assert len(comparisons) == 15
    assert all(profile[3] in (15, 30) for profile in REVERSE_SHADOW_ACCURACY_PRESETS.values())
    assert all(profile[3] != 1 for profile in REVERSE_SHADOW_ACCURACY_PRESETS.values())
