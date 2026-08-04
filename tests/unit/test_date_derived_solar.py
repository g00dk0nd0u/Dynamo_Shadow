import json
import math
from pathlib import Path

import pytest

from shadow_debug import _solar_calculation_debug_summary
from shadow_policies import SUN_POSITION_POLICY
from shadow_readiness import _build_pipeline_readiness
from shadow_settings import _normalize_settings
from shadow_sun import (_build_solar_calculation_v1, _derive_noaa_daily_solar_parameters,
                        _sun_position_for_true_solar_minutes)


def settings(basis="true_solar_time"):
    result = {"solar_parameter_mode": "date_derived_noaa_v1", "calculation_date": "2026-12-21",
              "time_basis": basis, "site_latitude_deg": 35.681236, "true_north_deg": 0,
              "analysis_start_time": "08:00", "analysis_end_time": "16:00", "sun_time_step_minutes": 240,
              "average_ground_level_elevation_m": 0, "measurement_height_m": 4}
    if basis == "japan_standard_time": result["site_longitude_deg"] = 139.767125
    return result


def explicit_settings(mode=True, basis="true_solar_time"):
    result = settings(basis)
    result.pop("calculation_date")
    result["solar_declination_deg"] = -23.44
    if basis == "japan_standard_time": result["equation_of_time_minutes"] = 1.93
    if mode:
        result["solar_parameter_mode"] = "explicit"
    else:
        result.pop("solar_parameter_mode")
    return result


def pipeline_for(normalized):
    return _build_pipeline_readiness(
        {"accepted_count": 1},
        {},
        normalized,
        measurement_plane={"readiness": {
            "measurement_plane_constructed": True,
            "ready_for_future_shadow_projection_context": True,
        }},
        footprint_extraction={"readiness": {
            "ready_for_future_footprint_polygon_generation": True,
        }},
    )


@pytest.mark.parametrize("value,available,day,days", [
    ("2026-01-01", True, 1, 365), ("2026-12-31", True, 365, 365),
    ("2024-02-29", True, 60, 366), ("2024-12-31", True, 366, 366),
    ("2026-13-01", False, None, None), ("2026-02-30", False, None, None),
    ("2025-02-29", False, None, None), ("2026-1-01", False, None, None)])
def test_strict_date_and_day_of_year(value, available, day, days):
    derived = _derive_noaa_daily_solar_parameters(value)
    normalized = _normalize_settings(dict(settings(), calculation_date=value))
    assert derived["available"] is available
    assert derived["day_of_year"] == day and derived["days_in_year"] == days
    assert normalized["normalized"]["calculation_date"] == (value if available else None)
    assert ("calculation_date" in normalized["invalid_keys"]) is (not available)


@pytest.mark.parametrize("basis", ["true_solar_time", "japan_standard_time"])
def test_date_derived_modes_and_readiness_agree(basis):
    normalized = _normalize_settings(settings(basis))
    solar = _build_solar_calculation_v1(normalized)
    assert normalized["readiness"]["ready_for_equal_time_shadow_calculation"] is True
    assert solar["available"] is True and solar["solar_parameters_resolved"] is True
    assert solar["solar_parameter_source_available"] is True
    assert solar["equation_of_time_applied"] is (basis == "japan_standard_time")
    pipeline = pipeline_for(normalized)
    assert pipeline["settings_ready_for_equal_time_shadow"] is True
    assert pipeline["equal_time_shadow_calculation_ready"] is True


@pytest.mark.parametrize("conflicts", [("solar_declination_deg",), ("equation_of_time_minutes",),
                                        ("solar_declination_deg", "equation_of_time_minutes")])
def test_mixed_parameter_sources_block_settings_solar_and_pipeline(conflicts):
    supplied = settings()
    for key in conflicts: supplied[key] = 1
    normalized = _normalize_settings(supplied)
    solar = _build_solar_calculation_v1(normalized)
    invalid = normalized["readiness"]["invalid_for_solar_time"]
    assert all(key in invalid for key in conflicts)
    assert normalized["readiness"]["ready_for_equal_time_shadow_calculation"] is False
    assert normalized["readiness"]["settings_ready_for_boundary_dependent_steps"] is False
    assert solar["available"] is False and solar["solar_parameters_resolved"] is False
    pipeline = pipeline_for(normalized)
    assert pipeline["settings_ready_for_equal_time_shadow"] is False
    assert pipeline["equal_time_shadow_calculation_ready"] is False


def test_invalid_date_blocks_settings_solar_and_pipeline():
    normalized = _normalize_settings(dict(settings(), calculation_date="2026-02-30"))
    solar = _build_solar_calculation_v1(normalized)
    pipeline = pipeline_for(normalized)
    assert normalized["readiness"]["ready_for_equal_time_shadow_calculation"] is False
    assert solar["available"] is False and solar["solar_parameter_source"] == "noaa_general_solar_position_calculations_v1"
    assert solar["solar_parameter_source_available"] is False and solar["solar_parameters_resolved"] is False
    assert pipeline["settings_ready_for_equal_time_shadow"] is False
    assert pipeline["equal_time_shadow_calculation_ready"] is False


@pytest.mark.parametrize("raw,inferred", [(explicit_settings(False), True), (explicit_settings(True), False),
                                            (settings(), False), ({}, False),
                                            ({"time_basis": "true_solar_time"}, False)])
