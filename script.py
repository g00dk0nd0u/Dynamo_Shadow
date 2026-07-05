# script.py
# Dynamo_Shadow v1 input diagnostics skeleton.
#
# This script intentionally does not perform shadow, sun-position, shadow
# polygon, grid accumulation, or equal-time contour calculations yet. It only
# summarizes Dynamo inputs and validates user-defined shadow caster proxies so
# the next implementation steps can be checked safely from Dynamo/Revit.

import json
import math
import traceback

try:
    import clr
    clr.AddReference("RevitAPI")
    from Autodesk.Revit.DB import BuiltInCategory, Options, Solid, GeometryInstance, Face, PlanarFace, Edge, Curve, Mesh
except Exception:
    BuiltInCategory = Options = Solid = GeometryInstance = Face = PlanarFace = Edge = Curve = Mesh = None

TOOL_NAME = "Dynamo_Shadow"
STAGE_NAME = "v1_measurement_plane_construction_diagnostics"

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
    "shadow caster geometry extraction diagnostics",
    "solid / face / edge summary",
    "footprint candidate diagnostics",
    "optional site boundary source validation",
    "property line / site property diagnostics when provided",
    "model lines fallback closed-loop diagnostics when provided",
    "settings coercion and normalization",
    "law56_2 awareness context diagnostics",
    "measurement plane readiness check",
    "measurement plane construction diagnostics",
    "pipeline readiness diagnostics",
    "footprint extraction from user-defined shadow proxy geometry",
    "optional site boundary loop extraction",
    "legal judgement mask preparation",
    "optional 5m / 10m measurement line generation when site_boundary is available",
    "true solar time diagnostics",
    "sun vector calculation",
    "time-slice shadow projection per caster",
    "logical union of shadows per time slice",
    "shadow duration accumulation without double counting",
    "equal-time contour generation",
    "legal judgement report",
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
    "一般モデル",
    "マス",
])

ACCEPTED_BUILT_IN_CATEGORY_NAMES = set([
    "OST_GenericModel",
    "OST_Mass",
])

SITE_BOUNDARY_PRIMARY_CATEGORY_NAMES = set([
    "OST_SiteProperty",
    "OST_SitePropertyLineSegment",
])

SITE_BOUNDARY_RELATED_CATEGORY_NAMES = set([
    "OST_SitePointBoundary",
    "OST_SitePropertyTags",
    "OST_Site",
    "OST_Property",
])

SITE_BOUNDARY_FALLBACK_LINE_CATEGORY_NAMES = set([
    "OST_Lines",
    "OST_SketchLines",
    "OST_Curves",
    "OST_GenericLines",
])

SITE_BOUNDARY_TOPO_CATEGORY_NAMES = set([
    "OST_Toposolid",
    "OST_SiteSurface",
    "OST_Topography",
    "OST_TopographySurface",
])

SETTINGS_SCHEMA_VERSION = "v1"

SETTINGS_REQUIRED_FOR_EQUAL_TIME_SHADOW = [
    "average_ground_level_elevation_m",
    "measurement_height_m",
    "latitude",
    "longitude",
    "true_north_deg",
]

SETTINGS_DIAGNOSTIC_DEFAULTS = {
    "profile": "standard_8_16",
    "grid_resolution_m": 1.0,
    "analysis_margin_m": 20.0,
    "closure_tolerance_m": 0.01,
}

SETTINGS_POLICY = {
    "optional": True,
    "missing_settings_is_fatal": False,
    "units": {
        "length": "meter",
        "angle": "degree",
        "latitude_longitude": "decimal_degree",
    },
    "level_used_as_average_ground_level": False,
    "level_used_as_measurement_plane": False,
    "required_for_equal_time_shadow": SETTINGS_REQUIRED_FOR_EQUAL_TIME_SHADOW,
    "diagnostic_defaults": SETTINGS_DIAGNOSTIC_DEFAULTS,
    "no_legal_assumption_defaults": SETTINGS_REQUIRED_FOR_EQUAL_TIME_SHADOW,
    "formal_permit_check": "external_tool_such_as_ADS",
}

SITE_BOUNDARY_POLICY = {
    "optional": True,
    "required_for_equal_time_shadow": False,
    "required_for_boundary_dependent_steps": True,
    "missing_site_boundary_is_fatal": False,
    "equal_time_shadow_available_without_site_boundary": True,
    "missing_site_boundary_behavior": "skip_boundary_dependent_steps_only",
    "boundary_dependent_steps": [
        "property_line_or_site_boundary_based_offset",
        "5m_10m_measurement_line_generation",
        "boundary_based_regulation_reference_check",
    ],
    "non_boundary_dependent_steps_continue": [
        "shadow_caster_geometry_reading",
        "time_slice_shadow_projection",
        "logical_union_of_shadows_per_time_slice",
        "shadow_duration_accumulation",
        "equal_time_shadow_output",
    ],
    "primary_source": "revit_property_line_or_site_property",
    "primary_built_in_categories": [
        "BuiltInCategory.OST_SiteProperty",
        "BuiltInCategory.OST_SitePropertyLineSegment",
    ],
    "related_site_categories_diagnostic_only": [
        "BuiltInCategory.OST_SitePointBoundary",
        "BuiltInCategory.OST_Site",
        "BuiltInCategory.OST_Property",
    ],
    "fallback_source": "model_lines_closed_loop",
    "fallback_line_categories": [
        "BuiltInCategory.OST_Lines",
        "BuiltInCategory.OST_SketchLines",
        "BuiltInCategory.OST_Curves",
        "BuiltInCategory.OST_GenericLines",
    ],
    "detail_lines_allowed": False,
    "cad_import_auto_boundary": False,
    "toposolid_auto_boundary": False,
    "temporary_revit_boundary_model": False,
    "measurement_lines_generated": False,
    "formal_permit_check": "external_tool_such_as_ADS",
}

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
    "allowed_initial_categories": ["BuiltInCategory.OST_Mass", "BuiltInCategory.OST_GenericModel"],
    "category_detection_priority": "built_in_category_then_localized_category_name",
    "localized_category_names_are_fallback_only": True,
    "shadow_role_overrides_category": False,
    "future_time_slice_union_policy": "logical_union",
    "double_count_overlapping_shadows": False,
}

