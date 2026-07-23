# Diagnostic-only solar-time conversion and sun position table.
import math

from shadow_policies import LEGAL_CONSTANTS, SUN_POSITION_POLICY

VALID_TIME_BASES = ("true_solar_time", "japan_standard_time")
TRUE_NORTH_CONVENTION = "true_north_deg is measured clockwise from the model +Y axis to true north; model_azimuth_deg=(true_north_azimuth_deg+true_north_deg)%360."


def _parse_time_to_minutes(value, key, warnings):
    if value is None:
        return None
    try:
        text = str(value).strip()
        parts = text.split(":")
        if len(parts) != 2:
            raise ValueError("expected HH:MM")
        hour = int(parts[0])
        minute = int(parts[1])
        if hour < 0 or hour > 24 or minute < 0 or minute >= 60 or (hour == 24 and minute != 0):
            raise ValueError("outside 00:00-24:00")
        return hour * 60 + minute
    except Exception:
        warnings.append("settings.{0} must be an HH:MM value; got {1}.".format(key, value))
        return None


def _format_minutes(minutes):
    rounded_seconds = int(round(float(minutes) * 60.0))
    day_seconds = 24 * 60 * 60
    rounded_seconds = rounded_seconds % day_seconds
    hour = rounded_seconds // 3600
    minute = (rounded_seconds % 3600) // 60
    second = rounded_seconds % 60
    return "{0:02d}:{1:02d}:{2:02d}".format(hour, minute, second)


def _deg(value):
    return value * 180.0 / math.pi


def _rad(value):
    return value * math.pi / 180.0


def _round(value, digits=6):
    if value is None:
        return None
    return round(value, digits)


def _normalize_minutes_with_day_offset(minutes):
    day_offset = math.floor(minutes / 1440.0)
    normalized = minutes - day_offset * 1440.0
    if abs(normalized - 1440.0) < 1e-9:
        normalized = 0.0
        day_offset += 1
    return normalized, int(day_offset)


def _jst_minutes_to_true_solar_minutes(japan_standard_time_minutes, site_longitude_deg, standard_meridian_deg, equation_of_time_minutes):
    longitude_correction_minutes = 4.0 * (site_longitude_deg - standard_meridian_deg)
    return japan_standard_time_minutes + longitude_correction_minutes + equation_of_time_minutes


def _direction_from_azimuth(azimuth_deg, basis):
    return {
        "x": _round(math.sin(_rad(azimuth_deg))),
        "y": _round(math.cos(_rad(azimuth_deg))),
        "z": 0.0,
        "basis": basis,
    }


def _model_direction_from_true_north_azimuth(azimuth_true_north_deg, true_north_deg):
    model_azimuth_deg = (azimuth_true_north_deg + true_north_deg) % 360.0
    return model_azimuth_deg, _direction_from_azimuth(model_azimuth_deg, "unit_horizontal_vector_model_xy_axes")


def _build_solar_time_conversion(input_minutes, input_time_basis, site_longitude_deg, standard_meridian_deg, equation_of_time_minutes):
    if input_time_basis not in VALID_TIME_BASES:
        raise ValueError("input_time_basis must be one of: true_solar_time, japan_standard_time.")
    if input_time_basis == "japan_standard_time":
        raw_true = _jst_minutes_to_true_solar_minutes(input_minutes, site_longitude_deg, standard_meridian_deg, equation_of_time_minutes)
        normalized, day_offset = _normalize_minutes_with_day_offset(raw_true)
        return {
            "input_minutes": input_minutes,
            "input_time_basis": input_time_basis,
            "true_solar_minutes_raw": _round(raw_true),
            "true_solar_minutes": _round(normalized),
            "true_solar_time": _format_minutes(normalized),
            "day_offset": day_offset,
            "longitude_correction_minutes": _round(4.0 * (site_longitude_deg - standard_meridian_deg)),
            "longitude_correction_applied": True,
            "equation_of_time_applied": True,
            "input_time_already_true_solar": False,
        }
    normalized, day_offset = _normalize_minutes_with_day_offset(input_minutes)
    return {
        "input_minutes": input_minutes,
        "input_time_basis": input_time_basis,
        "true_solar_minutes_raw": _round(input_minutes),
        "true_solar_minutes": _round(normalized),
        "true_solar_time": _format_minutes(normalized),
        "day_offset": day_offset,
        "longitude_correction_minutes": None,
        "longitude_correction_applied": False,
        "equation_of_time_applied": False,
        "input_time_already_true_solar": True,
    }


