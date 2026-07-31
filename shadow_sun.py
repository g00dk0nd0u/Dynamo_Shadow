"""Formal technical solar calculation v1 (not permit-certified)."""
import math
import calendar
from datetime import date

from shadow_policies import LEGAL_CONSTANTS, SUN_POSITION_POLICY
from shadow_profiles import get_solar_profile

VALID_TIME_BASES = ("true_solar_time", "japan_standard_time")
VALID_SOLAR_PARAMETER_MODES = ("regulatory_winter_solstice_v1", "explicit", "date_derived_noaa_v1")
REGULATORY_DECLINATION_DEG = -23.439
SERIALIZED_ROUNDING_DECIMAL_PLACES = 6
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


def _derive_noaa_daily_solar_parameters(calculation_date):
    """Derive one reproducible daily parameter pair at local-standard noon."""
    blockers = []
    parsed = None
    try:
        text = str(calculation_date).strip()
        if len(text) != 10 or text[4] != "-" or text[7] != "-":
            raise ValueError("expected YYYY-MM-DD")
        parsed = date(int(text[0:4]), int(text[5:7]), int(text[8:10]))
        if parsed.isoformat() != text:
            raise ValueError("expected zero-padded YYYY-MM-DD")
    except Exception:
        blockers.append("settings.calculation_date must be a valid YYYY-MM-DD date.")
    result = {
        "available": parsed is not None,
        "source": "noaa_general_solar_position_calculations_v1",
        "calculation_date": parsed.isoformat() if parsed else None,
        "day_of_year": parsed.timetuple().tm_yday if parsed else None,
        "days_in_year": (366 if calendar.isleap(parsed.year) else 365) if parsed else None,
        "reference_hour_local_standard": 12.0,
        "fractional_year_rad": None,
        "solar_declination_deg": None,
        "equation_of_time_minutes": None,
        "blockers": blockers,
        "warnings": [],
    }
    if not parsed:
        return result
    gamma = (2.0 * math.pi / result["days_in_year"] *
             (result["day_of_year"] - 1 +
              (result["reference_hour_local_standard"] - 12.0) / 24.0))
    equation = 229.18 * (0.000075 + 0.001868 * math.cos(gamma)
                         - 0.032077 * math.sin(gamma)
                         - 0.014615 * math.cos(2.0 * gamma)
                         - 0.040849 * math.sin(2.0 * gamma))
    declination = (0.006918 - 0.399912 * math.cos(gamma)
                   + 0.070257 * math.sin(gamma)
                   - 0.006758 * math.cos(2.0 * gamma)
                   + 0.000907 * math.sin(2.0 * gamma)
                   - 0.002697 * math.cos(3.0 * gamma)
                   + 0.001480 * math.sin(3.0 * gamma))
    result.update({"fractional_year_rad": gamma,
                   "solar_declination_deg": math.degrees(declination),
                   "equation_of_time_minutes": equation})
    return result


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
    x = math.sin(_rad(azimuth_deg))
    y = math.cos(_rad(azimuth_deg))
    return {
        "x": 0.0 if abs(x) < 1e-15 else x,
        "y": 0.0 if abs(y) < 1e-15 else y,
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
            "conversion_performed": True,
            "longitude_sign_convention": "east_positive; 4 * (site_longitude_deg - standard_meridian_deg)",
            "equation_of_time_sign_convention": "positive values advance true solar time",
            "true_solar_minutes_raw": raw_true,
            "true_solar_minutes": normalized,
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
        "conversion_performed": False,
        "longitude_sign_convention": "east_positive; longitude metadata does not alter true_solar_time input",
        "equation_of_time_sign_convention": "not applied to true_solar_time input",
        "true_solar_minutes_raw": input_minutes,
        "true_solar_minutes": normalized,
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
        "shadow_length_factor": shadow_length_factor,
        "raw_shadow_length_factor": shadow_length_factor,
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
    """Build the reproducible v1 solar contract and its formal direction slices."""
    normalized = settings_normalized.get("normalized", {}) if isinstance(settings_normalized, dict) else {}
    warnings, blockers = [], []
    invalid_keys = set(settings_normalized.get("invalid_keys", [])) if isinstance(settings_normalized, dict) else set()
    solar_invalid = sorted(invalid_keys.intersection({
        "profile", "time_basis", "solar_parameter_mode", "site_latitude_deg",
        "site_longitude_deg", "standard_meridian_deg", "solar_declination_deg",
        "equation_of_time_minutes", "true_north_deg", "sun_time_step_minutes",
        "analysis_start_time", "analysis_end_time", "calculation_date",
    }))
    if solar_invalid:
        blockers.append("Invalid solar settings: {0}.".format(", ".join(solar_invalid)))
    time_basis = normalized.get("time_basis")
    latitude_deg = normalized.get("site_latitude_deg")
    true_north_deg = normalized.get("true_north_deg")
    standard_meridian_deg = normalized.get("standard_meridian_deg", 135.0)
    site_longitude_deg = normalized.get("site_longitude_deg")
    requested_mode = normalized.get("solar_parameter_mode")
    profile_name = normalized.get("profile")
    profile = get_solar_profile(profile_name)
    regulatory_profile_resolved = profile is not None
    if not profile:
        blockers.append("settings.profile must be one of: standard_8_16, hokkaido_9_15.")

    legacy_regulatory_shape = (requested_mode is None and time_basis == "true_solar_time" and
                               normalized.get("solar_declination_deg") is not None and
                               abs(normalized.get("solar_declination_deg") - REGULATORY_DECLINATION_DEG) <= 1e-9 and
                               regulatory_profile_resolved)
    parameter_mode = requested_mode or "explicit"
    mode_inferred = requested_mode is None and (
        normalized.get("solar_declination_deg") is not None or
        normalized.get("equation_of_time_minutes") is not None)
    if parameter_mode not in VALID_SOLAR_PARAMETER_MODES:
        blockers.append("settings.solar_parameter_mode must be one of: regulatory_winter_solstice_v1, explicit, date_derived_noaa_v1.")
    if legacy_regulatory_shape:
        warnings.append("Legacy winter-solstice settings remain in explicit mode without numerical change; regulatory_winter_solstice_v1 is recommended.")

    declination_deg = normalized.get("solar_declination_deg")
    equation = normalized.get("equation_of_time_minutes")
    derived = None
    if parameter_mode == "regulatory_winter_solstice_v1":
        if time_basis != "true_solar_time":
            blockers.append("regulatory_winter_solstice_v1 requires time_basis=true_solar_time.")
        if normalized.get("calculation_date") is not None or equation is not None:
            blockers.append("regulatory_winter_solstice_v1 must not include calculation_date or equation_of_time_minutes.")
        if declination_deg is not None and abs(declination_deg - REGULATORY_DECLINATION_DEG) > 1e-9:
            blockers.append("regulatory_winter_solstice_v1 does not accept a conflicting solar_declination_deg.")
        declination_deg = REGULATORY_DECLINATION_DEG
        equation = None
        source = "fixed_v1_regulatory_reference_constant"
    elif parameter_mode == "date_derived_noaa_v1":
        if declination_deg is not None or equation is not None:
            blockers.append("explicit solar parameters must not be supplied when solar_parameter_mode is date_derived_noaa_v1")
        derived = _derive_noaa_daily_solar_parameters(normalized.get("calculation_date"))
        blockers.extend(derived["blockers"])
        if derived["available"]:
            declination_deg, equation = derived["solar_declination_deg"], derived["equation_of_time_minutes"]
        source = "noaa_general_solar_position_calculations_v1"
    else:
        source = "explicit_settings"
        if declination_deg is None:
            blockers.append("settings.solar_declination_deg is required when solar_parameter_mode is explicit.")

    if time_basis not in VALID_TIME_BASES:
        blockers.append("settings.time_basis is required and must be one of: true_solar_time, japan_standard_time.")
    if latitude_deg is None: blockers.append("settings.site_latitude_deg is required.")
    if true_north_deg is None: blockers.append("settings.true_north_deg is required.")
    if time_basis == "japan_standard_time":
        if site_longitude_deg is None: blockers.append("settings.site_longitude_deg is required when settings.time_basis is japan_standard_time.")
        if equation is None: blockers.append("settings.equation_of_time_minutes or a date-derived value is required for japan_standard_time.")

    start_text = normalized.get("analysis_start_time") or (profile or {}).get("window_start")
    end_text = normalized.get("analysis_end_time") or (profile or {}).get("window_end")
    step = normalized.get("sun_time_step_minutes")
    if step is None and profile: step = profile["default_computational_step_minutes"]
    start_minutes = _parse_time_to_minutes(start_text, "analysis_start_time", warnings)
    end_minutes = _parse_time_to_minutes(end_text, "analysis_end_time", warnings)
    if start_minutes is None: blockers.append("settings.analysis_start_time or a known profile window is required.")
    if end_minutes is None: blockers.append("settings.analysis_end_time or a known profile window is required.")
    if not isinstance(step, int) or step <= 0: blockers.append("settings.sun_time_step_minutes must be a positive integer.")
    if start_minutes is not None and end_minutes is not None and end_minutes < start_minutes:
        blockers.append("settings.analysis_end_time must be at or after settings.analysis_start_time.")

    available = not blockers
    slices = []
    if available:
        minute = start_minutes
        while minute <= end_minutes:
            conversion = _build_solar_time_conversion(minute, time_basis, site_longitude_deg, standard_meridian_deg, equation)
            solar = _sun_position_for_true_solar_minutes(conversion["true_solar_minutes"], latitude_deg, declination_deg, true_north_deg)
            guard = normalized.get("max_shadow_length_factor")
            solar["exceeds_projection_guard"] = bool(solar["raw_shadow_length_factor"] is not None and guard is not None and solar["raw_shadow_length_factor"] > guard)
            item = {"input_time": _format_minutes(minute)}
            item.update(conversion); item.update(solar)
            if solar.get("warning"): warnings.append("{0}: {1}".format(item["input_time"], solar["warning"]))
            slices.append(item); minute += step
    complete_valid_slices = bool(available and slices and all(item.get("shadow_direction_model") is not None for item in slices))
    formal_ready = bool(available and complete_valid_slices)
    specification = {
        "specification_version": "jp_shadow_solar_v1", "status": "formal_technical_not_permit_certified",
        "regulatory_reference": "winter_solstice_true_solar_time", "profile": profile_name,
        "regulatory_region_scope": (profile or {}).get("regulatory_region_scope"),
        "solar_parameter_mode": parameter_mode, "time_basis": time_basis,
        "window_start": _format_minutes(start_minutes) if start_minutes is not None else None,
        "window_end": _format_minutes(end_minutes) if end_minutes is not None else None,
        "computational_step_minutes": step,
        "reference_shape_interval_minutes": (profile or {}).get("reference_shape_interval_minutes"),
        "declination_deg": declination_deg, "declination_source": source,
        "standard_meridian_deg": standard_meridian_deg,
        "longitude_correction_applied": available and time_basis == "japan_standard_time",
        "equation_of_time_applied": available and time_basis == "japan_standard_time",
        "atmospheric_refraction_applied": False, "true_north_convention": TRUE_NORTH_CONVENTION,
        "azimuth_convention": "clockwise_from_true_north", "internal_precision": "full_double_precision",
        "serialized_rounding_decimal_places": SERIALIZED_ROUNDING_DECIMAL_PLACES,
        "true_north_source_note": "true_north_deg is supplied through settings; automatic Revit ActiveProjectLocation extraction is not implemented.",
        "permit_ready_certified": False,
    }
    return {
        "available": available, "complete": complete_valid_slices,
        "calculation_mode": parameter_mode, "solar_parameter_mode": parameter_mode,
        "solar_parameter_mode_inferred_for_backward_compatibility": mode_inferred,
        "legacy_compatibility_note": warnings[0] if legacy_regulatory_shape else None,
        "recommended_mode": "regulatory_winter_solstice_v1",
        "user_supplied_parameters": parameter_mode == "explicit",
        "regulatory_profile_validated": parameter_mode == "regulatory_winter_solstice_v1" and regulatory_profile_resolved,
        "reference_algorithm": parameter_mode == "date_derived_noaa_v1", "regulatory_default": False,
        "solar_parameter_source": source, "solar_parameter_source_available": declination_deg is not None,
        "solar_parameters_resolved": declination_deg is not None and not bool(blockers),
        "calculation_date": derived["calculation_date"] if derived else normalized.get("calculation_date"),
        "day_of_year": derived["day_of_year"] if derived else None, "days_in_year": derived["days_in_year"] if derived else None,
        "parameter_reference_hour_local_standard": derived["reference_hour_local_standard"] if derived else None,
        "fractional_year_rad": derived["fractional_year_rad"] if derived else None,
        "input_time_basis": time_basis, "output_time_basis": "true_solar_time",
        "standard_meridian_deg": standard_meridian_deg, "site_latitude_deg": latitude_deg,
        "site_longitude_deg": site_longitude_deg, "equation_of_time_minutes": equation,
        "solar_declination_deg": declination_deg, "true_north_deg": true_north_deg,
        "start_time": start_text, "end_time": end_text, "time_step_minutes": step,
        "longitude_correction_minutes": (None if not available or time_basis != "japan_standard_time" else _round(4.0 * (site_longitude_deg - standard_meridian_deg))),
        "equation_of_time_applied": available and time_basis == "japan_standard_time",
        "longitude_correction_applied": available and time_basis == "japan_standard_time",
        "slice_count": len(slices), "slices": slices, "blockers": blockers, "warnings": warnings,
        "atmospheric_refraction_applied": False,
        "date_based_declination_calculated": bool(derived and derived.get("available")),
        "date_based_equation_of_time_calculated": bool(derived and derived.get("available")),
        "solar_specification": specification,
        "formal_solar_calculation_ready": formal_ready,
        "regulatory_profile_resolved": regulatory_profile_resolved,
        "solar_coordinate_convention_resolved": true_north_deg is not None,
        "solar_reference_validation_passed": parameter_mode in VALID_SOLAR_PARAMETER_MODES,
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
