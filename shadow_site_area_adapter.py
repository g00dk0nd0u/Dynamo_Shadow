"""Read a single placed Revit Area boundary through SpatialElement boundary API."""
import math

from shadow_units import _internal_area_to_m2, _internal_length_to_meters
from shadow_utils import (
    _built_in_category_name_for_id,
    _category,
    _category_id_from_category,
    _safe_attr,
    _to_list,
    _try_unwrap_with_diagnostics,
    _type_name,
)

try:
    from Autodesk.Revit.DB import (
        Area,
        SpatialElement,
        SpatialElementBoundaryOptions,
        Line,
        BuiltInCategory,
    )
except Exception:
    Area = None
    SpatialElement = None
    SpatialElementBoundaryOptions = None
    Line = None
    BuiltInCategory = None

try:
    from Autodesk.Revit.DB.Architecture import Room
except Exception:
    Room = None

try:
    from Autodesk.Revit.DB.Mechanical import Space
except Exception:
    Space = None

METHOD = "revit_area_spatial_boundary_v1"


def _empty(provided=False, blocker=None):
    return {
        "provided": provided, "available": False, "complete": False,
        "method": METHOD, "source_type": None, "source_element_count": 0,
        "loop_count": 0, "loops": [], "level_id_available": False,
        "z_min_m": None, "z_max_m": None, "maximum_z_difference_m": None,
        "blockers": [] if blocker is None else [{"failure_code": blocker}],
        "warnings": [], "permit_ready_certified": False,
    }


def _flatten(value):
    out = []
    for item in _to_list(value):
        if isinstance(item, (list, tuple)):
            out.extend(_flatten(item))
        elif item is not None:
            out.append(item)
    return out


def _finite(value):
    try:
        number = float(value)
    except Exception:
        return None
    return number if math.isfinite(number) else None


def _category_name_for_element(element):
    category_id = _category_id_from_category(_category(element))
    return _built_in_category_name_for_id(category_id)


def _safe_fallback_is_area(element):
    """Limited test-double fallback; never accepts category-name-only non-spatial elements."""
    type_name = _type_name(element)
    if type_name in ("FakeArea", "Area") or getattr(element, "_is_revit_area_test_double", False):
        return True
    return False


def _is_area(element):
    if element is None:
        return False
    if Room is not None and isinstance(element, Room):
        return False
    if Space is not None and isinstance(element, Space):
        return False
    if Area is not None and isinstance(element, Area):
        return True
    lowered = _type_name(element).lower()
    if any(token in lowered for token in ("areatag", "spatialelementtag", "roomtag", "spacetag", "areaload", "filledregion", "floor", "modelcurve", "detailcurve")):
        return False
    if "generic" in lowered and "model" in lowered:
        return False
    category_name = _category_name_for_element(element)
    if SpatialElement is not None and isinstance(element, SpatialElement):
        return category_name == "OST_Areas"
    return _safe_fallback_is_area(element)


def _point_m(xyz):
    raw = []
    for attr in ("X", "Y", "Z"):
        value = _finite(getattr(xyz, attr, None))
        if value is None:
            return None, ["site boundary endpoint coordinate is unavailable or non-finite"]
        raw.append(value)
    x, wx = _internal_length_to_meters(raw[0])
    y, wy = _internal_length_to_meters(raw[1])
    z, wz = _internal_length_to_meters(raw[2])
    if any(v is None or not math.isfinite(float(v)) for v in (x, y, z)):
        return None, wx + wy + wz + ["site boundary endpoint unit conversion failed"]
    return {"x_m": x, "y_m": y, "z_m": z}, wx + wy + wz


def _curve_type(curve):
    return _type_name(curve).split(".")[-1]


def _is_line(curve):
    curve_type = _curve_type(curve).lower()
    if Line is not None and isinstance(curve, Line) and curve_type in ("line", "fakeline"):
        return True
    return curve_type in ("line", "fakeline")


