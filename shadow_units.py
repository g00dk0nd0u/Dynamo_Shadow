# Revit internal-unit to SI meter conversion diagnostics.
from shadow_policies import UNIT_CONVERSION_POLICY
from shadow_revit_api import UnitUtils, UnitTypeId, DisplayUnitType

_LENGTH = 0.3048
_AREA = 0.09290304
_VOLUME = 0.028316846592
_REVERSE_LENGTH = 3.280839895013123


def _conversion_backend():
    if UnitUtils is not None and UnitTypeId is not None:
        return "revit_unitutils_new_api"
    if UnitUtils is not None and DisplayUnitType is not None:
        return "revit_unitutils_legacy_api"
    return "fallback_factor"


def _meter_unit_id():
    if UnitTypeId is not None:
        return getattr(UnitTypeId, "Meters", None)
    if DisplayUnitType is not None:
        return getattr(DisplayUnitType, "DUT_METERS", None)
    return None


def _safe_number(value):
    if value is None:
        return None, []
    try:
        return float(value), []
    except Exception:
        return None, ["unit conversion skipped for non-numeric value: {0}".format(type(value).__name__)]


def _internal_length_to_meters(value):
    number, warnings = _safe_number(value)
    if number is None:
        return None, warnings
    unit_id = _meter_unit_id()
    if UnitUtils is not None and unit_id is not None:
        try:
            return float(UnitUtils.ConvertFromInternalUnits(number, unit_id)), warnings
        except Exception as exc:
            warnings.append("UnitUtils.ConvertFromInternalUnits failed; fallback factor used: {0}".format(str(exc)[:120]))
    return number * _LENGTH, warnings


def _meters_to_internal_length(value):
    number, warnings = _safe_number(value)
    if number is None:
        return None, warnings
    unit_id = _meter_unit_id()
    if UnitUtils is not None and unit_id is not None:
        try:
            return float(UnitUtils.ConvertToInternalUnits(number, unit_id)), warnings
        except Exception as exc:
            warnings.append("UnitUtils.ConvertToInternalUnits failed; fallback factor used: {0}".format(str(exc)[:120]))
    return number * _REVERSE_LENGTH, warnings


def _internal_area_to_m2(value):
    number, warnings = _safe_number(value)
    if number is None:
        return None, warnings
    return number * _AREA, warnings


def _internal_volume_to_m3(value):
    number, warnings = _safe_number(value)
    if number is None:
        return None, warnings
    return number * _VOLUME, warnings


def _point_raw_to_meters(point_raw):
    if point_raw is None:
        return None, []
    out = {}
    warnings = []
    for key in ("x", "y", "z"):
        converted, w = _internal_length_to_meters((point_raw or {}).get(key))
        out[key] = converted
        warnings.extend(w)
    return out, warnings


def _point_m_to_internal(point_m):
    if point_m is None:
        return None, []
    out = {}; warnings = []
    for key in ("x", "y", "z"):
        converted, w = _meters_to_internal_length((point_m or {}).get(key))
        out[key] = converted; warnings.extend(w)
    return out, warnings


def _bbox_raw_to_meters(bbox_raw):
    if bbox_raw is None:
        return None, []
    warnings = []
    min_m, w = _point_raw_to_meters((bbox_raw or {}).get("min_raw")); warnings.extend(w)
    max_m, w = _point_raw_to_meters((bbox_raw or {}).get("max_raw")); warnings.extend(w)
    out = {"min_m": min_m, "max_m": max_m, "diagnostic_only": True, "units": "meter"}
    return out, warnings


def _curve_summary_raw_to_meters(curve_summary):
    if curve_summary is None: return None, []
    out = dict(curve_summary); warnings = []
    out["length_m"], w = _internal_length_to_meters(curve_summary.get("length_raw")); warnings.extend(w)
    out["endpoint0_m"], w = _point_raw_to_meters(curve_summary.get("endpoint0_raw")); warnings.extend(w)
    out["endpoint1_m"], w = _point_raw_to_meters(curve_summary.get("endpoint1_raw")); warnings.extend(w)
    if warnings: out["unit_conversion_warnings"] = warnings
    return out, warnings


def _edge_summary_raw_to_meters(edge_summary):
    return _curve_summary_raw_to_meters(edge_summary)


def _face_summary_raw_to_meters(face_summary):
    if face_summary is None: return None, []
    out = dict(face_summary); warnings = []
    out["area_m2"], w = _internal_area_to_m2(face_summary.get("area_raw")); warnings.extend(w)
    out["origin_m"], w = _point_raw_to_meters(face_summary.get("origin_raw")); warnings.extend(w)
    out["normal_unitless"] = face_summary.get("normal_raw")
    if warnings: out["unit_conversion_warnings"] = warnings
    return out, warnings


def _solid_summary_raw_to_meters(solid_summary):
    if solid_summary is None: return None, []
    out = dict(solid_summary); warnings = []
    out["volume_m3"], w = _internal_volume_to_m3(solid_summary.get("volume_raw")); warnings.extend(w)
    out["surface_area_m2"], w = _internal_area_to_m2(solid_summary.get("surface_area_raw")); warnings.extend(w)
    out["bounding_box_m"], w = _bbox_raw_to_meters(solid_summary.get("bounding_box_raw")); warnings.extend(w)
    if warnings: out["unit_conversion_warnings"] = warnings
    return out, warnings


def _candidate_raw_to_meters(candidate):
    if candidate is None: return None, []
    out = dict(candidate); warnings = []
    out["total_length_m"], w = _internal_length_to_meters(candidate.get("total_length_raw")); warnings.extend(w)
    out["z_min_m"], w = _internal_length_to_meters(candidate.get("z_min_raw")); warnings.extend(w)
    out["z_max_m"], w = _internal_length_to_meters(candidate.get("z_max_raw")); warnings.extend(w)
    pts = []
    for point in candidate.get("endpoints_raw_sample") or []:
        p, w = _point_raw_to_meters(point); warnings.extend(w); pts.append(p)
    out["endpoints_m_sample"] = pts
    if warnings: out["unit_conversion_warnings"] = warnings
    return out, warnings


def _build_unit_conversion_diagnostics():
    return {
        "available": True,
        "diagnostic_only": True,
        "backend": _conversion_backend(),
        "length": {"internal_unit": "foot", "legal_unit": "meter", "fallback_factor": _LENGTH, "reverse_fallback_factor": _REVERSE_LENGTH},
        "area": {"internal_unit": "square_foot", "legal_unit": "square_meter", "fallback_factor": _AREA},
        "volume": {"internal_unit": "cubic_foot", "legal_unit": "cubic_meter", "fallback_factor": _VOLUME},
        "raw_fields_preserved": True,
        "converted_fields_added": True,
        "converted_fields_suffix": UNIT_CONVERSION_POLICY.get("converted_fields_suffix"),
        "used_for_legal_judgement": False,
        "used_for_shadow_projection": False,
        "warnings": [],
    }
