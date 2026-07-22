# Dynamo input summaries and source diagnostics.
from shadow_revit_api import BuiltInCategory
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
        unwrapped, unwrap_diag = _try_unwrap_with_diagnostics(item)
        category_name = _category_name(unwrapped)
        category_match = _diagnose_shadow_category(unwrapped, category_name)
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
            "native_type": unwrap_diag.get("native_type"),
            "unwrap_strategy": unwrap_diag.get("unwrap_strategy"),
            "category_name": category_name,
            "category_id": category_match.get("category_id"),
            "category_match_method": category_match.get("category_match_method"),
            "matched_revit_category": category_match.get("matched_revit_category"),
            "official_revit_api_category": category_match.get("official_revit_api_category"),
            "is_mass_related_category": category_match.get("is_mass_related_category"),
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

def _diagnose_curve_access(element):
    result = {
        "attempted": False,
        "available": False,
        "curve_count": None,
        "endpoint_count": None,
        "can_read_location_curve": False,
        "can_read_geometry_curve": False,
        "endpoints": [],
        "error": None,
    }
    if element is None:
        result["error"] = "element is None"
        return result

    errors = []
    curves = []
    result["attempted"] = True
    try:
        location = _safe_attr(element, "Location")
        curve = _safe_attr(location, "Curve") if location is not None else None
        if curve is not None:
            result["can_read_location_curve"] = True
            curves.append(curve)
    except Exception as exc:
        errors.append(_safe_text(exc))

    geometry_method = getattr(element, "get_Geometry", None)
    if callable(geometry_method):
        try:
            geometry = geometry_method(None)
            if geometry is not None:
                for item in geometry:
                    item_type = _type_name(item).lower()
                    if "curve" in item_type or "line" in item_type or "arc" in item_type:
                        result["can_read_geometry_curve"] = True
                        curves.append(item)
        except Exception:
            errors.append(traceback.format_exc())

    endpoints = []
    for curve in curves:
        pair = _get_curve_endpoints(curve)
        if pair:
            endpoints.extend(pair)
    result["curve_count"] = len(curves)
    result["endpoint_count"] = len(endpoints)
    result["endpoints"] = endpoints
    result["available"] = len(curves) > 0
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
            "closure_tolerance_m": 0.01,
            "reason": "No accepted site_boundary curves are available; boundary-dependent steps will be skipped.",
            "warnings": warnings,
        }
    if len(endpoints) < 2:
        return {
            "attempted": True,
            "candidate_curve_count": candidate_curve_count,
            "closed_loop_check_available": False,
            "appears_closed": None,
            "closure_tolerance_m": 0.01,
            "reason": "Curve endpoints could not be read safely; no curve sorting or polygonization is attempted in this PR.",
            "warnings": warnings,
        }
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
        "closure_tolerance_m": tol,
        "reason": "Simplified endpoint pairing diagnostic only; no sorting, self-intersection check, polygonization, offset, or 5m/10m measurement line generation is performed.",
        "warnings": warnings,
    }

def _diagnose_site_boundary(site_boundary):
    items = _to_list(site_boundary)
    diagnostics = {
        "provided": len(items) > 0,
        "required_for_equal_time_shadow": False,
        "required_for_boundary_dependent_steps": True,
        "count": len(items),
        "accepted_count": 0,
        "rejected_count": 0,
        "boundary_role": "optional_user_defined_site_boundary",
        "selection_mode": "multiple_supported",
        "primary_input_policy": "revit_property_line_or_site_property",
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
            "closure_tolerance_m": 0.01,
            "reason": "site_boundary is optional and not provided; boundary-dependent steps will be skipped",
            "warnings": [],
        }
        diagnostics["info"].extend([
            "site_boundary is optional.",
            "equal-time shadow output can continue without site_boundary.",
            "Boundary-dependent steps such as 5m/10m measurement line generation and boundary-based regulation checks will be skipped.",
        ])
        return diagnostics

    if len(items) == 1:
        diagnostics["warnings"].append("site_boundary received a single selected item; multiple Property Line segments or Model Lines may be required for a closed loop.")

    for index, item in enumerate(items):
        unwrapped, unwrap_diag = _try_unwrap_with_diagnostics(item)
        category_name = _category_name(unwrapped)
        category_match = _diagnose_site_category(unwrapped, category_name)
        official = category_match.get("official_revit_api_category")
        type_name = _type_name(unwrapped)
        name = _element_name(unwrapped)
        combined = " ".join([_safe_text(x) or "" for x in (type_name, name, category_name, official)])
        curve_access = _diagnose_curve_access(unwrapped)
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
        if not curve_access.get("available"):
            item_warnings.append("Curve/endpoint access is unavailable: {0}".format(curve_access.get("error")))
        if is_line_fallback and not curve_access.get("endpoint_count"):
            item_warnings.append("Model Lines fallback candidate cannot be confirmed as a closed loop because endpoints are unavailable.")
        if not (is_property or is_segment or is_line_fallback):
            item_warnings.append("site_boundary item is not recognized as Property Line / Site Property primary input or Model Lines fallback.")
        if is_related:
            item_diagnostics.append("site-related category is reported for diagnostics only unless usable boundary curves can be read safely.")

        accepted = (unwrapped is not None) and (not is_detail) and (not is_cad) and (not is_topo) and (is_property or is_segment or (is_line_fallback and curve_access.get("available")))
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

    diagnostics["loop_diagnostics"] = _diagnose_site_boundary_loop(diagnostics["items"])
    diagnostics["warnings"].extend(diagnostics["loop_diagnostics"].get("warnings", []))
    diagnostics["boundary_dependent_steps_available"] = diagnostics["accepted_count"] > 0 and diagnostics["loop_diagnostics"].get("closed_loop_check_available") is True
    diagnostics["boundary_dependent_steps_skipped"] = not diagnostics["boundary_dependent_steps_available"]
    if diagnostics["boundary_dependent_steps_skipped"]:
        diagnostics["info"].append("site_boundary was provided, but boundary-dependent steps remain gated until a usable Property Line/Site Property or closed Model Lines loop can be read.")
    return diagnostics
