import json
import math

import pytest

from shadow_settings import _normalize_settings
from shadow_sun import (_build_solar_calculation_v1, _build_solar_time_conversion,
                        _model_direction_from_true_north_azimuth,
                        _sun_position_for_true_solar_minutes)


def regulatory(**changes):
    value = {"profile": "standard_8_16", "solar_parameter_mode": "regulatory_winter_solstice_v1",
             "time_basis": "true_solar_time", "site_latitude_deg": 35.6812, "true_north_deg": 0}
    value.update(changes)
    return _build_solar_calculation_v1(_normalize_settings(value))


def test_noon_analytical_identity_and_direction():
    item = _sun_position_for_true_solar_minutes(720.0, 35.6812, -23.439, 0.0)
    expected_altitude = 90.0 - abs(35.6812 - (-23.439))
    assert item["hour_angle_deg"] == 0.0
    assert item["solar_altitude_deg"] == pytest.approx(expected_altitude, abs=1e-6)
    assert item["solar_azimuth_deg"] == pytest.approx(180.0, abs=1e-9)
    assert item["shadow_azimuth_true_north_deg"] == pytest.approx(0.0, abs=1e-9)
    assert item["shadow_direction_model"]["x"] == pytest.approx(0.0, abs=1e-12)
    assert item["shadow_direction_model"]["y"] == pytest.approx(1.0, abs=1e-12)


def test_symmetry_continuity_and_no_convex_substitution():
    slices = regulatory()["slices"]
    morning, afternoon = slices[0], slices[-1]
    assert morning["solar_altitude_deg"] == pytest.approx(afternoon["solar_altitude_deg"], abs=1e-9)
    assert morning["raw_shadow_length_factor"] == pytest.approx(afternoon["raw_shadow_length_factor"], abs=1e-12)
    assert morning["shadow_direction_model"]["x"] == pytest.approx(-afternoon["shadow_direction_model"]["x"])
    assert morning["shadow_direction_model"]["y"] == pytest.approx(afternoon["shadow_direction_model"]["y"])
    angles = []
    for item in slices:
        assert math.isfinite(item["solar_altitude_deg"]) and math.isfinite(item["solar_azimuth_deg"])
        assert "convex" not in json.dumps(item).lower()
        vector = item["shadow_direction_model"]
        angles.append(math.atan2(vector["x"], vector["y"]))
    assert all(abs((b - a + math.pi) % (2 * math.pi) - math.pi) < math.pi / 2 for a, b in zip(angles, angles[1:]))


@pytest.mark.parametrize("rotation", [0, 90, -90, 180])
def test_true_north_rotation_matches_independent_matrix(rotation):
    azimuth = 37.0
    _, actual = _model_direction_from_true_north_azimuth(azimuth, rotation)
    true_x, true_y = math.sin(math.radians(azimuth)), math.cos(math.radians(azimuth))
    theta = math.radians(rotation)
    expected_x = true_x * math.cos(theta) + true_y * math.sin(theta)
    expected_y = -true_x * math.sin(theta) + true_y * math.cos(theta)
    assert actual["x"] == pytest.approx(expected_x, abs=1e-12)
    assert actual["y"] == pytest.approx(expected_y, abs=1e-12)


@pytest.mark.parametrize("equation", [5.0, 0.0, -5.0])
def test_jst_east_positive_conversion_and_sign(equation):
    result = _build_solar_time_conversion(720, "japan_standard_time", 139.7671, 135.0, equation)
    correction = 4 * (139.7671 - 135.0)
    assert result["longitude_correction_minutes"] == pytest.approx(correction, abs=1e-6)
    assert result["true_solar_minutes_raw"] == pytest.approx(720 + correction + equation, abs=1e-6)
    assert result["conversion_performed"] is True


def test_jst_rollovers_are_reported():
    assert _build_solar_time_conversion(1439, "japan_standard_time", 180, 135, 20)["day_offset"] == 1
    assert _build_solar_time_conversion(0, "japan_standard_time", -180, 135, -20)["day_offset"] == -1


@pytest.mark.parametrize("profile,count,first,last", [
    ("standard_8_16", 17, "08:00:00", "16:00:00"),
    ("hokkaido_9_15", 13, "09:00:00", "15:00:00"),
])
def test_profile_windows(profile, count, first, last):
    result = regulatory(profile=profile)
    assert result["slice_count"] == count
    assert result["slices"][0]["input_time"] == first
    assert result["slices"][-1]["input_time"] == last


def test_stable_serialization_is_deterministic_offline():
    first = json.dumps(regulatory(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    second = json.dumps(regulatory(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    assert first.encode("ascii") == second.encode("ascii")


def test_modes_are_separate_and_legacy_remains_explicit():
    result = regulatory(site_longitude_deg=139.7671)
    assert not result["longitude_correction_applied"] and not result["equation_of_time_applied"]
    no_date = regulatory(solar_parameter_mode="date_derived_noaa_v1")
    assert not no_date["available"]
    legacy = regulatory(solar_parameter_mode=None, solar_declination_deg=-23.439,
                        analysis_start_time="08:00", analysis_end_time="16:00", sun_time_step_minutes=30)
    assert legacy["solar_parameter_mode"] == "explicit" and legacy["slice_count"] == 17
    assert legacy["recommended_mode"] == "regulatory_winter_solstice_v1"


def test_horizon_omits_formal_direction():
    item = _sun_position_for_true_solar_minutes(0, 35.6812, -23.439, 0)
    assert item["solar_altitude_deg"] <= 0
    assert item["shadow_direction_model"] is None
    assert item["shadow_length_factor"] is None and item["warning"]


@pytest.mark.parametrize("change", [
    {"site_latitude_deg": 91}, {"site_longitude_deg": 181}, {"true_north_deg": 361},
    {"profile": "unknown"}, {"time_basis": "utc"}, {"sun_time_step_minutes": 0},
    {"analysis_start_time": "16:00", "analysis_end_time": "08:00"},
    {"solar_declination_deg": -20.0},
])
def test_invalid_settings_block_formal_calculation(change):
    assert not regulatory(**change)["available"]
