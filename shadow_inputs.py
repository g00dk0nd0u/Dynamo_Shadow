# Dynamo input summaries and source diagnostics.
from shadow_revit_api import BuiltInCategory, CurveElement, ModelCurve, Options
from shadow_policies import (INPUT_KEYS, SUPPORTED_CATEGORY_NAMES, ACCEPTED_BUILT_IN_CATEGORY_NAMES, SITE_BOUNDARY_FALLBACK_LINE_CATEGORY_NAMES, SITE_BOUNDARY_RELATED_CATEGORY_NAMES, SITE_BOUNDARY_TOPO_CATEGORY_NAMES)
from shadow_utils import *


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

def _localized_category_name_match(category_name):
    if not category_name:
        return False
    normalized = category_name.strip().lower()
    return normalized in SUPPORTED_CATEGORY_NAMES

def _diagnose_shadow_category(element, category_name):
    category = _category(element)
    category_id = _category_id_from_category(category)
    official_category = _built_in_category_name_for_id(category_id)
    is_mass_related = bool(official_category and official_category.startswith("OST_Mass"))

    if official_category is not None:
        return {
            "category_id": category_id,
            "category_match_method": "built_in_category",
            "matched_revit_category": official_category,
            "official_revit_api_category": official_category,
            "is_mass_related_category": is_mass_related,
            "is_supported_category": official_category in ACCEPTED_BUILT_IN_CATEGORY_NAMES,
        }

    if _localized_category_name_match(category_name):
        return {
            "category_id": category_id,
            "category_match_method": "localized_category_name",
            "matched_revit_category": category_name,
            "official_revit_api_category": None,
            "is_mass_related_category": bool(category_name and category_name.strip().lower() in ("mass", "masses", "マス")),
            "is_supported_category": True,
        }

    return {
        "category_id": category_id,
        "category_match_method": "none",
        "matched_revit_category": category_name,
        "official_revit_api_category": None,
        "is_mass_related_category": False,
        "is_supported_category": False,
    }

def _diagnose_geometry_access(element):
    result = {
        "attempted": False,
        "available": False,
        "geometry_readable": False,
        "geometry_access_method": None,
        "geometry_fallback_used": False,
        "geometry_instance_count": 0,
        "solid_count": 0,
        "positive_solid_count": 0,
        "face_count": 0,
        "edge_count": 0,
        "mesh_count": 0,
        "error_type": None,
        "error": None,
    }
    if element is None:
        result["error"] = "element is None"
        return result
    collected = _collect_geometry_objects(element)
    access = collected.get("access") or {}
    result["attempted"] = bool(access.get("attempted"))
    result["geometry_readable"] = bool(access.get("geometry_readable"))
    result["available"] = result["geometry_readable"]
    result["geometry_access_method"] = access.get("geometry_access_method")
    result["geometry_fallback_used"] = bool(access.get("geometry_fallback_used"))
    result["error_type"] = access.get("error_type")
    result["error"] = access.get("error")
    for obj in collected.get("objects") or []:
        value = obj.get("object")
        if _is_geometry_instance_like(value):
            result["geometry_instance_count"] += 1
        elif _is_solid_like(value):
            result["solid_count"] += 1
            volume = _safe_float_attr(value, "Volume")
            if volume is not None and volume > 0:
                result["positive_solid_count"] += 1
        elif _is_face_like(value):
            result["face_count"] += 1
        elif _is_edge_like(value) or _is_curve_like(value):
            result["edge_count"] += 1
        elif _is_mesh_like(value):
            result["mesh_count"] += 1
    if result["error"] is None and collected.get("warnings"):
        result["error"] = "; ".join(collected.get("warnings")[:3])
    return result

