# Settings coercion and normalization.
import json
import math
from shadow_policies import SETTINGS_SCHEMA_VERSION, SETTINGS_REQUIRED_FOR_EQUAL_TIME_SHADOW, SETTINGS_DIAGNOSTIC_DEFAULTS
from shadow_utils import *


def _object_items_from_keys_values(value):
    keys = _safe_attr(value, "Keys")
    values = _safe_attr(value, "Values")
    if keys is None or values is None:
        return None
    try:
        return zip(list(keys), list(values))
    except Exception:
        return None

def _coerce_settings_to_dict(settings):
    warnings = []
    errors = []
    if settings is None:
        return {}, "none", warnings, errors
    try:
        if isinstance(settings, dict):
            return dict(settings), "python_dict", warnings, errors
        if _is_string(settings):
            text = settings.strip()
            if not text:
                return {}, "empty_string", ["settings JSON string is empty; treated as missing optional settings."], errors
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    return parsed, "json_string", warnings, errors
                warnings.append("settings JSON string did not decode to an object; treated as empty settings.")
                return {}, "json_string_non_object", warnings, errors
            except Exception as exc:
                warnings.append("settings JSON string could not be parsed; treated as empty settings: {0}".format(_safe_text(exc)))
                return {}, "json_string_parse_failed", warnings, errors
        pairs = _object_items_from_keys_values(settings)
        if pairs is not None:
            try:
                return dict(pairs), "keys_values_object", warnings, errors
            except Exception as exc:
                warnings.append("settings Keys/Values object could not be converted to dict; treated as empty settings: {0}".format(_safe_text(exc)))
                return {}, "keys_values_object_failed", warnings, errors
        try:
            if hasattr(settings, "items"):
                return dict(settings.items()), "items_object", warnings, errors
        except Exception as exc:
            warnings.append("settings items() object could not be converted to dict; trying sequence fallback: {0}".format(_safe_text(exc)))
        if _is_sequence(settings):
            try:
                return dict(settings), "pairs_sequence", warnings, errors
            except Exception as exc:
                warnings.append("settings sequence could not be converted from key-value pairs; treated as empty settings: {0}".format(_safe_text(exc)))
                return {}, "pairs_sequence_failed", warnings, errors
        warnings.append("settings input type {0} is not supported; treated as empty optional settings.".format(_type_name(settings)))
        return {}, "unsupported", warnings, errors
    except Exception as exc:
        warnings.append("settings coercion failed safely; treated as empty settings: {0}".format(_safe_text(exc)))
        return {}, "coercion_exception", warnings, errors

def _parse_float(value, key):
    if value is None:
        return None, None
    if _is_string(value) and not value.strip():
        return None, None
    try:
        parsed = float(value)
    except Exception:
        return None, "settings.{0} must be numeric; got {1}.".format(key, _safe_text(value))
    if math.isnan(parsed) or math.isinf(parsed):
        return None, "settings.{0} cannot be NaN or infinity.".format(key)
    return parsed, None

def _parse_int(value, key):
    parsed, warning = _parse_float(value, key)
    if parsed is None:
        return None, warning
    if int(parsed) != parsed:
        return None, "settings.{0} must be an integer; got {1}.".format(key, _safe_text(value))
    return int(parsed), None

def _parse_text(value, key):
    if value is None:
        return None, None
    try:
        text = str(value).strip()
    except Exception:
        return None, "settings.{0} could not be converted to text.".format(key)
    if not text:
        return None, None
    return text, None

def _parse_bool(value, key):
    if value is None:
        return None, None
    if isinstance(value, bool):
        return value, None
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value), None
    if _is_string(value):
        text = value.strip().lower()
        if text in ("true", "1", "yes", "on"):
            return True, None
        if text in ("false", "0", "no", "off", ""):
            return False, None
    return None, "settings.{0} must be boolean; got {1}.".format(key, _safe_text(value))

def _parse_debug_log_dir(value):
    text, warn = _parse_text(value, "debug_log_dir")
    if warn:
        return None, warn
    if text is None:
        return SETTINGS_DIAGNOSTIC_DEFAULTS["debug_log_dir"], None
    normalized = text.replace("\\", "/").strip("/")
    if not normalized:
        return SETTINGS_DIAGNOSTIC_DEFAULTS["debug_log_dir"], None
    if text.startswith("/") or ":" in text:
        return SETTINGS_DIAGNOSTIC_DEFAULTS["debug_log_dir"], "settings.debug_log_dir must be a relative path; absolute paths are rejected and default debug_logs is used."
    parts = [p for p in normalized.split("/") if p]
    if ".." in parts:
        return SETTINGS_DIAGNOSTIC_DEFAULTS["debug_log_dir"], "settings.debug_log_dir must not contain '..'; default debug_logs is used."
    return "/".join(parts), None

