# script.py
# Dynamo_Shadow v1 input diagnostics skeleton.
#
# This script intentionally does not perform shadow, sun-position, shadow
# polygon, grid accumulation, or equal-time contour calculations yet. It only
# summarizes Dynamo inputs and validates user-defined shadow caster proxies so
# the next implementation steps can be checked safely from Dynamo/Revit.

import traceback

TOOL_NAME = "Dynamo_Shadow"
STAGE_NAME = "v1_shadow_caster_input_diagnostics"

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
    "input diagnostics",
    "shadow caster proxy validation",
    "shadow caster geometry access check",
    "site boundary curve diagnostics",
    "settings normalization",
    "footprint extraction from user-defined proxy geometry",
    "time-slice shadow projection per caster",
    "logical union of shadows per time slice",
    "shadow duration accumulation without double counting",
    "equal-time contour generation",
]

INPUT_KEYS = [
    "building_elements",
    "site_boundary",
    "level",
    "settings",
]

SUPPORTED_CATEGORY_NAMES = set([
    "mass",
    "masses",
    "generic model",
    "generic models",
])

SHADOW_CASTER_POLICY = {
    "purpose": "conceptual_design_shadow_study",
    "formal_permit_check": "external_tool_such_as_ADS",
    "source_geometry": "user_defined_mass_or_generic_model_proxy",
    "multiple_shadow_casters_supported": True,
    "temporary_unified_revit_model": False,
    "per_caster_geometry_reading": True,
    "bounding_box_for_shadow_geometry": False,
    "bounding_box_for_shadow_judgement": False,
    "existing_model_auto_extraction": False,
    "allowed_initial_categories": ["Mass", "Generic Models"],
    "future_time_slice_union_policy": "logical_union",
    "double_count_overlapping_shadows": False,
}


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


def _safe_call(value, method_name, *args):
    try:
        method = getattr(value, method_name)
    except Exception:
        return None, "{0} is not available".format(method_name)
    if not callable(method):
        return None, "{0} is not callable".format(method_name)
    try:
        return method(*args), None
    except Exception as exc:
        return None, _safe_text(exc)


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


def _category_name(value):
    category = _safe_attr(value, "Category")
    name = _safe_attr(category, "Name") if category is not None else None
    return _safe_text(name) if name else None


def _element_name(value):
    name = _safe_attr(value, "Name")
    return _safe_text(name) if name else None


def _family_name(value):
    for candidate in (value, _safe_attr(value, "Symbol")):
        family_name = _safe_attr(candidate, "FamilyName")
        if family_name:
            return _safe_text(family_name)
        family = _safe_attr(candidate, "Family")
        family_name = _safe_attr(family, "Name") if family is not None else None
        if family_name:
            return _safe_text(family_name)
    return None


def _type_label(value):
    symbol = _safe_attr(value, "Symbol")
    symbol_name = _safe_attr(symbol, "Name") if symbol is not None else None
    if symbol_name:
        return _safe_text(symbol_name)
    type_id = _safe_attr(value, "GetTypeId")
    if type_id is not None:
        return _safe_text(type_id)
    return None


def _type_name(value):
    try:
        return type(value).__name__
    except Exception:
        return "unknown"


def _lookup_parameter_text(value, parameter_name):
    parameter, error = _safe_call(value, "LookupParameter", parameter_name)
    if error or parameter is None:
        return None
    for method_name in ("AsString", "AsValueString"):
        text, method_error = _safe_call(parameter, method_name)
        if not method_error and text:
            return _safe_text(text)
    return _safe_text(parameter)


def _is_supported_shadow_category(category_name):
    if not category_name:
        return False
    normalized = category_name.strip().lower()
    return normalized in SUPPORTED_CATEGORY_NAMES


def _diagnose_geometry_access(element):
    result = {
        "attempted": False,
        "available": False,
        "solid_count": None,
        "curve_count": None,
        "mesh_count": None,
        "error": None,
    }
    if element is None:
        result["error"] = "element is None"
        return result

    geometry_method = getattr(element, "get_Geometry", None)
    if not callable(geometry_method):
        result["error"] = "get_Geometry is not available in this environment or for this element."
        return result

    result["attempted"] = True
    try:
        geometry = geometry_method(None)
        if geometry is None:
            result["error"] = "get_Geometry returned None."
            return result
        result["available"] = True
        solid_count = 0
        curve_count = 0
        mesh_count = 0
        for item in geometry:
            item_type = _type_name(item).lower()
            if "solid" in item_type:
                solid_count += 1
            elif "curve" in item_type or "line" in item_type or "arc" in item_type:
                curve_count += 1
            elif "mesh" in item_type:
                mesh_count += 1
        result["solid_count"] = solid_count
        result["curve_count"] = curve_count
        result["mesh_count"] = mesh_count
    except Exception:
        result["available"] = False
        result["error"] = traceback.format_exc()
    return result


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