def _summarize_one(value):
    primitive = value is None or _is_string(value) or isinstance(value, (int, float, bool, dict))
    unwrapped = value if primitive else _try_unwrap(value)
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
    first = items[0] if items else None
    primitive = first is None or _is_string(first) or isinstance(first, (int, float, bool, dict))
    sample_type = _type_name(first if primitive else _try_unwrap(first)) if items else None

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
        unwrapped, unwrap_diag = _try_unwrap_with_diagnostics(item)
        element_id, element_id_diag = _read_element_id(unwrapped)
        category, category_diag = _read_element_category(unwrapped)
        category_id_object, category_id_prop_diag = _safe_property(category, "Id")
        category_id, category_id_diag = _read_id_object(category_id_object, "category_id")
        category_name_value, category_name_diag = _safe_property(category, "Name")
        category_name = _safe_text(category_name_value) if category_name_value else None
        category_match = _diagnose_shadow_category(unwrapped, category_name)
        category_match["category_id"] = category_id
        shadow_role = _lookup_parameter_text(unwrapped, "ShadowRole") if unwrapped is not None else None
        is_supported_category = category_match.get("is_supported_category", False)
        geometry_access = _diagnose_geometry_access(unwrapped)
        item_warnings = []

        if unwrapped is None:
            item_warnings.append("building_elements contains None at index {0}.".format(index))
        if not category_name and category_match.get("official_revit_api_category") is None:
            item_warnings.append("category could not be read from BuiltInCategory or localized display name; accepted is False until it can be identified as OST_Mass or OST_GenericModel.")
        elif category_match.get("is_mass_related_category") and not is_supported_category:
            item_warnings.append("Mass-related BuiltInCategory was detected, but only OST_Mass and OST_GenericModel are accepted as initial shadow caster proxy categories in v1 diagnostics.")
        elif not is_supported_category:
            item_warnings.append("category '{0}' is not accepted for shadow caster proxies; use user-defined Mass or Generic Model elements. ShadowRole is advisory and does not override category support.".format(category_match.get("matched_revit_category")))
        if shadow_role is None:
            item_warnings.append("ShadowRole parameter is missing or empty; this is a warning only for v1 diagnostics.")
        if not geometry_access.get("available"):
            item_warnings.append("geometry_readable is false: {0}".format(geometry_access.get("error") or "no geometry returned"))

        accepted = (unwrapped is not None) and is_supported_category
        if accepted:
            diagnostics["accepted_count"] += 1
        else:
            diagnostics["rejected_count"] += 1

        diagnostics["items"].append({
            "index": index,
            "is_none": unwrapped is None,
            "type": _type_name(unwrapped),
            "wrapper_type": unwrap_diag.get("wrapper_type"),
            "wrapper_type_module": unwrap_diag.get("wrapper_type_module"),
            "candidate_type": unwrap_diag.get("candidate_type"),
            "candidate_type_module": unwrap_diag.get("candidate_type_module"),
            "native_type": unwrap_diag.get("native_type"),
            "native_type_module": unwrap_diag.get("native_type_module"),
            "unwrap_strategy": unwrap_diag.get("unwrap_strategy"),
            "unwrapped": unwrap_diag.get("unwrapped"),
            "unwrap_attempts": unwrap_diag.get("unwrap_attempts"),
            "unwrap_failure_reasons": unwrap_diag.get("unwrap_failure_reasons"),
            "native_candidate_usable": unwrap_diag.get("native_candidate_usable"),
            "native_property_access_ready": element_id is not None or category is not None,
            "is_valid_object_status": ((unwrap_diag.get("candidate_probes") or [{}])[-1]).get("is_valid_object_status", "unknown"),
            "candidate_probes": unwrap_diag.get("candidate_probes"),
            "property_access_diagnostics": {"Id": element_id_diag.get("property_diagnostics"), "Category": category_diag.get("property_diagnostics", {}).get("Category"), "IsValidObject": ((unwrap_diag.get("candidate_probes") or [{}])[-1]).get("property_access_diagnostics", {}).get("IsValidObject"), "Symbol": category_diag.get("property_diagnostics", {}).get("Symbol")},
            "document_reacquire_attempted": unwrap_diag.get("document_reacquire_attempted"),
            "document_reacquire_attempts": unwrap_diag.get("document_reacquire_attempts"),
            "document_reacquire_succeeded": unwrap_diag.get("document_reacquire_succeeded"),
            "document_reacquire_strategy": unwrap_diag.get("document_reacquire_strategy"),
            "category_name": category_name,
            "category_id": category_match.get("category_id"),
            "category_match_method": category_match.get("category_match_method"),
            "matched_revit_category": category_match.get("matched_revit_category"),
            "official_revit_api_category": category_match.get("official_revit_api_category"),
            "is_mass_related_category": category_match.get("is_mass_related_category"),
            "element_id": element_id,
            "element_id_object_type": element_id_diag.get("element_id_object_type"),
            "element_id_property_read_method": element_id_diag.get("element_id_property_read_method"),
            "element_id_value_read_method": element_id_diag.get("element_id_value_read_method"),
            "element_id_access_error_type": element_id_diag.get("element_id_error_type"),
            "element_id_access_error": element_id_diag.get("element_id_error"),
            "element_id_read_method": element_id_diag.get("element_id_value_read_method"),
            "category_available": category_diag.get("category_available"),
            "category_source": category_diag.get("category_source"),
            "category_object_type": category_diag.get("category_object_type"),
            "category_property_read_method": category_diag.get("category_property_read_method"),
            "category_id_read_method": category_id_diag.get("category_id_value_read_method"),
            "category_name_read_method": category_name_diag.get("read_method"),
            "category_access_error_type": category_diag.get("category_error_type"),
            "category_access_error": category_diag.get("category_error"),
            "category_read_method": category_match.get("category_match_method"),
            "category_id_raw_type": _type_name(category_id_object) if category is not None else None,
            "geometry_probe_attempted": geometry_access.get("attempted"),
            "name": _element_name(unwrapped),
            "family_name": _family_name(unwrapped),
            "type_name": _type_label(unwrapped),
            "shadow_role": shadow_role,
            "is_supported_category": is_supported_category,
            "accepted": accepted,
            "geometry_access": geometry_access,
            "diagnostics": {
                "source_geometry": "user_defined_mass_or_generic_model_proxy",
                "category_detection_priority": "built_in_category_then_localized_category_name",
                "shadow_role_overrides_category": False,
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

def _safe_built_in_category_names(names):
    available = []
    missing = []
    if BuiltInCategory is None:
        return available, list(names)
    for name in names:
        try:
            if hasattr(BuiltInCategory, name):
                getattr(BuiltInCategory, name)
                available.append(name)
            else:
                missing.append(name)
        except Exception:
            missing.append(name)
    return available, missing

def _looks_like(text, needles):
    text = (text or "").lower()
    return any(needle.lower() in text for needle in needles)

def _is_valid_owner_view_id(element):
    owner_view_id = _safe_attr(element, "OwnerViewId")
    value = _revit_id_to_int(owner_view_id)
    return value is not None and value != -1

def _get_curve_endpoints(curve):
    points = []
    for index in (0, 1):
        point, error = _safe_call(curve, "GetEndPoint", index)
        if error or point is None:
            return None
        coords = []
        for attr in ("X", "Y", "Z"):
            raw = _safe_attr(point, attr)
            try:
                coords.append(float(raw))
            except Exception:
                return None
        points.append(tuple(coords))
    return tuple(points)

def _is_curve_element_input(element):
    if _is_instance_of_optional(element, CurveElement) or _is_instance_of_optional(element, ModelCurve):
        return True
    type_name = (_type_name(element) or "").lower().replace(" ", "")
    return any(name in type_name for name in ("curveelement", "modelcurve", "modelline"))

def _diagnose_geometry_curve_fallback(element):
    curves = []
    error = None
    _runtime_checkpoint("SITE_CURVE_GEOMETRY_FALLBACK_BEFORE")
    try:
        if Options is None:
            return curves, "Autodesk.Revit.DB.Options is unavailable; geometry diagnostic fallback was not run."
        geometry_method = getattr(element, "get_Geometry", None)
        if not callable(geometry_method):
            return curves, "get_Geometry is unavailable; geometry diagnostic fallback was not run."
        options = Options()
        try:
            options.ComputeReferences = False
            options.IncludeNonVisibleObjects = True
        except BaseException:
            pass
        geometry = geometry_method(options)
        for item in _safe_iter(geometry):
            if _is_curve_like(item):
                curves.append(item)
    except BaseException as exc:
        error = "{0}: {1}".format(type(exc).__name__, _safe_text(exc))
    finally:
        _runtime_checkpoint("SITE_CURVE_GEOMETRY_FALLBACK_AFTER", "failed" if error else ("ok" if curves else "none"))
    return curves, error

def _diagnose_curve_access(element):
    result = {
        "attempted": False,
        "available": False,
        "curve_count": None,
        "endpoint_count": None,
        "can_read_location_curve": False,
        "can_read_geometry_curve": False,
        "endpoints": [],
        "curve_access_method": "unavailable",
        "geometry_fallback_attempted": False,
        "geometry_fallback_skipped_reason": None,
        "location_curve_available": False,
        "endpoint_read_succeeded": False,
        "error": None,
    }
    if element is None:
        result["error"] = "element is None"
        return result

    errors = []
    result["attempted"] = True
    curve = None
    _runtime_checkpoint("SITE_CURVE_LOCATION_BEFORE")
    try:
        location = _safe_attr(element, "Location")
        curve = _safe_attr(location, "Curve") if location is not None else None
    except BaseException as exc:
        errors.append(_safe_text(exc))
    finally:
        _runtime_checkpoint("SITE_CURVE_LOCATION_AFTER", "ok" if curve is not None else "none")

    if curve is not None:
        result["location_curve_available"] = True
        result["can_read_location_curve"] = True
        _runtime_checkpoint("SITE_CURVE_ENDPOINTS_BEFORE")
        try:
            pair = _get_curve_endpoints(curve)
        except BaseException as exc:
            pair = None
            errors.append(_safe_text(exc))
        finally:
            _runtime_checkpoint("SITE_CURVE_ENDPOINTS_AFTER", "ok" if pair else "failed")
        if pair:
            result.update({
                "available": True,
                "curve_count": 1,
                "endpoint_count": 2,
                "endpoints": list(pair),
                "curve_access_method": "location_curve",
                "geometry_fallback_skipped_reason": "usable_location_curve",
                "endpoint_read_succeeded": True,
            })
            return result

    if _is_curve_element_input(element):
        result["geometry_fallback_skipped_reason"] = "curve_element_input"
        curves = []
    else:
        result["geometry_fallback_attempted"] = True
        curves, fallback_error = _diagnose_geometry_curve_fallback(element)
        if fallback_error:
            errors.append(fallback_error)

    endpoints = []
    for fallback_curve in curves:
        _runtime_checkpoint("SITE_CURVE_ENDPOINTS_BEFORE")
        pair = None
        try:
            pair = _get_curve_endpoints(fallback_curve)
        except BaseException as exc:
            errors.append(_safe_text(exc))
        finally:
            _runtime_checkpoint("SITE_CURVE_ENDPOINTS_AFTER", "ok" if pair else "failed")
        if pair:
            endpoints.extend(pair)
    result["curve_count"] = len(curves)
    result["endpoint_count"] = len(endpoints)
    result["endpoints"] = endpoints
    result["available"] = len(curves) > 0
    result["endpoint_read_succeeded"] = len(endpoints) > 0
    if result["available"]:
        result["curve_access_method"] = "geometry_fallback"
        result["can_read_geometry_curve"] = True
    if errors:
        result["error"] = "; ".join([e for e in errors if e])
    elif not result["available"]:
        result["error"] = "Curve access is not available; no offset, 5m/10m line, or shadow calculation is attempted."
    return result

def _diagnose_site_category(element, category_name):
    category = _category(element)
    category_id = _category_id_from_category(category)
    official_category = _built_in_category_name_for_id(category_id)
    if official_category is not None:
        return {
            "category_id": category_id,
            "category_match_method": "built_in_category",
            "matched_revit_category": official_category,
            "official_revit_api_category": official_category,
        }
    return {
        "category_id": category_id,
        "category_match_method": "localized_category_name_or_type_fallback" if category_name else "none",
        "matched_revit_category": category_name,
        "official_revit_api_category": None,
    }

def _diagnose_site_boundary_loop(items):
    endpoints = []
    warnings = []
    for item in items:
        if not item.get("accepted"):
            continue
        curve_access = item.get("curve_access") or {}
        endpoints.extend(curve_access.get("endpoints") or [])
        if item.get("is_model_line_fallback_candidate") and not curve_access.get("endpoint_count"):
            warnings.append("Model Lines fallback was accepted but endpoints could not be read; closed-loop confirmation is unavailable.")
    candidate_curve_count = sum((item.get("curve_access") or {}).get("curve_count") or 0 for item in items if item.get("accepted"))
    if candidate_curve_count == 0:
        return {
            "attempted": False,
            "candidate_curve_count": 0,
            "closed_loop_check_available": False,
            "appears_closed": None,
            "closure_tolerance_internal": 0.01,
            "endpoint_units": "revit_internal",
            "reason": "No accepted site_boundary curves are available; boundary-dependent steps will be skipped.",
            "warnings": warnings,
        }
    if len(endpoints) < 2:
        return {
            "attempted": True,
            "candidate_curve_count": candidate_curve_count,
            "closed_loop_check_available": False,
            "appears_closed": None,
            "closure_tolerance_internal": 0.01,
            "endpoint_units": "revit_internal",
            "reason": "Curve endpoints could not be read safely; no curve sorting or polygonization is attempted in this PR.",
            "warnings": warnings,
        }
    # Location.Curve endpoints are Revit internal units, so the bucket
    # tolerance must use those same units rather than metres.
    tol = 0.01
    buckets = {}
    for pt in endpoints:
        key = tuple(round(coord / tol) for coord in pt)
        buckets[key] = buckets.get(key, 0) + 1
    odd = [key for key, count in buckets.items() if count % 2]
    return {
        "attempted": True,
        "candidate_curve_count": candidate_curve_count,
        "closed_loop_check_available": True,
        "appears_closed": len(odd) == 0,
        "closure_tolerance_internal": tol,
        "endpoint_units": "revit_internal",
        "reason": "Simplified endpoint pairing diagnostic only; no sorting, self-intersection check, polygonization, offset, or 5m/10m measurement line generation is performed.",
        "warnings": warnings,
    }

def _diagnose_site_boundary_unsafe(site_boundary):
    items = _to_list(site_boundary)
    diagnostics = {
        "provided": len(items) > 0,
        "required_for_equal_time_shadow": False,
        "required_for_boundary_dependent_steps": True,
        "count": len(items),
        "accepted_count": 0,
        "rejected_count": 0,
        "boundary_role": "optional_user_defined_site_boundary",
        "selection_mode": "single_revit_area",
        "primary_input_policy": "single_revit_area",
        "formal_geometry_required": True,
        "selected_input_type": None,
        "fallback_input_policy": "model_lines_closed_loop",
        "boundary_dependent_steps_available": False,
        "boundary_dependent_steps_skipped": True,
        "equal_time_shadow_available_without_site_boundary": True,
        "items": [],
        "loop_diagnostics": {},
        "warnings": [],
        "info": [],
    }
    if not items:
        diagnostics["loop_diagnostics"] = {
            "attempted": False,
            "candidate_curve_count": 0,
            "closed_loop_check_available": False,
            "appears_closed": None,
            "closure_tolerance_internal": 0.01,
            "endpoint_units": "revit_internal",
            "reason": "site_boundary is optional and not provided; boundary-dependent steps will be skipped",
            "warnings": [],
        }
        diagnostics["info"].extend([
            "site_boundary is optional.",
            "equal-time shadow output can continue without site_boundary.",
            "Boundary-dependent steps such as 5m/10m measurement line generation and boundary-based regulation checks will be skipped.",
        ])
        return diagnostics

    for index, item in enumerate(items):
        unwrapped, unwrap_diag = _try_unwrap_with_diagnostics(item)
        category_name = _category_name(unwrapped)
        category_match = _diagnose_site_category(unwrapped, category_name)
        official = category_match.get("official_revit_api_category")
        type_name = _type_name(unwrapped)
        name = _element_name(unwrapped)
        combined = " ".join([_safe_text(x) or "" for x in (type_name, name, category_name, official)])
        is_area = official == "OST_Areas" or type_name in ("Area", "FakeArea") or bool(_safe_attr(unwrapped, "_is_revit_area_test_double"))
        curve_access = {"available": False, "attempted": False, "reason": "Formal Area boundary validation is performed by site_boundary_area_extraction."} if is_area else _diagnose_curve_access(unwrapped)
        is_property = official == "OST_SiteProperty"
        is_segment = official == "OST_SitePropertyLineSegment"
        is_site_point = official == "OST_SitePointBoundary"
        is_line_fallback = official in SITE_BOUNDARY_FALLBACK_LINE_CATEGORY_NAMES or _looks_like(combined, ["modelcurve", "modelline", "model line"])
        is_detail = bool(_safe_attr(unwrapped, "ViewSpecific")) or _is_valid_owner_view_id(unwrapped) or _looks_like(combined, ["detailcurve", "detailline", "detail line"])
        is_cad = _looks_like(combined, ["importinstance", "cadlink", "dwg", "dxf", "import"])
        is_topo = official in SITE_BOUNDARY_TOPO_CATEGORY_NAMES or _looks_like(combined, ["toposolid", "sitesurface", "topography", "toposurface"])
        is_related = official in SITE_BOUNDARY_RELATED_CATEGORY_NAMES
        item_warnings = []
        item_diagnostics = []
        if unwrapped is None:
            item_warnings.append("site_boundary contains None at index {0}; this item is ignored.".format(index))
        if is_site_point:
            item_warnings.append("OST_SitePointBoundary is related to Property Lines but a point alone is not a closed boundary loop and will not proceed to loop extraction.")
        if is_detail:
            item_warnings.append("Detail Line-like element is view-specific and is not accepted as a primary site_boundary input.")
        if is_cad:
            item_warnings.append("CAD import/link-like element is diagnostic only; CAD lines are not automatically adopted as site_boundary.")
        if is_topo:
            item_warnings.append("Toposolid/SiteSurface/Topography-like element is diagnostic only; terrain edges are not automatically adopted as site_boundary.")
        if (not is_area) and not curve_access.get("available"):
            item_warnings.append("Curve/endpoint access is unavailable: {0}".format(curve_access.get("error")))
        if is_line_fallback and not curve_access.get("endpoint_count"):
            item_warnings.append("Model Lines fallback candidate cannot be confirmed as a closed loop because endpoints are unavailable.")
        if not (is_area or is_property or is_segment or is_line_fallback):
            item_warnings.append("site_boundary item is not recognized as the formal single Revit Area input; legacy Property Line / Model Line candidates are diagnostic only.")
        if is_related:
            item_diagnostics.append("site-related category is reported for diagnostics only unless usable boundary curves can be read safely.")

        accepted = (unwrapped is not None) and (not is_detail) and (not is_cad) and (not is_topo) and is_area
        if accepted:
            diagnostics["accepted_count"] += 1
        else:
            diagnostics["rejected_count"] += 1
        entry = {
            "index": index,
            "is_none": unwrapped is None,
            "type": type_name,
            "category_name": category_name,
            "category_id": category_match.get("category_id"),
            "category_match_method": category_match.get("category_match_method"),
            "matched_revit_category": category_match.get("matched_revit_category"),
            "official_revit_api_category": official,
            "element_id": _element_id(unwrapped),
            "name": name,
            "selected_input_type": "Area" if is_area else type_name,
            "is_area_candidate": is_area,
            "is_property_line_candidate": is_property,
            "is_property_line_segment_candidate": is_segment,
            "is_site_point_boundary_related": is_site_point,
            "is_model_line_fallback_candidate": is_line_fallback,
            "is_detail_line_like": is_detail,
            "is_cad_import_like": is_cad,
            "is_toposolid_or_site_surface_like": is_topo,
            "accepted": accepted,
            "curve_access": curve_access,
            "diagnostics": item_diagnostics,
            "warnings": item_warnings,
        }
        diagnostics["items"].append(entry)
        diagnostics["warnings"].extend(item_warnings)

    diagnostics["loop_diagnostics"] = {"attempted": False, "reason": "Formal boundary validation is performed by site_boundary_area_extraction and site_boundary_geometry."}
    diagnostics["boundary_dependent_steps_available"] = False
    diagnostics["boundary_dependent_steps_skipped"] = True
    diagnostics["info"].append("site_boundary diagnostics only identify the selected Area input; formal boundary readiness is reported by site_boundary_area_extraction and site_boundary_geometry.")
    return diagnostics


def _diagnose_site_boundary(site_boundary):
    """Diagnose optional boundary items independently so one bad item cannot abort peers."""
    items = _to_list(site_boundary)
    if not items:
        return _diagnose_site_boundary_unsafe(site_boundary)
    combined = _diagnose_site_boundary_unsafe(None)
    combined["provided"] = True
    combined["count"] = len(items)
    combined["items"] = []
    combined["warnings"] = []
    combined["info"] = []
    for index, item in enumerate(items):
        try:
            result = _diagnose_site_boundary_unsafe([item])
            entry = (result.get("items") or [])[0]
            entry["index"] = index
            combined["items"].append(entry)
            combined["accepted_count"] += int(bool(entry.get("accepted")))
            combined["rejected_count"] += int(not bool(entry.get("accepted")))
            combined["warnings"].extend(entry.get("warnings") or [])
        except BaseException as exc:
            warning = "site_boundary item {0} diagnostics failed; remaining items continue.".format(index)
            combined["items"].append({
                "index": index, "is_none": item is None, "type": _type_name(item),
                "accepted": False, "diagnostic_failed": True,
                "error_type": type(exc).__name__, "curve_access": {"available": False},
                "warnings": [warning],
            })
            combined["rejected_count"] += 1
            combined["warnings"].append(warning)
    if combined.get("accepted_count") == 1:
        combined["selected_input_type"] = "Area"
    combined["loop_diagnostics"] = {"attempted": False, "reason": "Formal boundary validation is performed by site_boundary_area_extraction and site_boundary_geometry."}
    combined["boundary_dependent_steps_available"] = False
    combined["boundary_dependent_steps_skipped"] = True
    combined["info"].append("site_boundary diagnostics only identify Area selection; readiness is reported by formal Area extraction/geometry/mask outputs.")
    return combined