def _sun_position_for_true_solar_minutes(minutes, latitude_deg, declination_deg, true_north_deg):
    true_solar_hours = minutes / 60.0
    hour_angle_deg = 15.0 * (true_solar_hours - 12.0)
    lat = _rad(latitude_deg)
    dec = _rad(declination_deg)
    hour_angle = _rad(hour_angle_deg)
    sin_altitude = math.sin(lat) * math.sin(dec) + math.cos(lat) * math.cos(dec) * math.cos(hour_angle)
    sin_altitude = max(-1.0, min(1.0, sin_altitude))
    altitude = math.asin(sin_altitude)
    altitude_deg = _deg(altitude)
    azimuth_rad = math.atan2(math.sin(hour_angle), math.cos(hour_angle) * math.sin(lat) - math.tan(dec) * math.cos(lat)) + math.pi
    azimuth_deg = (_deg(azimuth_rad) + 360.0) % 360.0
    warning = None
    if altitude_deg > 0.0:
        shadow_length_factor = 1.0 / math.tan(altitude)
        shadow_azimuth_true = (azimuth_deg + 180.0) % 360.0
        shadow_direction_true = _direction_from_azimuth(shadow_azimuth_true, "unit_horizontal_vector_away_from_sun_true_north_axes")
        shadow_azimuth_model, shadow_direction_model = _model_direction_from_true_north_azimuth(shadow_azimuth_true, true_north_deg)
    else:
        shadow_length_factor = None
        shadow_azimuth_true = None
        shadow_direction_true = None
        shadow_azimuth_model = None
        shadow_direction_model = None
        warning = "Solar altitude is at or below the horizon; shadow length factor and shadow vectors are omitted."
    return {
        "hour_angle_deg": _round(hour_angle_deg),
        "solar_declination_deg": declination_deg,
        "solar_altitude_deg": _round(altitude_deg),
        "solar_azimuth_deg": _round(azimuth_deg),
        "shadow_azimuth_true_north_deg": _round(shadow_azimuth_true),
        "shadow_length_factor": _round(shadow_length_factor),
        "shadow_direction_true_north": shadow_direction_true,
        "shadow_direction_vector": None if shadow_direction_true is None else {"x_east": shadow_direction_true.get("x"), "y_north": shadow_direction_true.get("y"), "z_up": 0.0, "basis": shadow_direction_true.get("basis")},
        "true_north_deg": true_north_deg,
        "true_north_convention": TRUE_NORTH_CONVENTION,
        "shadow_azimuth_model_deg": _round(shadow_azimuth_model),
        "shadow_direction_model": shadow_direction_model,
        "atmospheric_refraction_applied": False,
        "warning": warning,
    }


