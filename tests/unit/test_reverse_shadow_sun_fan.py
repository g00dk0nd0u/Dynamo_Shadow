import math
from shadow_settings import _normalize_settings
from shadow_sun import build_true_solar_sun_ray_fan


def _settings(latitude=35):
    return _normalize_settings({"profile": "standard_8_16", "time_basis": "true_solar_time",
        "solar_parameter_mode": "regulatory_winter_solstice_v1", "site_latitude_deg": latitude,
        "true_north_deg": 0, "average_ground_level_elevation_m": 0, "measurement_height_m": 4})


def test_inclusive_non_aligned_fan_is_unit_and_monotonic():
    result = build_true_solar_sun_ray_fan(_settings(), 575, 865, 15)
    times = [item["true_solar_minutes"] for item in result["samples"]]
    assert result["complete"] and times[0] == 575 and times[-1] == 865 and len(times) == len(set(times))
    angles = [item["sun_azimuth_model_unwrapped_deg"] for item in result["samples"]]
    assert angles == sorted(angles) or angles == sorted(angles, reverse=True)
    for item in result["samples"]:
        ray = item["ray_vector_model"]
        assert math.isclose(sum(v*v for v in ray.values()), 1, abs_tol=1e-6) and ray["z"] > 0


def test_rough_step_and_fan_failures():
    assert build_true_solar_sun_ray_fan(_settings(), 570, 870, 30)["sample_count"] == 11
    assert build_true_solar_sun_ray_fan(_settings(), 570, 570, 15)["blockers"][0]["failure_code"] == "reverse_shadow_sun_ray_invalid"
    assert build_true_solar_sun_ray_fan({}, 570, 870, 15)["blockers"][0]["failure_code"] == "reverse_shadow_sun_ray_invalid"
    assert build_true_solar_sun_ray_fan(_settings(80), 480, 500, 15)["blockers"][0]["failure_code"] == "reverse_shadow_sun_below_horizon"