GEOMETRY_EXTRACTION_POLICY = {
    "purpose": "shadow_caster_geometry_extraction_diagnostics",
    "read_only": True,
    "create_revit_elements": False,
    "accepted_shadow_caster_sources": ["user_selected_mass", "user_selected_generic_model"],
    "auto_extract_existing_building_model": False,
    "use_bounding_box_for_shadow_geometry": False,
    "use_bounding_box_for_shadow_judgement": False,
    "bounding_box_allowed_for": ["diagnostic_summary", "future_analysis_extent_estimation"],
    "geometry_units": "revit_raw_internal_units",
    "official_unit_conversion": "not_implemented_in_this_pr",
    "footprint_polygon_generated": False,
    "shadow_projection_generated": False,
    "equal_time_contours_generated": False,
}


LAW56_2_AWARENESS_POLICY = {
    "purpose": "building_standard_law_article_56_2_shadow_restriction_awareness",
    "formal_permit_check": "external_tool_such_as_ADS",
    "implemented_as_legal_judgement": False,
    "legal_judgement_generated": False,
    "date_basis": "winter_solstice",
    "time_basis": "true_solar_time",
    "standard_time_window": {"start": "08:00", "end": "16:00"},
    "hokkaido_time_window": {"start": "09:00", "end": "15:00"},
    "measurement_plane_basis": "average_ground_level_plus_designated_measurement_height",
    "measurement_plane_formula": "measurement_plane_elevation_m = average_ground_level_elevation_m + measurement_height_m",
    "boundary_distance_rule_awareness": "beyond_5m_from_site_boundary",
    "exclusion_awareness": ["outside_target_area", "high_rise_residential_inducement_district", "urban_renaissance_special_district", "own_site_area"],
    "multiple_buildings_policy_awareness": "buildings_on_same_site_are_treated_as_one_building",
    "relaxation_awareness": ["road", "river", "sea", "significant_elevation_difference", "other_special_conditions_by_enforcement_order"],
    "outside_target_area_building_awareness": "building_over_10m_outside_target_area_casting_shadow_into_target_area_may_be_treated_as_in_target_area",
    "different_restriction_zones_awareness": "ordinance_and_enforcement_order_required",
    "ordinance_dependent_values": ["target_area", "applicable_building_threshold", "measurement_height_m", "allowed_shadow_duration", "selected_table_row"],
    "not_implemented_in_this_pr": ["ordinance lookup", "target area mask", "own site exclusion", "beyond 5m judgement range", "5m/10m measurement lines", "relaxation handling", "legal OK/NG judgement", "true solar time calculation", "sun vector calculation", "shadow projection", "equal-time contour generation"],
}

MEASUREMENT_PLANE_POLICY = {
    "purpose": "article_56_2_measurement_plane_construction_diagnostics",
    "create_revit_element": False,
    "internal_data_only": True,
    "plane_type": "horizontal_plane",
    "normal": "+Z",
    "coordinate_system": "legal_si_meters",
    "formula": "measurement_plane_elevation_m = average_ground_level_elevation_m + measurement_height_m",
    "average_ground_level_source": "settings.average_ground_level_elevation_m",
    "measurement_height_source": "settings.measurement_height_m",
    "revit_level_used_as_average_ground_level": False,
    "revit_level_used_as_measurement_plane": False,
    "revit_internal_unit_conversion": "not_implemented_in_this_pr",
    "geometry_relation": "diagnostic_only",
    "formal_intersection_with_revit_geometry": "not_implemented_in_this_pr",
    "site_boundary_required_for_plane_construction": False,
    "site_boundary_required_for_legal_judgement_masks": True,
    "legal_judgement_generated": False,
}

LAW56_2_FUTURE_REQUIRED_INPUTS = [
    "ordinance_profile", "target_area_status", "applicable_building_threshold",
    "measurement_height_m", "allowed_shadow_duration_profile", "site_boundary",
    "own_site_boundary", "target_area_mask", "exclusion_area_masks",
    "road_water_relaxation_profile", "elevation_difference_relaxation_profile",
    "true_solar_time_profile", "same_site_building_group",
]