def _build_solar_calculation_v1(settings_normalized):
    normalized = settings_normalized.get("normalized", {}) if isinstance(settings_normalized, dict) else {}
    warnings = []
    blockers = []
    time_basis = normalized.get("time_basis")
    if time_basis not in VALID_TIME_BASES:
        blockers.append("settings.time_basis is required and must be one of: true_solar_time, japan_standard_time.")
    latitude_deg = normalized.get("site_latitude_deg")
    declination_deg = normalized.get("solar_declination_deg")
    true_north_deg = normalized.get("true_north_deg")
    standard_meridian_deg = normalized.get("standard_meridian_deg")
    site_longitude_deg = normalized.get("site_longitude_deg")
    equation = normalized.get("equation_of_time_minutes")
    if latitude_deg is None: blockers.append("settings.site_latitude_deg is required.")
    if declination_deg is None: blockers.append("settings.solar_declination_deg is required; date-based calculation is not implemented.")
    if true_north_deg is None: blockers.append("settings.true_north_deg is required.")
    if time_basis == "japan_standard_time":
        if site_longitude_deg is None: blockers.append("settings.site_longitude_deg is required when settings.time_basis is japan_standard_time.")
        if equation is None: blockers.append("settings.equation_of_time_minutes is required when settings.time_basis is japan_standard_time.")
    start_key = "analysis_start_time"
    end_key = "analysis_end_time"
    start_text = normalized.get(start_key)
    end_text = normalized.get(end_key)
    if time_basis == "true_solar_time":
        if start_text is None and normalized.get("true_solar_start_time") is not None:
            start_text = normalized.get("true_solar_start_time"); start_key = "true_solar_start_time"
        if end_text is None and normalized.get("true_solar_end_time") is not None:
            end_text = normalized.get("true_solar_end_time"); end_key = "true_solar_end_time"
    if start_text is None: blockers.append("settings.analysis_start_time is required as HH:MM.")
    if end_text is None: blockers.append("settings.analysis_end_time is required as HH:MM.")
    start_minutes = _parse_time_to_minutes(start_text, start_key, warnings)
    end_minutes = _parse_time_to_minutes(end_text, end_key, warnings)
    if start_text is not None and start_minutes is None: blockers.append("settings.{0} must be a valid HH:MM time.".format(start_key))
    if end_text is not None and end_minutes is None: blockers.append("settings.{0} must be a valid HH:MM time.".format(end_key))
    step = normalized.get("sun_time_step_minutes")
    if not isinstance(step, int) or step <= 0:
        blockers.append("settings.sun_time_step_minutes is required and must be a positive integer.")
    if start_minutes is not None and end_minutes is not None and end_minutes < start_minutes:
        blockers.append("settings.analysis_end_time must be at or after settings.analysis_start_time in the input time basis.")
    available = len(blockers) == 0
    slices = []
    if available:
        minute = start_minutes
        while minute <= end_minutes:
            conversion = _build_solar_time_conversion(minute, time_basis, site_longitude_deg, standard_meridian_deg, equation)
            solar = _sun_position_for_true_solar_minutes(conversion["true_solar_minutes"], latitude_deg, declination_deg, true_north_deg)
            item = {"input_time": _format_minutes(minute), "input_time_basis": time_basis}
            item.update(conversion)
            item.update(solar)
            if solar.get("warning"):
                warnings.append("{0}: {1}".format(item["input_time"], solar["warning"]))
            slices.append(item)
            minute += step
    return {
        "available": available,
        "complete": available,
        "calculation_mode": "explicit_declination_and_equation_of_time_v1",
        "input_time_basis": time_basis,
        "output_time_basis": "true_solar_time",
        "standard_meridian_deg": standard_meridian_deg,
        "site_latitude_deg": latitude_deg,
        "site_longitude_deg": site_longitude_deg,
        "equation_of_time_minutes": equation,
        "solar_declination_deg": declination_deg,
        "true_north_deg": true_north_deg,
        "start_time": start_text,
        "end_time": end_text,
        "time_step_minutes": step,
        "longitude_correction_minutes": None if not available or time_basis != "japan_standard_time" else _round(4.0 * (site_longitude_deg - standard_meridian_deg)),
        "equation_of_time_applied": available and time_basis == "japan_standard_time",
        "longitude_correction_applied": available and time_basis == "japan_standard_time",
        "slice_count": len(slices),
        "slices": slices,
        "blockers": blockers,
        "warnings": warnings,
        "atmospheric_refraction_applied": False,
        "date_based_declination_calculated": False,
        "date_based_equation_of_time_calculated": False,
        "permit_ready_certified": False,
    }


def _build_sun_position_diagnostics(settings_normalized):
    solar = _build_solar_calculation_v1(settings_normalized)
    diagnostics = {
        "available": solar["available"],
        "diagnostic_only": True,
        "time_basis": solar["input_time_basis"],
        "legacy_time_basis_fallback_performed": False,
        "jst_conversion_performed": solar["longitude_correction_applied"],
        "equation_of_time_correction_performed": solar["equation_of_time_applied"],
        "standard_meridian_135e_used_for_calculation": solar["standard_meridian_deg"] == 135.0,
        "site_latitude_deg": solar["site_latitude_deg"],
        "solar_declination_deg": solar["solar_declination_deg"],
        "start_time": solar["start_time"],
        "end_time": solar["end_time"],
        "time_step_minutes": solar["time_step_minutes"],
        "slice_count": solar["slice_count"],
        "warnings": list(solar["warnings"]) + list(solar["blockers"]),
    }
    return solar["slices"], diagnostics, SUN_POSITION_POLICY, solar
