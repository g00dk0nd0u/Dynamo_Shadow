import json
import math
from pathlib import Path

import pytest

from shadow_debug import _solar_calculation_debug_summary
from shadow_settings import _normalize_settings
from shadow_sun import (_build_solar_calculation_v1, _derive_noaa_daily_solar_parameters,
                        _sun_position_for_true_solar_minutes)


def settings(basis="true_solar_time"):
    result = {"solar_parameter_mode":"date_derived_noaa_v1", "calculation_date":"2026-12-21",
              "time_basis":basis, "site_latitude_deg":35.681236, "true_north_deg":0,
              "analysis_start_time":"08:00", "analysis_end_time":"16:00", "sun_time_step_minutes":240,
              "average_ground_level_elevation_m":0, "measurement_height_m":4}
    if basis == "japan_standard_time": result["site_longitude_deg"] = 139.767125
    return result


@pytest.mark.parametrize("value,available,day,days", [
    ("2026-01-01", True, 1, 365), ("2026-12-31", True, 365, 365),
    ("2024-02-29", True, 60, 366), ("2024-12-31", True, 366, 366),
    ("2026-13-01", False, None, None), ("2026-02-30", False, None, None),
    ("2025-02-29", False, None, None), ("2026-1-01", False, None, None)])
def test_strict_date_and_day_of_year(value, available, day, days):
    result = _derive_noaa_daily_solar_parameters(value)
    assert result["available"] is available
    assert result["day_of_year"] == day
    assert result["days_in_year"] == days


@pytest.mark.parametrize("basis", ["true_solar_time", "japan_standard_time"])
def test_date_derived_modes(basis):
    result = _build_solar_calculation_v1(_normalize_settings(settings(basis)))
    assert result["available"] is True
    assert result["date_based_declination_calculated"] is True
    assert result["date_based_equation_of_time_calculated"] is True
    assert result["equation_of_time_applied"] is (basis == "japan_standard_time")


@pytest.mark.parametrize("key", ["solar_declination_deg", "equation_of_time_minutes"])
def test_mixed_parameter_sources_block(key):
    supplied = settings(); supplied[key] = 1
    result = _build_solar_calculation_v1(_normalize_settings(supplied))
    assert result["available"] is False
    assert any("must not be supplied" in item for item in result["blockers"])


def test_no_implicit_solstice_and_explicit_backward_compatibility():
    missing = settings(); del missing["calculation_date"]
    result = _build_solar_calculation_v1(_normalize_settings(missing))
    assert result["available"] is False and result["calculation_date"] is None
    explicit = settings(); explicit.pop("solar_parameter_mode"); explicit.pop("calculation_date"); explicit["solar_declination_deg"] = -23.44
    result = _build_solar_calculation_v1(_normalize_settings(explicit))
    assert result["available"] is True
    assert result["solar_parameter_mode"] == "explicit"
    assert result["solar_parameter_mode_inferred_for_backward_compatibility"] is True


def test_external_reference_fixture_authenticity_and_tolerances():
    cases = json.loads((Path(__file__).parent / "fixtures/solar_external_reference_cases.json").read_text())
    for case in cases:
        assert case["independent_external_reference"] is True
        assert case["source_organization"] in ("NOAA", "NREL")
        assert case["source_url"] and case["accessed_date"]
        assert "same equations implemented in shadow_sun.py" not in case["reference_method"]
        derived = _derive_noaa_daily_solar_parameters(case["calculation_date"])
        minutes = int(case["input_time"][:2]) * 60 + int(case["input_time"][3:5])
        minutes += 4 * (case["longitude_deg"] - case["standard_meridian_deg"]) + derived["equation_of_time_minutes"]
        solar = _sun_position_for_true_solar_minutes(minutes, case["latitude_deg"], derived["solar_declination_deg"], 0)
        tolerance = case["tolerance"]
        assert abs(derived["equation_of_time_minutes"] - case["expected_equation_of_time_minutes"]) <= tolerance["equation_of_time_minutes"]
        assert abs(derived["solar_declination_deg"] - case["expected_solar_declination_deg"]) <= tolerance["solar_declination_deg"]
        assert abs(solar["solar_altitude_deg"] - case["expected_solar_altitude_deg"]) <= tolerance["solar_altitude_deg"]
        assert abs(solar["solar_azimuth_deg"] - case["expected_solar_azimuth_deg"]) <= tolerance["solar_azimuth_deg"]


def test_winter_directions_and_true_north_rotations():
    positions = [_sun_position_for_true_solar_minutes(h * 60, 35, -23.42, 0) for h in (8, 12, 16)]
    assert positions[0]["hour_angle_deg"] < 0 == positions[1]["hour_angle_deg"] < positions[2]["hour_angle_deg"]
    assert positions[0]["solar_azimuth_deg"] < 180 < positions[2]["solar_azimuth_deg"]
    for position in positions:
        sun = position["solar_azimuth_deg"]
        assert position["shadow_azimuth_true_north_deg"] == pytest.approx((sun + 180) % 360)
    for rotation in (0, 90, -90, 360):
        vector = _sun_position_for_true_solar_minutes(720, 35, -23.42, rotation)["shadow_direction_model"]
        assert math.hypot(vector["x"], vector["y"]) == pytest.approx(1, abs=1e-6)
        assert 0 <= _sun_position_for_true_solar_minutes(720, 35, -23.42, rotation)["shadow_azimuth_model_deg"] < 360


def test_debug_summary_is_allowlisted_and_omits_slices():
    result = _build_solar_calculation_v1(_normalize_settings(settings()))
    result.update({"absolute_path":"/home/private", "username":"private", "model_name":"client", "raw":"Autodesk.Revit.DB"})
    summary = _solar_calculation_debug_summary(result)
    text = json.dumps(summary)
    for forbidden in ("absolute_path", "username", "model_name", "Autodesk.Revit.DB", "slices"):
        assert forbidden not in text
