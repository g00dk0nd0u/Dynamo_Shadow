import math

from shadow_settings import _normalize_settings
from shadow_sun import _build_solar_calculation_v1, _build_solar_time_conversion, _model_direction_from_true_north_azimuth


def solar(settings):
    return _build_solar_calculation_v1(_normalize_settings(settings))


def base(**kw):
    data = {
        "time_basis": "true_solar_time",
        "analysis_start_time": "12:00",
        "analysis_end_time": "12:00",
        "sun_time_step_minutes": 30,
        "site_latitude_deg": 35.0,
        "solar_declination_deg": -23.44,
        "true_north_deg": 0.0,
    }
    data.update(kw)
    return data


def test_true_solar_noon_has_zero_hour_angle_and_no_time_corrections():
    out = solar(base())
    s = out["slices"][0]
    assert out["available"] is True
    assert s["true_solar_time"] == "12:00:00"
    assert s["hour_angle_deg"] == 0.0
    assert s["longitude_correction_applied"] is False
    assert s["equation_of_time_applied"] is False


def test_jst_at_135e_has_zero_longitude_correction():
    out = solar(base(time_basis="japan_standard_time", site_longitude_deg=135, equation_of_time_minutes=0))
    assert out["longitude_correction_minutes"] == 0.0
    assert out["slices"][0]["true_solar_time"] == "12:00:00"


def test_jst_east_of_135e_adds_positive_twenty_minutes():
    out = solar(base(time_basis="japan_standard_time", site_longitude_deg=140, equation_of_time_minutes=0))
    assert out["longitude_correction_minutes"] == 20.0
    assert out["slices"][0]["true_solar_time"] == "12:20:00"


def test_jst_west_of_135e_adds_negative_twenty_minutes():
    out = solar(base(time_basis="japan_standard_time", site_longitude_deg=130, equation_of_time_minutes=0))
    assert out["longitude_correction_minutes"] == -20.0
    assert out["slices"][0]["true_solar_time"] == "11:40:00"


def test_equation_of_time_is_added_to_jst():
    out = solar(base(time_basis="japan_standard_time", site_longitude_deg=135, equation_of_time_minutes=10))
    assert out["slices"][0]["true_solar_time"] == "12:10:00"


def test_next_day_wrap_reports_day_offset_one():
    c = _build_solar_time_conversion(1430, "japan_standard_time", 140, 135, 10)
    assert c["true_solar_time"] == "00:20:00"
    assert c["day_offset"] == 1


def test_previous_day_wrap_reports_day_offset_minus_one():
    c = _build_solar_time_conversion(10, "japan_standard_time", 130, 135, -10)
    assert c["true_solar_time"] == "23:40:00"
    assert c["day_offset"] == -1


def test_true_north_zero_keeps_true_north_vector_in_model_axes():
    model_az, model = _model_direction_from_true_north_azimuth(0, 0)
    assert model_az == 0
    assert model["x"] == 0.0 and model["y"] == 1.0


def test_true_north_90_rotates_true_north_to_model_positive_x():
    model_az, model = _model_direction_from_true_north_azimuth(0, 90)
    assert model_az == 90
    assert model["x"] == 1.0 and abs(model["y"]) == 0.0


def test_true_north_minus_90_rotates_true_north_to_model_negative_x():
    model_az, model = _model_direction_from_true_north_azimuth(0, -90)
    assert model_az == 270
    assert model["x"] == -1.0 and abs(model["y"]) == 0.0


def test_morning_and_afternoon_shadow_direction_flips_smoothly_around_noon():
    out = solar(base(analysis_start_time="11:30", analysis_end_time="12:30", sun_time_step_minutes=30, solar_declination_deg=0))
    xs = [s["shadow_direction_true_north"]["x"] for s in out["slices"]]
    assert xs[0] < 0
    assert abs(xs[1]) < 1e-6
    assert xs[2] > 0
    assert abs(xs[0] - xs[1]) < 0.25 and abs(xs[1] - xs[2]) < 0.25


def test_jst_missing_longitude_blocks_formal_calculation():
    out = solar(base(time_basis="japan_standard_time", equation_of_time_minutes=0))
    assert out["available"] is False
    assert any("site_longitude_deg" in b for b in out["blockers"])


def test_jst_missing_equation_of_time_blocks_formal_calculation():
    out = solar(base(time_basis="japan_standard_time", site_longitude_deg=135))
    assert out["available"] is False
    assert any("equation_of_time_minutes" in b for b in out["blockers"])


def test_true_solar_time_allows_missing_longitude():
    out = solar(base())
    assert out["available"] is True
    assert out["site_longitude_deg"] is None