def test_mode_inference_only_for_legacy_explicit_parameters(raw, inferred):
    solar = _build_solar_calculation_v1(_normalize_settings(raw))
    assert solar["solar_parameter_mode_inferred_for_backward_compatibility"] is inferred


def test_explicit_source_resolution_and_missing_input():
    valid = _build_solar_calculation_v1(_normalize_settings(explicit_settings(True)))
    missing = explicit_settings(True); missing.pop("solar_declination_deg")
    invalid = _build_solar_calculation_v1(_normalize_settings(missing))
    assert valid["solar_parameter_source"] == "explicit_settings"
    assert valid["solar_parameter_source_available"] is True and valid["solar_parameters_resolved"] is True
    assert invalid["available"] is False
    assert invalid["solar_parameter_source_available"] is False and invalid["solar_parameters_resolved"] is False


def test_policy_contract_is_mode_specific():
    requirements = SUN_POSITION_POLICY["requirements_by_mode"]
    assert "solar_declination_deg" not in requirements["date_derived_noaa_v1"]["true_solar_time"]
    assert "equation_of_time_minutes" not in requirements["date_derived_noaa_v1"]["japan_standard_time"]
    assert "equation_of_time_minutes" in requirements["explicit"]["japan_standard_time"]
    assert SUN_POSITION_POLICY["date_based_declination_calculation_supported"] is True
    assert SUN_POSITION_POLICY["date_based_equation_of_time_calculation_supported"] is True


def test_provisional_fixture_is_nonempty_complete_in_coverage_and_uses_seconds():
    cases = json.loads((Path(__file__).parent.parent / "fixtures/solar_provisional_cross_check_cases.json").read_text())
    required = {("Tokyo", "08:00:00"), ("Tokyo", "12:00:00"), ("Tokyo", "16:00:00"),
                ("Kagoshima", "12:00:00"), ("Sapporo", "09:00:00"),
                ("Sapporo", "12:00:00"), ("Sapporo", "15:00:00")}
    assert cases
    keys = [(case["location"], case["input_time"]) for case in cases]
    assert len(keys) == len(set(keys)) and required <= set(keys)
    numeric_inputs = ("observer_elevation_m", "annual_average_pressure_mbar", "annual_average_temperature_c",
                      "delta_ut1_seconds", "surface_slope_deg", "surface_azimuth_rotation_deg",
                      "atmospheric_refraction_deg")
    for case in cases:
        assert case["independent_external_reference"] is False
        assert case["purpose"] == "provisional_cross_check"
        assert case["provenance_verified"] is False
        assert case["reference_generation_provenance"] == "unverified"
        assert case["permit_ready_validation"] is False
        assert case["delta_t_seconds"] is None
        assert all(isinstance(case[key], (int, float)) for key in numeric_inputs)
        assert case["reference_output_fields"]["altitude"] == "Topocentric elevation angle (uncorrected)"
        assert case["calculation_date"] == "2026-12-21" and case["timezone_hours"] == 9
        assert case["input_time_basis"] == "japan_standard_time" and case["standard_meridian_deg"] == 135.0
        parts = case["input_time"].split(":")
        assert len(parts) == 3
        input_minutes = int(parts[0]) * 60.0 + int(parts[1]) + int(parts[2]) / 60.0
        assert input_minutes >= 0


def test_winter_shadow_quadrants_and_true_north_rotations():
    morning, noon, afternoon = [_sun_position_for_true_solar_minutes(h * 60, 35, -23.42, 0) for h in (8, 12, 16)]
    assert morning["hour_angle_deg"] < 0 == noon["hour_angle_deg"] < afternoon["hour_angle_deg"]
    assert morning["solar_azimuth_deg"] < 180
    assert noon["solar_azimuth_deg"] == pytest.approx(180, abs=1e-6)
    assert afternoon["solar_azimuth_deg"] > 180
    for shadow, x_sign in ((morning["shadow_direction_true_north"], -1),
                           (afternoon["shadow_direction_true_north"], 1)):
        assert shadow["x"] * x_sign > 0 and shadow["y"] > 0
    assert abs(noon["shadow_direction_true_north"]["x"]) < 1e-6
    assert noon["shadow_direction_true_north"]["y"] > 0
    vectors = {}
    for rotation in (0, 90, -90, 360):
        result = _sun_position_for_true_solar_minutes(720, 35, -23.42, rotation)
        vectors[rotation] = result["shadow_direction_model"]
        assert math.hypot(vectors[rotation]["x"], vectors[rotation]["y"]) == pytest.approx(1, abs=1e-6)
        assert 0 <= result["shadow_azimuth_model_deg"] < 360
    assert vectors[360] == vectors[0]


def test_debug_summary_defaults_and_allowlist():
    empty = _solar_calculation_debug_summary(None)
    for key in ("available", "complete", "solar_parameter_mode_inferred_for_backward_compatibility",
                "solar_parameter_source_available", "solar_parameters_resolved"):
        assert empty[key] is False
    assert empty["slice_count"] == 0
    result = _build_solar_calculation_v1(_normalize_settings(settings()))
    result.update({"absolute_path": "/home/private", "username": "private", "model_name": "client",
                   "raw": "Autodesk.Revit.DB"})
    summary = _solar_calculation_debug_summary(result)
    assert summary["calculation_mode"] == "date_derived_noaa_v1"
    assert summary["solar_parameters_resolved"] is True
    text = json.dumps(summary)
    for forbidden in ("absolute_path", "username", "model_name", "Autodesk.Revit.DB", "slices"):
        assert forbidden not in text
