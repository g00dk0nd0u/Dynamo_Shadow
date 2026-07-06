# Diagnostic-only true-solar-time sun position table.
import math

from shadow_policies import LEGAL_CONSTANTS, SUN_POSITION_POLICY


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
        warnings.append("settings.{0} must be a true-solar-time HH:MM value; got {1}.".format(key, value))
        return None


def _format_minutes(minutes):
    hour = int(minutes // 60)
    minute = int(minutes % 60)
    return "{0:02d}:{1:02d}".format(hour, minute)


def _deg(value):
    return value * 180.0 / math.pi


def _rad(value):
    return value * math.pi / 180.0


def _round(value, digits=6):
    if value is None:
        return None
    return round(value, digits)


def _sun_position_for_minutes(minutes, latitude_deg, declination_deg):
    true_solar_hours = minutes / 60.0
    hour_angle_deg = 15.0 * (true_solar_hours - 12.0)
    lat = _rad(latitude_deg)
    dec = _rad(declination_deg)
    hour_angle = _rad(hour_angle_deg)

    sin_altitude = math.sin(lat) * math.sin(dec) + math.cos(lat) * math.cos(dec) * math.cos(hour_angle)
    sin_altitude = max(-1.0, min(1.0, sin_altitude))
    altitude = math.asin(sin_altitude)
    altitude_deg = _deg(altitude)
    zenith_deg = 90.0 - altitude_deg

    azimuth_rad = math.atan2(
        math.sin(hour_angle),
        math.cos(hour_angle) * math.sin(lat) - math.tan(dec) * math.cos(lat),
    ) + math.pi
    azimuth_deg = (_deg(azimuth_rad) + 360.0) % 360.0

    if altitude_deg > 0.0:
        shadow_length_factor = 1.0 / math.tan(altitude)
        shadow_azimuth_deg = (azimuth_deg + 180.0) % 360.0
        shadow_direction_vector = {
            "x_east": _round(math.sin(_rad(shadow_azimuth_deg))),
            "y_north": _round(math.cos(_rad(shadow_azimuth_deg))),
            "z_up": 0.0,
            "basis": "unit_horizontal_vector_away_from_sun_true_north_axes",
        }
    else:
        shadow_length_factor = None
        shadow_direction_vector = None

    return {
        "true_solar_time": _format_minutes(minutes),
        "hour_angle_deg": _round(hour_angle_deg),
        "solar_altitude_deg": _round(altitude_deg),
        "solar_azimuth_deg": _round(azimuth_deg),
        "zenith_deg": _round(zenith_deg),
        "shadow_length_factor": _round(shadow_length_factor),
        "shadow_direction_vector": shadow_direction_vector,
    }


def _build_sun_position_diagnostics(settings_normalized):
    warnings = []
    normalized = settings_normalized.get("normalized", {}) if isinstance(settings_normalized, dict) else {}
    latitude_deg = normalized.get("site_latitude_deg")
    declination_deg = normalized.get("solar_declination_deg")
    time_basis = normalized.get("time_basis") or "true_solar_time"
    start_text = normalized.get("true_solar_start_time") or LEGAL_CONSTANTS["standard_start_time"]
    end_text = normalized.get("true_solar_end_time") or LEGAL_CONSTANTS["standard_end_time"]
    step_minutes = normalized.get("sun_time_step_minutes") or LEGAL_CONSTANTS["time_step_minutes"]

    if time_basis != "true_solar_time":
        warnings.append("Only settings.time_basis='true_solar_time' is supported for sun position diagnostics in this PR; no JST conversion is performed.")
    if latitude_deg is None:
        warnings.append("settings.site_latitude_deg is required for diagnostic sun position calculations; missing latitude is non-fatal.")
    if declination_deg is None:
        warnings.append("settings.solar_declination_deg is required for v1 diagnostic sun position calculations; missing declination is non-fatal.")

    start_minutes = _parse_time_to_minutes(start_text, "true_solar_start_time", warnings)
    end_minutes = _parse_time_to_minutes(end_text, "true_solar_end_time", warnings)
    try:
        step_minutes = int(step_minutes)
    except Exception:
        step_minutes = LEGAL_CONSTANTS["time_step_minutes"]
        warnings.append("settings.sun_time_step_minutes must be an integer; default 30 minutes is used.")
    if step_minutes != 30:
        warnings.append("Only 30-minute sun time slices are supported in this PR; default 30 minutes is used.")
        step_minutes = 30

    available = latitude_deg is not None and declination_deg is not None and time_basis == "true_solar_time" and start_minutes is not None and end_minutes is not None and end_minutes >= start_minutes
    if start_minutes is not None and end_minutes is not None and end_minutes < start_minutes:
        warnings.append("settings.true_solar_end_time must be at or after settings.true_solar_start_time; sun table is not built.")

    slices = []
    if available:
        minute = start_minutes
        while minute <= end_minutes:
            slices.append(_sun_position_for_minutes(minute, latitude_deg, declination_deg))
            minute += step_minutes

    diagnostics = {
        "available": available,
        "diagnostic_only": True,
        "time_basis": "true_solar_time",
        "jst_conversion_performed": False,
        "equation_of_time_correction_performed": False,
        "standard_meridian_135e_used_for_calculation": False,
        "site_latitude_deg": latitude_deg,
        "solar_declination_deg": declination_deg,
        "start_time": start_text,
        "end_time": end_text,
        "time_step_minutes": step_minutes,
        "slice_count": len(slices),
        "warnings": warnings,
    }
    return slices, diagnostics, SUN_POSITION_POLICY