def _parse_debug_log_filename(value):
    text, warn = _parse_text(value, "debug_log_filename")
    if warn:
        return None, warn
    if text is None:
        return SETTINGS_DIAGNOSTIC_DEFAULTS["debug_log_filename"], None
    if "/" in text or "\\" in text or ".." in text or not text.endswith(".json"):
        return SETTINGS_DIAGNOSTIC_DEFAULTS["debug_log_filename"], "settings.debug_log_filename must be a fixed .json filename without path separators or '..'; default latest_debug.json is used."
    if text.startswith("run_") or text.startswith("raw_") or text.startswith("private_"):
        return SETTINGS_DIAGNOSTIC_DEFAULTS["debug_log_filename"], "settings.debug_log_filename must not use run_, raw_, or private_ growth patterns; default latest_debug.json is used."
    return text, None

def _range_warning(key, value):
    if value is None:
        return None
    ranges = {
        "latitude": (-90.0, 90.0, True, True),
        "site_latitude_deg": (-90.0, 90.0, True, True),
        "longitude": (-180.0, 180.0, True, True),
        "site_longitude_deg": (-180.0, 180.0, True, True),
        "solar_declination_deg": (-90.0, 90.0, True, True),
        "true_north_deg": (-360.0, 360.0, True, True),
        "measurement_height_m": (0.0, None, False, True),
        "grid_resolution_m": (0.0, None, False, True),
        "analysis_margin_m": (0.0, None, True, True),
        "closure_tolerance_m": (0.0, None, False, True),
    }
    if key not in ranges:
        return None
    low, high, low_inc, high_inc = ranges[key]
    if low is not None and (value < low or (value == low and not low_inc)):
        return "settings.{0} is outside the accepted range.".format(key)
    if high is not None and (value > high or (value == high and not high_inc)):
        return "settings.{0} is outside the accepted range.".format(key)
    return None

