# script.py
# Dynamo_Shadow v0 input diagnostics skeleton.
#
# This script intentionally does not perform shadow, sun-position, or
# equal-time contour calculations yet. It only summarizes Dynamo inputs so the
# next implementation steps can be validated safely from Dynamo/Revit.

import traceback

TOOL_NAME = "Dynamo_Shadow"
STAGE_NAME = "v0_input_diagnostics"

LEGAL_CONSTANTS = {
    "date_basis": "winter_solstice",
    "standard_start_time": "08:00",
    "standard_end_time": "16:00",
    "time_step_minutes": 30,
    "measurement_line_near_m": 5.0,
    "measurement_line_far_m": 10.0,
    "standard_profile_note": "Standard Building Standard Law shadow period. Regional exceptions such as Hokkaido should be handled by future profiles.",
    "regional_exception_examples": {
        "hokkaido_start_time": "09:00",
        "hokkaido_end_time": "15:00",
    },
}

PLANNED_PIPELINE = [
    "input extraction",
    "sun position / shadow direction",
    "time-slice shadow geometry",
    "accumulation",
    "equal-time contour generation",
    "diagnostics and validation",
]

INPUT_KEYS = [
    "building_elements",
    "site_boundary",
    "level",
    "settings",
]


def _get_global(name, default=None):
    try:
        return globals().get(name, default)
    except Exception:
        return default


def _fallback_in(index, default=None):
    values = _get_global("IN", None)
    try:
        if values is not None and len(values) > index:
            return values[index]
    except Exception:
        pass
    return default


def _read_inputs():
    """Read named INPUTS first, then fall back to legacy IN[] positions."""
    named_inputs = _get_global("INPUTS", None)
    result = {}
    source = "IN"

    if isinstance(named_inputs, dict):
        source = "INPUTS"
        for index, key in enumerate(INPUT_KEYS):
            if key in named_inputs:
                result[key] = named_inputs.get(key)
            else:
                result[key] = _fallback_in(index)
    else:
        for index, key in enumerate(INPUT_KEYS):
            result[key] = _fallback_in(index)

    return result, source


def _try_unwrap(value):
    unwrap = _get_global("UnwrapElement", None)
    if unwrap is None:
        return value
    try:
        return unwrap(value)
    except Exception:
        return value


def _is_string(value):
    try:
        return isinstance(value, basestring)
    except NameError:
        return isinstance(value, str)


def _is_sequence(value):
    if value is None or _is_string(value):
        return False
    if isinstance(value, dict):
        return False
    try:
        iter(value)
        return True
    except Exception:
        return False


def _to_list(value):
    if value is None:
        return []
    if _is_sequence(value):
        try:
            return list(value)
        except Exception:
            return [value]
    return [value]


def _safe_text(value):
    if value is None:
        return None
    try:
        text = str(value)
    except Exception:
        try:
            text = repr(value)
        except Exception:
            text = "<unrepresentable>"
    if len(text) > 160:
        return text[:157] + "..."
    return text


def _safe_attr(value, attr):
    try:
        attr_value = getattr(value, attr)
    except Exception:
        return None
    try:
        if callable(attr_value):
            return attr_value()
    except Exception:
        return None
    return attr_value


def _element_id(value):
    element_id = _safe_attr(value, "Id")
    if element_id is None:
        return None
    for attr in ("IntegerValue", "Value"):
        raw = _safe_attr(element_id, attr)
        if raw is not None:
            try:
                return int(raw)
            except Exception:
                return _safe_text(raw)
    return _safe_text(element_id)


def _element_name(value):
    for attr in ("Name", "FamilyName"):
        name = _safe_attr(value, attr)
        if name:
            return _safe_text(name)
    return None


def _type_name(value):
    try:
        return type(value).__name__
    except Exception:
        return "unknown"


def _summarize_one(value):
    unwrapped = _try_unwrap(value)
    summary = {
        "type": _type_name(unwrapped),
        "is_none": unwrapped is None,
    }

    element_id = _element_id(unwrapped)
    if element_id is not None:
        summary["element_id"] = element_id

    name = _element_name(unwrapped)
    if name:
        summary["name"] = name

    if unwrapped is None or _is_string(unwrapped) or isinstance(unwrapped, (int, float, bool)):
        summary["value"] = _safe_text(unwrapped)

    return summary


def _summarize_input(value, sample_limit=5):
    items = _to_list(value)
    sample_type = _type_name(_try_unwrap(items[0])) if items else None

    summary = {
        "is_none": value is None,
        "provided": value is not None,
        "type": _type_name(value),
        "is_list_like": _is_sequence(value),
        "count": len(items),
        "sample_type": sample_type,
        "sample_limit": sample_limit,
        "sample": [],
    }

    for item in items[:sample_limit]:
        summary["sample"].append(_summarize_one(item))

    summary["truncated_count"] = max(0, len(items) - sample_limit)
    return summary


def _settings_warnings(settings):
    warnings = []
    if settings is None:
        warnings.append("settings input is empty; v0 diagnostics are using only fixed legal constants.")
        return warnings
    if not isinstance(settings, dict):
        warnings.append("settings input is not a dictionary; it is summarized but not interpreted in v0.")
    return warnings


def _build_success():
    raw_inputs, input_source = _read_inputs()
    warnings = []

    for key in INPUT_KEYS:
        if raw_inputs.get(key) is None:
            warnings.append("{0} input is empty.".format(key))

    warnings.extend(_settings_warnings(raw_inputs.get("settings")))

    return {
        "success": True,
        "tool": TOOL_NAME,
        "stage": STAGE_NAME,
        "message": "Dynamo_Shadow v0 input diagnostics only; shadow calculation is not implemented yet.",
        "legal_constants": LEGAL_CONSTANTS,
        "inputs": {
            "source": input_source,
            "building_elements": _summarize_input(raw_inputs.get("building_elements")),
            "site_boundary": _summarize_input(raw_inputs.get("site_boundary")),
            "level": _summarize_input(raw_inputs.get("level")),
            "settings": _summarize_input(raw_inputs.get("settings")),
        },
        "planned_pipeline": PLANNED_PIPELINE,
        "warnings": warnings,
    }


def _build_failure(error_text):
    return {
        "success": False,
        "tool": TOOL_NAME,
        "stage": STAGE_NAME,
        "message": "script.py failed while building v0 input diagnostics.",
        "legal_constants": LEGAL_CONSTANTS,
        "inputs": {},
        "planned_pipeline": PLANNED_PIPELINE,
        "warnings": [],
        "error": _safe_text(error_text),
    }


try:
    OUT = _build_success()
except Exception:
    OUT = _build_failure(traceback.format_exc())