GEOMETRY_READINESS_REQUIRED_FOR_FUTURE_SHADOW = [
    "at least one accepted shadow caster",
    "at least one readable solid or mesh",
    "at least one footprint candidate or bottom face candidate",
    "measurement plane readiness from settings is recommended, but geometry diagnostics can run without it",
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


def _revit_id_to_int(value):
    if value is None:
        return None
    for attr in ("IntegerValue", "Value"):
        raw = _safe_attr(value, attr)
        if raw is not None:
            try:
                return int(raw)
            except Exception:
                pass
    try:
        return int(value)
    except Exception:
        return None


def _built_in_category_value(value):
    raw = _safe_attr(value, "value__")
    if raw is not None:
        try:
            return int(raw)
        except Exception:
            pass
    try:
        return int(value)
    except Exception:
        return None


def _element_id(value):
    element_id = _safe_attr(value, "Id")
    if element_id is None:
        return None
    integer_id = _revit_id_to_int(element_id)
    if integer_id is not None:
        return integer_id
    return _safe_text(element_id)


def _category(value):
    return _safe_attr(value, "Category")


def _category_id_from_category(category):
    if category is None:
        return None
    category_id = _safe_attr(category, "Id")
    integer_id = _revit_id_to_int(category_id)
    if integer_id is not None:
        return integer_id
    return _safe_text(category_id) if category_id is not None else None


def _category_name(value):
    category = _category(value)
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


def _built_in_category_name_for_id(category_id):
    if BuiltInCategory is None or category_id is None:
        return None
    try:
        category_id_int = int(category_id)
    except Exception:
        return None
    for name in dir(BuiltInCategory):
        if not name.startswith("OST_"):
            continue
        try:
            candidate = getattr(BuiltInCategory, name)
        except Exception:
            continue
        if _built_in_category_value(candidate) == category_id_int:
            return name
    return None


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



def _type_name_lower(value):
    return (_type_name(value) or "unknown").lower()


def _is_instance_of_optional(value, cls):
    try:
        return cls is not None and isinstance(value, cls)
    except Exception:
        return False


def _is_geometry_instance_like(value):
    t = _type_name_lower(value)
    return _is_instance_of_optional(value, GeometryInstance) or "geometryinstance" in t or hasattr(value, "GetInstanceGeometry") or hasattr(value, "SymbolGeometry")


def _is_solid_like(value):
    t = _type_name_lower(value)
    return _is_instance_of_optional(value, Solid) or "solid" in t or (hasattr(value, "Faces") and hasattr(value, "Volume"))


def _is_face_like(value):
    t = _type_name_lower(value)
    return _is_instance_of_optional(value, Face) or "face" in t or hasattr(value, "Area")


def _is_planar_face_like(value):
    t = _type_name_lower(value)
    return _is_instance_of_optional(value, PlanarFace) or "planarface" in t or hasattr(value, "FaceNormal")


def _is_edge_like(value):
    t = _type_name_lower(value)
    return _is_instance_of_optional(value, Edge) or "edge" in t or hasattr(value, "AsCurve")


def _is_curve_like(value):
    t = _type_name_lower(value)
    return _is_instance_of_optional(value, Curve) or "curve" in t or "line" in t or "arc" in t or hasattr(value, "GetEndPoint")


def _is_mesh_like(value):
    t = _type_name_lower(value)
    return _is_instance_of_optional(value, Mesh) or "mesh" in t


def _safe_iter(value):
    if value is None or _is_string(value):
        return []
    try:
        return list(value)
    except Exception:
        return []


def _safe_float_attr(value, attr):
    raw = _safe_attr(value, attr)
    try:
        return float(raw)
    except Exception:
        return None


def _xyz_to_raw_dict(point):
    if point is None:
        return None
    result = {}
    for attr in ("X", "Y", "Z"):
        result[attr.lower()] = _safe_float_attr(point, attr)
    if all(result.get(k) is None for k in ("x", "y", "z")):
        return None
    result["units"] = "revit_raw_internal_units"
    return result


def _vector_to_raw_dict(vector):
    return _xyz_to_raw_dict(vector)


def _safe_get_bounding_box(element):
    if element is None:
        return {"available": False, "diagnostic_only": True, "used_for_shadow_geometry": False, "used_for_shadow_judgement": False, "reason": "element is None"}
    bbox = None
    error = None
    try:
        getter = getattr(element, "get_BoundingBox", None)
        if callable(getter):
            bbox = getter(None)
        if bbox is None:
            bbox = _safe_attr(element, "BoundingBox")
    except Exception as exc:
        error = _safe_text(exc)
    if bbox is None:
        return {"available": False, "diagnostic_only": True, "used_for_shadow_geometry": False, "used_for_shadow_judgement": False, "reason": error or "BoundingBox unavailable"}
    return {"available": True, "diagnostic_only": True, "used_for_shadow_geometry": False, "used_for_shadow_judgement": False, "min_raw": _xyz_to_raw_dict(_safe_attr(bbox, "Min")), "max_raw": _xyz_to_raw_dict(_safe_attr(bbox, "Max")), "units": "revit_raw_internal_units"}


def _safe_get_geometry(element):
    if element is None:
        return None, "element is None"
    method = getattr(element, "get_Geometry", None)
    if not callable(method):
        return None, "get_Geometry is not available in this environment or for this element."
    try:
        if Options is not None:
            try:
                return method(Options()), None
            except Exception:
                pass
        return method(None), None
    except Exception as exc:
        return None, _safe_text(exc)


def _collect_geometry_objects(element):
    objects, warnings = [], []
    geom, error = _safe_get_geometry(element)
    if error:
        warnings.append("geometry could not be read: {0}".format(error))
    def add_many(values, depth, source):
        if depth > 3:
            warnings.append("geometry nesting exceeded diagnostic recursion depth; deeper objects were skipped.")
            return
        for value in _safe_iter(values):
            objects.append({"depth": depth, "source": source, "type": _type_name(value), "object": value, "type_lower": _type_name_lower(value)})
            if _is_geometry_instance_like(value):
                symbol = _safe_attr(value, "SymbolGeometry")
                if symbol is not None:
                    add_many(symbol, depth + 1, "geometry_instance_symbol")
                inst, inst_error = _safe_call(value, "GetInstanceGeometry")
                if inst_error:
                    warnings.append("GeometryInstance.GetInstanceGeometry unavailable: {0}".format(inst_error))
                elif inst is not None:
                    add_many(inst, depth + 1, "geometry_instance_instance")
            elif not (_is_solid_like(value) or _is_face_like(value) or _is_edge_like(value) or _is_curve_like(value) or _is_mesh_like(value)):
                nested = _safe_iter(value)
                if nested:
                    add_many(nested, depth + 1, "nested_geometry")
    if geom is not None:
        add_many(geom, 0, "element_geometry")
    return {"objects": objects, "warnings": warnings}


def _summarize_solid(solid):
    warnings = []
    volume = _safe_float_attr(solid, "Volume")
    area = _safe_float_attr(solid, "SurfaceArea")
    faces = _safe_iter(_safe_attr(solid, "Faces"))
    edges = _safe_iter(_safe_attr(solid, "Edges"))
    if volume is None or volume <= 0:
        warnings.append("solid has zero/unknown volume; retained as diagnostic only.")
    bbox = None
    try:
        bbox = _safe_attr(solid, "GetBoundingBox")
    except Exception:
        bbox = None
    return {"type": _type_name(solid), "volume_raw": volume, "surface_area_raw": area, "face_count": len(faces), "edge_count": len(edges), "has_positive_volume": bool(volume is not None and volume > 0), "bounding_box_raw": {"min_raw": _xyz_to_raw_dict(_safe_attr(bbox, "Min")), "max_raw": _xyz_to_raw_dict(_safe_attr(bbox, "Max")), "diagnostic_only": True} if bbox is not None else None, "warnings": warnings}


def _summarize_face(face):
    warnings = []
    normal = _safe_attr(face, "FaceNormal") or _safe_attr(face, "Normal")
    normal_raw = _vector_to_raw_dict(normal)
    z = normal_raw.get("z") if normal_raw else None
    if z is None:
        orientation = "unknown"; role = "unknown"; warnings.append("face normal unavailable; orientation is diagnostic unknown.")
    elif z >= 0.9:
        orientation = "horizontal_up"; role = "top_face_candidate"
    elif z <= -0.9:
        orientation = "horizontal_down"; role = "bottom_face_candidate"
    elif abs(z) <= 0.1:
        orientation = "vertical"; role = "side_face_candidate"
    else:
        orientation = "sloped_or_unknown"; role = "unknown"
    loops = _safe_iter(_safe_attr(face, "EdgeLoops"))
    edge_count = 0
    for loop in loops:
        edge_count += len(_safe_iter(loop))
    return {"type": _type_name(face), "is_planar": _is_planar_face_like(face), "area_raw": _safe_float_attr(face, "Area"), "normal_raw": normal_raw, "origin_raw": _xyz_to_raw_dict(_safe_attr(face, "Origin")), "edge_loop_count": len(loops) if loops else None, "edge_count": edge_count if loops else None, "orientation_candidate": orientation, "height_role_candidate": role, "warnings": warnings}


def _summarize_edge_or_curve(value):
    warnings = []
    curve = value
    if _is_edge_like(value):
        curve, err = _safe_call(value, "AsCurve")
        if err:
            warnings.append("Edge.AsCurve unavailable: {0}".format(err))
            curve = None
    p0 = p1 = None
    if curve is not None:
        p0, e0 = _safe_call(curve, "GetEndPoint", 0)
        p1, e1 = _safe_call(curve, "GetEndPoint", 1)
        if e0 or e1:
            warnings.append("curve endpoints unavailable; edge remains diagnostic only.")
    z0 = (_xyz_to_raw_dict(p0) or {}).get("z")
    z1 = (_xyz_to_raw_dict(p1) or {}).get("z")
    length = _safe_float_attr(curve, "Length") if curve is not None else None
    return {"type": _type_name(value), "curve_type": _type_name(curve) if curve is not None else None, "length_raw": length, "endpoint0_raw": _xyz_to_raw_dict(p0), "endpoint1_raw": _xyz_to_raw_dict(p1), "is_horizontal_candidate": (z0 is not None and z1 is not None and abs(z0 - z1) < 1e-9), "z_min_raw": min([z for z in (z0, z1) if z is not None]) if z0 is not None or z1 is not None else None, "z_max_raw": max([z for z in (z0, z1) if z is not None]) if z0 is not None or z1 is not None else None, "warnings": warnings}


def _build_law56_2_awareness_context(settings_normalized, site_boundary=None):
    normalized = (settings_normalized or {}).get("normalized") or {}
    profile = normalized.get("profile")
    if profile in ("hokkaido_9_15", "hokkaido"):
        selected = LAW56_2_AWARENESS_POLICY["hokkaido_time_window"]
        source = "settings.profile"
    else:
        selected = LAW56_2_AWARENESS_POLICY["standard_time_window"]
        source = "standard_8_16_default_diagnostic"
    warnings = []
    if (site_boundary or {}).get("provided") is not True:
        warnings.append("site_boundary is not required for measurement plane construction, but is required for future beyond-5m and own-site legal judgement masks.")
    return {
        "policy": LAW56_2_AWARENESS_POLICY,
        "article": "Building Standard Law Article 56-2 shadow restriction awareness",
        "date_basis": LAW56_2_AWARENESS_POLICY["date_basis"],
        "time_basis": LAW56_2_AWARENESS_POLICY["time_basis"],
        "active_time_window_profile": profile,
        "standard_time_window": LAW56_2_AWARENESS_POLICY["standard_time_window"],
        "hokkaido_time_window": LAW56_2_AWARENESS_POLICY["hokkaido_time_window"],
        "selected_time_window": selected,
        "selected_time_window_source": source,
        "measurement_plane_basis": LAW56_2_AWARENESS_POLICY["measurement_plane_basis"],
        "boundary_distance_rule_awareness": LAW56_2_AWARENESS_POLICY["boundary_distance_rule_awareness"],
        "exclusion_awareness": LAW56_2_AWARENESS_POLICY["exclusion_awareness"],
        "multiple_buildings_policy_awareness": LAW56_2_AWARENESS_POLICY["multiple_buildings_policy_awareness"],
        "relaxation_awareness": LAW56_2_AWARENESS_POLICY["relaxation_awareness"],
        "ordinance_dependent_values": LAW56_2_AWARENESS_POLICY["ordinance_dependent_values"],
        "future_required_inputs": LAW56_2_FUTURE_REQUIRED_INPUTS,
        "implemented_now": ["awareness diagnostics", "time window profile selection for diagnostics", "measurement plane policy context"],
        "not_implemented_in_this_pr": LAW56_2_AWARENESS_POLICY["not_implemented_in_this_pr"],
        "warnings": warnings,
        "info": ["Time windows are true-solar-time awareness only; no true solar time calculation, JST clock-time conversion, sun vector calculation, or legal judgement is performed."],
    }


def _construct_measurement_plane(settings_normalized, level=None):
    normalized = (settings_normalized or {}).get("normalized") or {}
    mp_norm = (settings_normalized or {}).get("measurement_plane") or {}
    agl = normalized.get("average_ground_level_elevation_m")
    mh = normalized.get("measurement_height_m")
    available = mp_norm.get("available") is True and agl is not None and mh is not None
    elevation = agl + mh if available else None
    settings_ready = ((settings_normalized or {}).get("readiness") or {}).get("ready_for_equal_time_shadow_calculation") is True
    blockers_mp = []
    if agl is None:
        blockers_mp.append("average_ground_level_elevation_m missing")
    if mh is None:
        blockers_mp.append("measurement_height_m missing")
    if mp_norm.get("available") is not True:
        blockers_mp.append("measurement plane unavailable")
    blockers_projection = [] if available and settings_ready else list(blockers_mp)
    if not settings_ready:
        blockers_projection.append("settings not ready for equal-time shadow calculation")
    blockers_legal = ["legal judgement masks not implemented", "site_boundary / own site / target area masks required for legal judgement but not constructed in this PR"]
    warnings = []
    if not available:
        warnings.append("Measurement plane could not be constructed; this is non-fatal for input diagnostics.")
    if level is not None:
        warnings.append("Level reference is present but is not used as average ground level or measurement plane.")
    warnings.append("Geometry raw_internal_units and measurement plane meters are not formally converted in this PR.")
    return {
        "policy": MEASUREMENT_PLANE_POLICY,
        "law56_2_awareness": LAW56_2_AWARENESS_POLICY,
        "provided": (settings_normalized or {}).get("provided") is True,
        "available": available,
        "construction_attempted": True,
        "coordinate_system": "legal_si_meters",
        "units": "meter",
        "plane_type": "horizontal_plane",
        "horizontal": True,
        "normal_raw": {"x": 0.0, "y": 0.0, "z": 1.0, "units": "unitless", "note": "same abstract +Z direction; not derived from Revit geometry"},
        "normal_m": {"x": 0.0, "y": 0.0, "z": 1.0, "units": "unitless"},
        "origin_m": {"x": 0.0, "y": 0.0, "z": elevation, "units": "meter", "note": "abstract legal SI coordinate origin for diagnostics only; not a Revit point"} if available else None,
        "elevation_m": elevation,
        "plane_equation": "z = {0}".format(elevation) if available else None,
        "average_ground_level_elevation_m": agl,
        "measurement_height_m": mh,
        "formula": "measurement_plane_elevation_m = average_ground_level_elevation_m + measurement_height_m",
        "source_keys": {"average_ground_level_elevation_m": "settings.average_ground_level_elevation_m", "measurement_height_m": "settings.measurement_height_m"},
        "level_reference_present": level is not None,
        "level_used_as_average_ground_level": False,
        "level_used_as_measurement_plane": False,
        "legal_meaning": ["Article 56-2 measurement horizontal plane at designated height above average ground level.", "This is not a Revit Level.", "This is not a Revit element.", "This is not a legal judgement result."],
        "readiness": {"measurement_plane_constructed": available, "ready_for_future_footprint_projection_context": available, "ready_for_future_shadow_projection_context": available and settings_ready, "ready_for_legal_judgement_masks": False, "blockers_for_measurement_plane": blockers_mp, "blockers_for_future_shadow_projection_context": blockers_projection, "blockers_for_legal_judgement_masks": blockers_legal},
        "blockers": blockers_mp + blockers_legal,
        "warnings": warnings,
        "info": ["Measurement plane is an internal diagnostic data object only; no Revit element, DirectShape, ModelCurve, or debug plane is created."],
    }


def _measurement_plane_relation(bbox, face_summaries, measurement_plane):
    elev = (measurement_plane or {}).get("elevation_m")
    if (measurement_plane or {}).get("available") is not True:
        return {"available": False, "formal_intersection_available": False, "raw_comparison_available": False, "measurement_plane_elevation_m": None, "geometry_units": "revit_raw_internal_units", "measurement_plane_units": "meter", "unit_conversion_status": "not_implemented_in_this_pr", "raw_relation_candidate": "unknown", "reason": "measurement plane is unavailable; geometry diagnostics continue.", "used_for_legal_judgement": False, "used_for_shadow_geometry": False}
    zs = []
    for key in ("min_raw", "max_raw"):
        z = ((bbox or {}).get(key) or {}).get("z")
        if z is not None:
            zs.append(z)
    for f in face_summaries:
        z = ((f.get("origin_raw") or {}).get("z"))
        if z is not None:
            zs.append(z)
    if not zs:
        rel = "unknown"; raw_available = False; reason = "no raw z values available for diagnostic comparison; raw_internal_units and meters are not formally converted."
    elif min(zs) > elev:
        rel = "caster_above_measurement_plane_raw_candidate"; raw_available = True; reason = "raw_internal_units and meters are not formally converted; this above-plane relation is only a placeholder diagnostic."
    elif max(zs) < elev:
        rel = "caster_below_measurement_plane_raw_candidate"; raw_available = True; reason = "raw_internal_units and meters are not formally converted; this below-plane relation is only a placeholder diagnostic."
    else:
        rel = "caster_intersects_measurement_plane_raw_range_candidate"; raw_available = True; reason = "raw_internal_units and meters are not formally converted; raw range overlap is not a formal intersection test."
    return {"available": True, "formal_intersection_available": False, "raw_comparison_available": raw_available, "measurement_plane_elevation_m": elev, "geometry_units": "revit_raw_internal_units", "measurement_plane_units": "meter", "unit_conversion_status": "not_implemented_in_this_pr", "raw_relation_candidate": rel, "reason": reason, "used_for_legal_judgement": False, "used_for_shadow_geometry": False}

def _diagnose_shadow_caster_geometry(building_elements, shadow_casters, settings_normalized, measurement_plane=None):
    items_in = _to_list(building_elements)
    diag = {"policy": GEOMETRY_EXTRACTION_POLICY, "provided": bool(items_in), "count": len(items_in), "accepted_caster_count": (shadow_casters or {}).get("accepted_count", 0), "geometry_readable_caster_count": 0, "solid_count": 0, "positive_solid_count": 0, "face_count": 0, "edge_count": 0, "mesh_count": 0, "bottom_face_candidate_count": 0, "top_face_candidate_count": 0, "vertical_face_candidate_count": 0, "footprint_candidate_count": 0, "measurement_plane_relation_available": False, "measurement_plane_elevation_m": ((measurement_plane or {}).get("elevation_m")), "units": {"geometry": "revit_raw_internal_units", "official_unit_conversion": "not_implemented_in_this_pr"}, "items": [], "readiness": {}, "warnings": [], "info": ["Geometry extraction diagnostics are read-only and create no Revit elements.", "Footprint candidates are diagnostic only; no footprint polygon, shadow polygon, projection, grid accumulation, or equal-time contour is generated."]}
    caster_items = (shadow_casters or {}).get("items") or []
    for index, item in enumerate(items_in):
        unwrapped = _try_unwrap(item)
        caster_info = caster_items[index] if index < len(caster_items) else {}
        accepted = caster_info.get("accepted") is True
        item_warnings = []
        collected = _collect_geometry_objects(unwrapped) if accepted else {"objects": [], "warnings": ["shadow caster category is not accepted; geometry diagnostics skipped for this item."]}
        item_warnings.extend(collected.get("warnings", []))
        objs = collected.get("objects") or []
        solids=[]; faces=[]; edges=[]; mesh_count=0
        for obj in objs:
            val = obj.get("object")
            if _is_solid_like(val):
                ss = _summarize_solid(val); solids.append(ss)
                for f in _safe_iter(_safe_attr(val, "Faces")):
                    faces.append(_summarize_face(f))
                for e in _safe_iter(_safe_attr(val, "Edges")):
                    edges.append(_summarize_edge_or_curve(e))
            elif _is_face_like(val):
                faces.append(_summarize_face(val))
            elif _is_edge_like(val) or _is_curve_like(val):
                edges.append(_summarize_edge_or_curve(val))
            elif _is_mesh_like(val):
                mesh_count += 1
        bottom=sum(1 for f in faces if f.get("height_role_candidate")=="bottom_face_candidate")
        top=sum(1 for f in faces if f.get("height_role_candidate")=="top_face_candidate")
        vertical=sum(1 for f in faces if f.get("height_role_candidate")=="side_face_candidate")
        pos=sum(1 for solid in solids if solid.get("has_positive_volume"))
        if accepted and bottom == 0:
            item_warnings.append("No bottom face candidate was found; future footprint extraction may be blocked for this caster.")
        bbox = _safe_get_bounding_box(unwrapped)
        relation = _measurement_plane_relation(bbox, faces[:20], measurement_plane)
        if relation.get("available"):
            diag["measurement_plane_relation_available"] = True
        entry={"index": index, "element_id": _element_id(unwrapped), "name": _element_name(unwrapped), "category_name": _category_name(unwrapped), "accepted_shadow_caster": accepted, "geometry_attempted": accepted, "geometry_available": len(objs)>0, "geometry_object_count": len(objs), "solid_count": len(solids), "positive_solid_count": pos, "face_count": len(faces), "edge_count": len(edges), "mesh_count": mesh_count, "bottom_face_candidate_count": bottom, "top_face_candidate_count": top, "vertical_face_candidate_count": vertical, "footprint_candidate_count": bottom, "bounding_box_diagnostic": bbox, "measurement_plane_relation": relation, "solids": solids[:20], "faces_summary": faces[:20], "edges_summary_sample": edges[:20], "warnings": item_warnings}
        diag["items"].append(entry); diag["warnings"].extend(item_warnings)
        if len(objs)>0: diag["geometry_readable_caster_count"] += 1
        diag["solid_count"] += len(solids); diag["positive_solid_count"] += pos; diag["face_count"] += len(faces); diag["edge_count"] += len(edges); diag["mesh_count"] += mesh_count; diag["bottom_face_candidate_count"] += bottom; diag["top_face_candidate_count"] += top; diag["vertical_face_candidate_count"] += vertical; diag["footprint_candidate_count"] += bottom
    fp_ready = diag["accepted_caster_count"] > 0 and diag["positive_solid_count"] > 0 and diag["footprint_candidate_count"] > 0
    settings_ready = (((settings_normalized or {}).get("readiness") or {}).get("ready_for_equal_time_shadow_calculation") is True)
    fp_blockers=[]; proj_blockers=[]
    if diag["accepted_caster_count"] <= 0: fp_blockers.append("No accepted shadow caster proxy elements are available.")
    if diag["positive_solid_count"] <= 0: fp_blockers.append("No positive-volume solid was found in accepted shadow caster geometry.")
    if diag["footprint_candidate_count"] <= 0: fp_blockers.append("No bottom face / footprint candidate was found.")
    if not fp_ready: proj_blockers.extend(fp_blockers)
    if not settings_ready: proj_blockers.append("Settings are not ready for future equal-time shadow calculation.")
    mp_ready = ((measurement_plane or {}).get("readiness") or {}).get("measurement_plane_constructed") is True
    if not mp_ready:
        proj_blockers.append("Measurement plane is not constructed; future shadow projection context is blocked.")
    diag["readiness"]={"geometry_diagnostics_ready": True, "ready_for_future_footprint_extraction": fp_ready, "ready_for_future_shadow_projection": fp_ready and settings_ready and mp_ready, "blockers_for_future_footprint_extraction": fp_blockers, "blockers_for_future_shadow_projection": proj_blockers}
    return diag


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
        unwrapped = _try_unwrap(item)
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


def _range_warning(key, value):
    if value is None:
        return None
    ranges = {
        "latitude": (-90.0, 90.0, True, True),
        "longitude": (-180.0, 180.0, True, True),
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
    known = set(["profile", "average_ground_level_elevation_m", "measurement_height_m", "measurement_plane_elevation_m", "latitude", "longitude", "true_north_deg", "grid_resolution_m", "analysis_margin_m", "closure_tolerance_m"])
    ignored_keys = sorted([_safe_text(k) for k in settings_dict.keys() if k not in known])
    if ignored_keys:
        info.append("Unknown settings keys are ignored by v1 diagnostics: {0}".format(", ".join(ignored_keys)))

    profile, warn = _parse_text(settings_dict.get("profile"), "profile")
    if warn:
        warnings.append(warn); invalid_keys.append("profile")
    if profile is None:
        profile = SETTINGS_DIAGNOSTIC_DEFAULTS["profile"]; defaults_applied.append("profile")
    normalized["profile"] = profile

    for key in ["average_ground_level_elevation_m", "measurement_height_m", "latitude", "longitude", "true_north_deg", "grid_resolution_m", "analysis_margin_m", "closure_tolerance_m"]:
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


def _build_pipeline_readiness(shadow_casters, site_boundary, settings_normalized, shadow_caster_geometry=None, measurement_plane=None):
    blockers_equal = []
    blockers_boundary = []
    shadow_ready = (shadow_casters or {}).get("accepted_count", 0) > 0
    settings_ready = ((settings_normalized or {}).get("readiness") or {}).get("ready_for_equal_time_shadow_calculation") is True
    boundary_ready = (site_boundary or {}).get("boundary_dependent_steps_available") is True
    geom_ready = ((shadow_caster_geometry or {}).get("readiness") or {}).get("geometry_diagnostics_ready") is True
    footprint_ready = ((shadow_caster_geometry or {}).get("readiness") or {}).get("ready_for_future_footprint_extraction") is True
    mp_readiness = (measurement_plane or {}).get("readiness") or {}
    measurement_plane_ready = mp_readiness.get("measurement_plane_constructed") is True
    future_projection_context_ready = mp_readiness.get("ready_for_future_shadow_projection_context") is True
    legal_judgement_masks_ready = False
    future_projection_ready = footprint_ready and measurement_plane_ready and settings_ready
    blockers_fp = list(((shadow_caster_geometry or {}).get("readiness") or {}).get("blockers_for_future_footprint_extraction") or [])
    blockers_mp = list(mp_readiness.get("blockers_for_measurement_plane") or [])
    blockers_projection = []
    if not footprint_ready:
        blockers_projection.extend(blockers_fp)
    if not measurement_plane_ready:
        blockers_projection.extend(blockers_mp)
    if not settings_ready:
        blockers_projection.append("Settings are not ready for future equal-time shadow calculation.")
    blockers_legal = list(mp_readiness.get("blockers_for_legal_judgement_masks") or [])
    if not boundary_ready:
        blockers_legal.append("site_boundary is missing or not usable as a closed boundary; future legal judgement masks such as beyond-5m range and own-site exclusion are blocked.")
    if not shadow_ready:
        blockers_equal.append("No accepted shadow caster proxy elements are available.")
    if not settings_ready:
        missing = ((settings_normalized or {}).get("readiness") or {}).get("missing_for_equal_time_shadow") or []
        invalid = ((settings_normalized or {}).get("readiness") or {}).get("invalid_for_equal_time_shadow") or []
        blockers_equal.append("Settings are not ready for future equal-time shadow calculation; missing={0}, invalid={1}.".format(missing, invalid))
    if not measurement_plane_ready:
        blockers_equal.extend(blockers_mp)
    equal_ready = shadow_ready and settings_ready and measurement_plane_ready
    if not equal_ready:
        blockers_boundary.append("Boundary-dependent steps require shadow caster, settings, and measurement plane readiness first.")
    if not boundary_ready:
        blockers_boundary.append("site_boundary is missing or not usable as a closed boundary; boundary-dependent steps remain skipped.")
    return {
        "input_diagnostics_ready": True,
        "shadow_caster_ready": shadow_ready,
        "shadow_caster_geometry_ready": geom_ready,
        "footprint_extraction_ready": footprint_ready,
        "measurement_plane_ready": measurement_plane_ready,
        "measurement_plane_constructed": measurement_plane_ready,
        "future_projection_context_ready": future_projection_context_ready,
        "future_shadow_projection_ready": future_projection_ready,
        "legal_judgement_masks_ready": legal_judgement_masks_ready,
        "settings_ready_for_equal_time_shadow": settings_ready,
        "site_boundary_required_for_equal_time_shadow": False,
        "site_boundary_ready_for_boundary_dependent_steps": boundary_ready,
        "equal_time_shadow_calculation_ready": equal_ready,
        "boundary_dependent_steps_ready": equal_ready and boundary_ready,
        "blockers_for_equal_time_shadow": blockers_equal,
        "blockers_for_footprint_extraction": blockers_fp,
        "blockers_for_measurement_plane": blockers_mp,
        "blockers_for_future_projection_context": list(mp_readiness.get("blockers_for_future_shadow_projection_context") or []),
        "blockers_for_future_shadow_projection": blockers_projection,
        "blockers_for_legal_judgement_masks": blockers_legal,
        "blockers_for_boundary_dependent_steps": blockers_boundary,
        "next_implementation_steps": ["footprint extraction from user-defined shadow proxy geometry", "optional site boundary loop extraction", "legal judgement mask preparation", "true solar time diagnostics", "sun vector calculation", "time-slice shadow projection", "logical union", "shadow duration accumulation", "equal-time contour generation", "legal judgement report"],
    }

def _build_success():
    raw_inputs, input_source = _read_inputs()
    warnings = []

    for key in INPUT_KEYS:
        if key in ("site_boundary", "settings"):
            continue
        if raw_inputs.get(key) is None:
            warnings.append("{0} input is empty.".format(key))

    shadow_casters = _diagnose_shadow_casters(raw_inputs.get("building_elements"))
    site_boundary = _diagnose_site_boundary(raw_inputs.get("site_boundary"))
    settings_normalized = _normalize_settings(raw_inputs.get("settings"), raw_inputs.get("level"))
    law56_2_awareness = _build_law56_2_awareness_context(settings_normalized, site_boundary)
    measurement_plane = _construct_measurement_plane(settings_normalized, raw_inputs.get("level"))
    shadow_caster_geometry = _diagnose_shadow_caster_geometry(raw_inputs.get("building_elements"), shadow_casters, settings_normalized, measurement_plane)
    pipeline_readiness = _build_pipeline_readiness(shadow_casters, site_boundary, settings_normalized, shadow_caster_geometry, measurement_plane)
    warnings.extend(shadow_casters.get("warnings", []))
    warnings.extend(site_boundary.get("warnings", []))
    warnings.extend(settings_normalized.get("warnings", []))
    warnings.extend(law56_2_awareness.get("warnings", []))
    warnings.extend(measurement_plane.get("warnings", []))
    warnings.extend(shadow_caster_geometry.get("warnings", []))
    warnings.extend(pipeline_readiness.get("blockers_for_equal_time_shadow", []))
    warnings.extend(pipeline_readiness.get("blockers_for_footprint_extraction", []))
    warnings.extend(pipeline_readiness.get("blockers_for_measurement_plane", []))
    warnings.extend(pipeline_readiness.get("blockers_for_future_projection_context", []))
    warnings.extend(pipeline_readiness.get("blockers_for_future_shadow_projection", []))
    warnings.extend(pipeline_readiness.get("blockers_for_legal_judgement_masks", []))
    if not pipeline_readiness.get("boundary_dependent_steps_ready"):
        warnings.extend(pipeline_readiness.get("blockers_for_boundary_dependent_steps", []))

    return {
        "success": True,
        "tool": TOOL_NAME,
        "stage": STAGE_NAME,
        "message": "Dynamo_Shadow v1 input diagnostics only; measurement plane construction diagnostics and Building Standard Law Article 56-2 awareness were added. The measurement plane is an internal diagnostic data object only; no Revit element creation, true solar time calculation, sun vector calculation, shadow projection, legal judgement, 5m/10m measurement line generation, or equal-time contours are implemented.",
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
        "shadow_caster_geometry": shadow_caster_geometry,
        "law56_2_awareness": law56_2_awareness,
        "measurement_plane": measurement_plane,
        "measurement_plane_policy": MEASUREMENT_PLANE_POLICY,
        "geometry_extraction_policy": GEOMETRY_EXTRACTION_POLICY,
        "site_boundary": site_boundary,
        "site_boundary_policy": SITE_BOUNDARY_POLICY,
        "settings_normalized": settings_normalized,
        "settings_policy": SETTINGS_POLICY,
        "pipeline_readiness": pipeline_readiness,
        "planned_pipeline": PLANNED_PIPELINE,
        "warnings": warnings,
    }

def _build_failure(error_text):
    raw_inputs, input_source = _read_inputs()
    shadow_casters = None
    site_boundary = None
    settings_normalized = None
    pipeline_readiness = None
    shadow_caster_geometry = None
    law56_2_awareness = None
    measurement_plane = None
    try:
        shadow_casters = _diagnose_shadow_casters(raw_inputs.get("building_elements"))
    except Exception:
        shadow_casters = None
    try:
        site_boundary = _diagnose_site_boundary(raw_inputs.get("site_boundary"))
    except Exception:
        site_boundary = None
    try:
        settings_normalized = _normalize_settings(raw_inputs.get("settings"), raw_inputs.get("level"))
    except Exception:
        settings_normalized = None
    try:
        law56_2_awareness = _build_law56_2_awareness_context(settings_normalized or {}, site_boundary or {})
    except Exception:
        law56_2_awareness = None
    try:
        measurement_plane = _construct_measurement_plane(settings_normalized or {}, raw_inputs.get("level"))
    except Exception:
        measurement_plane = None
    try:
        shadow_caster_geometry = _diagnose_shadow_caster_geometry(raw_inputs.get("building_elements"), shadow_casters or {}, settings_normalized or {}, measurement_plane)
        pipeline_readiness = _build_pipeline_readiness(shadow_casters or {}, site_boundary or {}, settings_normalized or {}, shadow_caster_geometry, measurement_plane)
    except Exception:
        pipeline_readiness = None

    return {
        "success": False,
        "tool": TOOL_NAME,
        "stage": STAGE_NAME,
        "message": "script.py failed while building v1 measurement plane construction diagnostics.",
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
        "shadow_caster_geometry": shadow_caster_geometry,
        "law56_2_awareness": law56_2_awareness,
        "measurement_plane": measurement_plane,
        "measurement_plane_policy": MEASUREMENT_PLANE_POLICY,
        "geometry_extraction_policy": GEOMETRY_EXTRACTION_POLICY,
        "site_boundary": site_boundary,
        "site_boundary_policy": SITE_BOUNDARY_POLICY,
        "settings_normalized": settings_normalized,
        "settings_policy": SETTINGS_POLICY,
        "pipeline_readiness": pipeline_readiness,
        "planned_pipeline": PLANNED_PIPELINE,
        "warnings": [],
        "error": error_text,
    }


try:
    OUT = _build_success()
except Exception:
    OUT = _build_failure(traceback.format_exc())