def _normalize_settings(settings, level=None):
    settings_dict, input_format, warnings, errors = _coerce_settings_to_dict(settings)
    normalized = {}
    defaults_applied = []
    invalid_keys = []
    info = []
    known = set(["profile", "average_ground_level_elevation_m", "measurement_height_m", "measurement_plane_elevation_m", "latitude", "longitude", "site_latitude_deg", "site_longitude_deg", "solar_declination_deg", "time_basis", "true_solar_start_time", "true_solar_end_time", "sun_time_step_minutes", "true_north_deg", "grid_resolution_m", "analysis_margin_m", "closure_tolerance_m", "debug_log_enabled", "debug_log_dir", "debug_log_filename"])
    ignored_keys = sorted([_safe_text(k) for k in settings_dict.keys() if k not in known])
    if ignored_keys:
        info.append("Unknown settings keys are ignored by v1 diagnostics: {0}".format(", ".join(ignored_keys)))

    profile, warn = _parse_text(settings_dict.get("profile"), "profile")
    if warn:
        warnings.append(warn); invalid_keys.append("profile")
    if profile is None:
        profile = SETTINGS_DIAGNOSTIC_DEFAULTS["profile"]; defaults_applied.append("profile")
    normalized["profile"] = profile

    debug_log_enabled, warn = _parse_bool(settings_dict.get("debug_log_enabled"), "debug_log_enabled")
    if warn:
        warnings.append(warn); invalid_keys.append("debug_log_enabled")
    if debug_log_enabled is None:
        debug_log_enabled = SETTINGS_DIAGNOSTIC_DEFAULTS["debug_log_enabled"]; defaults_applied.append("debug_log_enabled")
    normalized["debug_log_enabled"] = debug_log_enabled

    debug_log_dir, warn = _parse_debug_log_dir(settings_dict.get("debug_log_dir"))
    if warn:
        warnings.append(warn); invalid_keys.append("debug_log_dir")
    if settings_dict.get("debug_log_dir") is None:
        defaults_applied.append("debug_log_dir")
    normalized["debug_log_dir"] = debug_log_dir

    debug_log_filename, warn = _parse_debug_log_filename(settings_dict.get("debug_log_filename"))
    if warn:
        warnings.append(warn); invalid_keys.append("debug_log_filename")
    if settings_dict.get("debug_log_filename") is None:
        defaults_applied.append("debug_log_filename")
    normalized["debug_log_filename"] = debug_log_filename

    for key in ["average_ground_level_elevation_m", "measurement_height_m", "latitude", "longitude", "site_latitude_deg", "site_longitude_deg", "solar_declination_deg", "true_north_deg", "grid_resolution_m", "analysis_margin_m", "closure_tolerance_m"]:
        value, warn = _parse_float(settings_dict.get(key), key)
        range_warn = _range_warning(key, value)
        if warn or range_warn:
            warnings.append(warn or range_warn)
            invalid_keys.append(key)
            value = None
        if value is None and key in SETTINGS_DIAGNOSTIC_DEFAULTS:
            value = SETTINGS_DIAGNOSTIC_DEFAULTS[key]
            defaults_applied.append(key)
        normalized[key] = value

    if normalized.get("site_latitude_deg") is None and normalized.get("latitude") is not None:
        normalized["site_latitude_deg"] = normalized.get("latitude")
        info.append("settings.latitude is accepted as a compatibility alias for settings.site_latitude_deg.")
    if normalized.get("site_longitude_deg") is None and normalized.get("longitude") is not None:
        normalized["site_longitude_deg"] = normalized.get("longitude")
        info.append("settings.longitude is accepted as a compatibility alias for settings.site_longitude_deg; longitude is not used by true_solar_time diagnostics.")

    time_basis, warn = _parse_text(settings_dict.get("time_basis"), "time_basis")
    if warn:
        warnings.append(warn); invalid_keys.append("time_basis")
    if time_basis is None:
        time_basis = "true_solar_time"; defaults_applied.append("time_basis")
    normalized["time_basis"] = time_basis

    for key in ["true_solar_start_time", "true_solar_end_time"]:
        text, warn = _parse_text(settings_dict.get(key), key)
        if warn:
            warnings.append(warn); invalid_keys.append(key)
        normalized[key] = text

    sun_step, warn = _parse_int(settings_dict.get("sun_time_step_minutes"), "sun_time_step_minutes")
    if warn:
        warnings.append(warn); invalid_keys.append("sun_time_step_minutes")
    normalized["sun_time_step_minutes"] = sun_step

    agl = normalized.get("average_ground_level_elevation_m")
    mh = normalized.get("measurement_height_m")
    if agl is not None and mh is not None:
        mpe = agl + mh
        measurement_plane = {"available": True, "elevation_m": mpe, "formula": "average_ground_level_elevation_m + measurement_height_m"}
    else:
        mpe = None
        measurement_plane = {"available": False, "elevation_m": None, "reason": "missing average_ground_level_elevation_m or measurement_height_m"}
    normalized["measurement_plane_elevation_m"] = mpe

    missing_required = [k for k in SETTINGS_REQUIRED_FOR_EQUAL_TIME_SHADOW if normalized.get(k) is None]
    invalid_for_equal = [k for k in invalid_keys if k in SETTINGS_REQUIRED_FOR_EQUAL_TIME_SHADOW]
    if settings is None:
        info.append("settings is optional for input diagnostics; missing settings is not fatal.")
    info.append("Revit Level Elevation is not used as average ground level or measurement plane.")
    return {
        "provided": settings is not None,
        "schema_version": SETTINGS_SCHEMA_VERSION,
        "input_format": input_format,
        "raw_type": _type_name(settings),
        "normalized": normalized,
        "measurement_plane": measurement_plane,
        "readiness": {
            "ready_for_input_diagnostics": True,
            "ready_for_equal_time_shadow_calculation": len(missing_required) == 0 and len(invalid_for_equal) == 0,
            "settings_ready_for_boundary_dependent_steps": len(missing_required) == 0 and len(invalid_for_equal) == 0,
            "missing_for_equal_time_shadow": missing_required,
            "invalid_for_equal_time_shadow": invalid_for_equal,
        },
        "defaults_applied": defaults_applied,
        "missing_required_keys": missing_required,
        "invalid_keys": sorted(set(invalid_keys)),
        "ignored_keys": ignored_keys,
        "warnings": warnings,
        "errors": errors,
        "info": info,
        "level_reference_present": level is not None,
        "level_used_as_average_ground_level": False,
        "level_used_as_measurement_plane": False,
    }
