import json
from pathlib import Path

import pytest

import script
from shadow_settings import _normalize_settings
from shadow_sun import _build_solar_calculation_v1, _build_solar_time_conversion, _parse_time_to_minutes, _sun_position_for_true_solar_minutes


def _time_seconds(text):
    h, m, s = [int(part) for part in text.split(":")]
    return h * 3600 + m * 60 + s


def test_failure_path_includes_solar_calculation_v1_when_sun_diagnostics_raise(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("forced sun diagnostic failure")

    monkeypatch.setattr(script, "_build_sun_position_diagnostics", fail)
    payload = script._build_failure("forced top-level failure")

    assert isinstance(payload, dict)
    assert payload["success"] is False
    assert "solar_calculation_v1" in payload
    assert payload["solar_calculation_v1"] is None


def _base_settings(time_basis="true_solar_time"):
    return {
        "time_basis": time_basis,
        "site_latitude_deg": 35.0,
        "solar_declination_deg": -23.44,
        "true_north_deg": 0.0,
        "analysis_start_time": "09:00",
        "analysis_end_time": "10:00",
        "sun_time_step_minutes": 30,
        "average_ground_level_elevation_m": 0.0,
        "measurement_height_m": 4.0,
    }


def test_true_solar_readiness_uses_site_latitude_not_legacy_latitude():
    normalized = _normalize_settings(_base_settings("true_solar_time"))
    readiness = normalized["readiness"]
    assert readiness["ready_for_equal_time_shadow_calculation"] is True
    assert "latitude" not in readiness["missing_for_equal_time_shadow"]


def test_japan_standard_time_requires_longitude_and_equation_of_time():
    settings = _base_settings("japan_standard_time")
    normalized = _normalize_settings(settings)
    readiness = normalized["readiness"]
    assert readiness["ready_for_equal_time_shadow_calculation"] is False
    assert "site_longitude_deg" in readiness["missing_for_equal_time_shadow"]
    assert "equation_of_time_minutes" in readiness["missing_for_equal_time_shadow"]


def test_true_solar_time_calculates_without_site_longitude():
    normalized = _normalize_settings(_base_settings("true_solar_time"))
    solar = _build_solar_calculation_v1(normalized)
    assert solar["available"] is True
    assert solar["slice_count"] == 3


def test_solar_time_conversion_formats_fractional_minutes_to_seconds_and_day_offsets():
    conversion = _build_solar_time_conversion(12 * 60 + 1.93, "true_solar_time", None, None, None)
    assert conversion["true_solar_time"] == "12:01:56"
    assert conversion["day_offset"] == 0

    next_day = _build_solar_time_conversion(23 * 60 + 59.9, "true_solar_time", None, None, None)
    assert next_day["true_solar_time"] == "23:59:54"
    assert next_day["day_offset"] == 0

    previous_day = _build_solar_time_conversion(-0.1, "true_solar_time", None, None, None)
    assert previous_day["true_solar_time"] == "23:59:54"
    assert previous_day["day_offset"] == -1


def test_unknown_time_basis_is_rejected_for_direct_conversion():
    with pytest.raises(ValueError):
        _build_solar_time_conversion(720, "local_clock_time", None, None, None)


@pytest.mark.parametrize("key,value", [
    ("site_latitude_deg", 91),
    ("site_longitude_deg", 181),
    ("standard_meridian_deg", 181),
    ("solar_declination_deg", 30),
    ("equation_of_time_minutes", 30),
    ("sun_time_step_minutes", 0),
])
def test_invalid_solar_numeric_ranges_are_reported(key, value):
    settings = _base_settings("japan_standard_time")
    settings.update({"site_longitude_deg": 139.0, "standard_meridian_deg": 135.0, "equation_of_time_minutes": 1.0})
    settings[key] = value
    normalized = _normalize_settings(settings)
    assert key in normalized["invalid_keys"]
    assert key in normalized["readiness"]["invalid_for_equal_time_shadow"]
    assert normalized["readiness"]["ready_for_equal_time_shadow_calculation"] is False


def test_external_solar_fixture_is_loaded_and_matches_implementation():
    fixture_path = Path(__file__).parent.parent / "fixtures" / "solar_formula_regression_cases.json"
    cases = json.loads(fixture_path.read_text())
    assert cases
    for case in cases:
        warnings = []
        input_minutes = _parse_time_to_minutes(case["input_time"], "input_time", warnings)
        assert warnings == []
        conversion = _build_solar_time_conversion(input_minutes, case["input_time_basis"], case["longitude"], case["standard_meridian"], case["equation_of_time"])
        solar = _sun_position_for_true_solar_minutes(conversion["true_solar_minutes"], case["latitude"], case["declination"], 0.0)
        legacy_settings = {
            "time_basis": case["input_time_basis"],
            "site_latitude_deg": case["latitude"],
            "site_longitude_deg": case["longitude"],
            "standard_meridian_deg": case["standard_meridian"],
            "solar_declination_deg": case["declination"],
            "equation_of_time_minutes": case["equation_of_time"],
            "true_north_deg": 0.0,
            "analysis_start_time": case["input_time"],
            "analysis_end_time": case["input_time"],
            "sun_time_step_minutes": 30,
            "average_ground_level_elevation_m": 0.0,
            "measurement_height_m": 4.0,
        }
        calculation = _build_solar_calculation_v1(_normalize_settings(legacy_settings))
        assert calculation["available"] is True
        assert calculation["solar_parameter_mode"] == "explicit"
        assert calculation["solar_parameter_mode_inferred_for_backward_compatibility"] is True
        slice_result = calculation["slices"][0]
        expected_fields = {
            "input_time_basis": case["input_time_basis"],
            "true_solar_time": conversion["true_solar_time"],
            "true_solar_minutes": conversion["true_solar_minutes"],
            "hour_angle_deg": solar["hour_angle_deg"],
            "solar_altitude_deg": solar["solar_altitude_deg"],
            "solar_azimuth_deg": solar["solar_azimuth_deg"],
            "shadow_azimuth_true_north_deg": solar["shadow_azimuth_true_north_deg"],
            "shadow_direction_vector": solar["shadow_direction_vector"],
            "shadow_azimuth_model_deg": solar["shadow_azimuth_model_deg"],
            "shadow_direction_model": solar["shadow_direction_model"],
            "longitude_correction_minutes": conversion["longitude_correction_minutes"],
            "equation_of_time_applied": conversion["equation_of_time_applied"],
            "longitude_correction_applied": conversion["longitude_correction_applied"],
        }
        assert {key: slice_result[key] for key in expected_fields} == expected_fields
        assert abs(_time_seconds(conversion["true_solar_time"]) - _time_seconds(case["expected_true_solar_time"])) <= case["tolerance"]["time_seconds"]
        assert abs(solar["solar_altitude_deg"] - case["expected_altitude"]) <= case["tolerance"]["angle_deg"]
        assert abs(solar["solar_azimuth_deg"] - case["expected_azimuth"]) <= case["tolerance"]["angle_deg"]
        assert case["permit_ready_certified"] is False
        assert case["atmospheric_refraction_applied"] is False
        assert case["reference_source_name_or_url"]
        assert case["independent_external_reference"] is False
        assert case["purpose"] == "internal_formula_regression"