def extract_site_boundary_area(area_input):
    items = []
    for raw in _flatten(area_input):
        unwrapped, _ = _try_unwrap_with_diagnostics(raw)
        items.append(unwrapped if unwrapped is not None else raw)
    if not items:
        return _empty(False)
    if len(items) > 1:
        return _empty(True, "multiple_site_boundary_areas_not_supported")

    area = items[0]
    result = _empty(True)
    result["source_element_count"] = 1
    result["source_type"] = _type_name(area).split(".")[-1]
    if not _is_area(area):
        result["blockers"].append({"failure_code": "site_boundary_input_is_not_area", "input_type": result["source_type"]})
        return result
    result["source_type"] = "Area"

    try:
        area_raw = _safe_attr(area, "Area")
        area_value = _finite(area_raw)
        if area_value is None:
            result["blockers"].append({"failure_code": "site_boundary_area_unplaced_or_unbounded", "reason": "area_value_unavailable_or_non_finite"})
            return result
        area_m2, warnings = _internal_area_to_m2(area_value)
        result["warnings"].extend(warnings)
        if area_m2 is None or not math.isfinite(float(area_m2)):
            result["blockers"].append({"failure_code": "site_boundary_area_unplaced_or_unbounded", "reason": "area_unit_conversion_failed"})
            return result
        result["area_api_m2"] = area_m2
        if area_m2 <= 0:
            result["blockers"].append({"failure_code": "site_boundary_area_unplaced_or_unbounded"})
            return result
    except Exception:
        result["blockers"].append({"failure_code": "site_boundary_area_unplaced_or_unbounded", "reason": "area_value_api_failure"})
        return result

    get_boundary = getattr(area, "GetBoundarySegments", None)
    if not callable(get_boundary):
        result["blockers"].append({"failure_code": "site_boundary_area_boundary_missing"})
        return result
    try:
        options = SpatialElementBoundaryOptions() if SpatialElementBoundaryOptions is not None else None
        loops_raw = get_boundary(options)
    except Exception:
        result["blockers"].append({"failure_code": "site_boundary_area_boundary_api_failure"})
        return result

    loops = list(loops_raw or [])
    result["loop_count"] = len(loops)
    if not loops:
        result["blockers"].append({"failure_code": "site_boundary_area_boundary_missing"})
        return result
    if len(loops) > 1:
        result["blockers"].append({"failure_code": "site_boundary_area_multiple_loops_unsupported", "loop_count": len(loops)})
        return result

    z_values = []
    for loop_index, loop in enumerate(loops):
        raw_segments = list(loop or [])
        if len(raw_segments) < 3:
            result["blockers"].append({"failure_code": "site_boundary_area_boundary_missing", "segment_count": len(raw_segments)})
            return result
        segments = []
        for segment_index, boundary_segment in enumerate(raw_segments):
            get_curve = getattr(boundary_segment, "GetCurve", None)
            if not callable(get_curve):
                result["blockers"].append({"failure_code": "site_boundary_area_boundary_missing", "segment_index": segment_index})
                return result
            try:
                curve = get_curve()
            except Exception:
                result["blockers"].append({"failure_code": "site_boundary_area_boundary_api_failure", "segment_index": segment_index})
                return result
            curve_type = _curve_type(curve)
            if not _is_line(curve):
                result["blockers"].append({"failure_code": "unsupported_site_boundary_curve_type", "curve_type": curve_type, "segment_index": segment_index})
                return result
            get_endpoint = getattr(curve, "GetEndPoint", None)
            if not callable(get_endpoint):
                result["blockers"].append({"failure_code": "site_boundary_area_boundary_missing", "segment_index": segment_index})
                return result
            try:
                start, w0 = _point_m(get_endpoint(0))
                end, w1 = _point_m(get_endpoint(1))
            except Exception:
                result["blockers"].append({"failure_code": "site_boundary_area_boundary_api_failure", "segment_index": segment_index})
                return result
            result["warnings"].extend(w0 + w1)
            if start is None or end is None:
                result["blockers"].append({"failure_code": "site_boundary_area_boundary_missing", "segment_index": segment_index})
                return result
            z_values.extend([start["z_m"], end["z_m"]])
            segments.append({"curve_type": "Line", "start": start, "end": end, "segment_index": segment_index})
        result["loops"].append({"loop_index": loop_index, "segment_count": len(segments), "segments": segments})

    result["z_min_m"] = min(z_values)
    result["z_max_m"] = max(z_values)
    result["maximum_z_difference_m"] = result["z_max_m"] - result["z_min_m"]
    result["level_id_available"] = _safe_attr(area, "LevelId") is not None
    result["available"] = True
    result["complete"] = True
    return result