def _diagnose_shadow_casters(building_elements):
    items = _to_list(building_elements)
    diagnostics = {
        "count": len(items),
        "accepted_count": 0,
        "rejected_count": 0,
        "caster_role": "user_defined_shadow_proxy",
        "selection_mode": "multiple_supported",
        "items": [],
        "warnings": [],
    }

    if not items:
        diagnostics["warnings"].append("building_elements is empty; select one or more user-defined Mass or Generic Model shadow proxy elements.")

    for index, item in enumerate(items):
        unwrapped = _try_unwrap(item)
        category_name = _category_name(unwrapped)
        shadow_role = _lookup_parameter_text(unwrapped, "ShadowRole") if unwrapped is not None else None
        is_supported_category = _is_supported_shadow_category(category_name)
        geometry_access = _diagnose_geometry_access(unwrapped)
        item_warnings = []

        if unwrapped is None:
            item_warnings.append("building_elements contains None at index {0}.".format(index))
        if not category_name:
            item_warnings.append("category_name could not be read; accepted is False until it can be identified as Mass or Generic Models.")
        elif not is_supported_category:
            item_warnings.append("category '{0}' is not accepted for shadow caster proxies; use user-defined Mass or Generic Model elements.".format(category_name))
        if shadow_role is None:
            item_warnings.append("ShadowRole parameter is missing or empty; this is a warning only for v1 diagnostics.")
        if not geometry_access.get("available"):
            item_warnings.append("geometry access is not available: {0}".format(geometry_access.get("error")))

        accepted = (unwrapped is not None) and is_supported_category
        if accepted:
            diagnostics["accepted_count"] += 1
        else:
            diagnostics["rejected_count"] += 1

        diagnostics["items"].append({
            "index": index,
            "is_none": unwrapped is None,
            "type": _type_name(unwrapped),
            "category_name": category_name,
            "element_id": _element_id(unwrapped),
            "name": _element_name(unwrapped),
            "family_name": _family_name(unwrapped),
            "type_name": _type_label(unwrapped),
            "shadow_role": shadow_role,
            "is_supported_category": is_supported_category,
            "accepted": accepted,
            "geometry_access": geometry_access,
            "diagnostics": {
                "source_geometry": "user_defined_mass_or_generic_model_proxy",
                "existing_model_auto_extraction": False,
                "bounding_box": {
                    "diagnostic_only": True,
                    "used_for_shadow_geometry": False,
                    "used_for_shadow_judgement": False,
                    "values_reported": False,
                },
                "temporary_unified_revit_model": False,
                "future_time_slice_union_policy": "logical_union",
                "double_count_overlapping_shadows": False,
            },
            "warnings": item_warnings,
        })
        diagnostics["warnings"].extend(item_warnings)

    return diagnostics


def _settings_warnings(settings):
    warnings = []
    if settings is None:
        warnings.append("settings input is empty; diagnostics continue, but average_ground_level_elevation_m and measurement_height_m should be provided before calculation work.")
        return warnings
    if not isinstance(settings, dict):
        warnings.append("settings input is not a dictionary; it is summarized but not interpreted in v1 diagnostics.")
        return warnings
    if "average_ground_level_elevation_m" not in settings:
        warnings.append("settings.average_ground_level_elevation_m is missing; do not use Level Elevation as a substitute for average ground level.")
    if "measurement_height_m" not in settings:
        warnings.append("settings.measurement_height_m is missing; measurement plane height cannot be normalized yet.")
    return warnings


def _build_success():
    raw_inputs, input_source = _read_inputs()
    warnings = []

    for key in INPUT_KEYS:
        if raw_inputs.get(key) is None:
            warnings.append("{0} input is empty.".format(key))

    shadow_casters = _diagnose_shadow_casters(raw_inputs.get("building_elements"))
    warnings.extend(shadow_casters.get("warnings", []))
    warnings.extend(_settings_warnings(raw_inputs.get("settings")))

    return {
        "success": True,
        "tool": TOOL_NAME,
        "stage": STAGE_NAME,
        "message": "Dynamo_Shadow v1 input diagnostics only; shadow calculation, sun position, shadow polygons, grid accumulation, and equal-time contours are not implemented yet.",
        "legal_constants": LEGAL_CONSTANTS,
        "inputs": {
            "source": input_source,
            "building_elements": _summarize_input(raw_inputs.get("building_elements")),
            "site_boundary": _summarize_input(raw_inputs.get("site_boundary")),
            "level": _summarize_input(raw_inputs.get("level")),
            "settings": _summarize_input(raw_inputs.get("settings")),
        },
        "shadow_casters": shadow_casters,
        "shadow_caster_policy": SHADOW_CASTER_POLICY,
        "planned_pipeline": PLANNED_PIPELINE,
        "warnings": warnings,
    }


def _build_failure(error_text):
    raw_inputs, input_source = _read_inputs()
    return {
        "success": False,
        "tool": TOOL_NAME,
        "stage": STAGE_NAME,
        "message": "script.py failed while building v1 shadow caster input diagnostics.",
        "legal_constants": LEGAL_CONSTANTS,
        "inputs": {
            "source": input_source,
            "building_elements": _summarize_input(raw_inputs.get("building_elements")),
            "site_boundary": _summarize_input(raw_inputs.get("site_boundary")),
            "level": _summarize_input(raw_inputs.get("level")),
            "settings": _summarize_input(raw_inputs.get("settings")),
        },
        "planned_pipeline": PLANNED_PIPELINE,
        "warnings": [],
        "error": error_text,
    }


try:
    OUT = _build_success()
except Exception:
    OUT = _build_failure(traceback.format_exc())
