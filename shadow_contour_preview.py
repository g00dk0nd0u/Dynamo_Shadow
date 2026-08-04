"""Optional Revit DirectShape Curve preview of equal-time contours.

This adapter visualizes technical contour output only.  It does not alter the
contour calculation and its elements are not legal-judgement inputs.
"""
import math

from shadow_policies import SETTINGS_DIAGNOSTIC_DEFAULTS
from shadow_preview import (_collect_owned_preview_ids as _collect_preview_ids, _element_id,
                            _safe_message, _set_plan_curve_representation)
from shadow_units import _meters_to_internal_length
from shadow_revit_api import (BuiltInCategory, ElementId, XYZ, Line, DirectShape,
    FilteredElementCollector, OverrideGraphicSettings, Color, SubTransaction)

try:
    from RevitServices.Persistence import DocumentManager
except Exception:
    DocumentManager = None
try:
    from RevitServices.Transactions import TransactionManager
except Exception:
    TransactionManager = None


APPLICATION_ID = "Dynamo_Shadow.EqualTimeContourPreview"


def normalize_equal_time_contour_preview_settings(settings):
    source = (settings or {}).get("normalized") if isinstance(settings, dict) else None
    source = source if isinstance(source, dict) else (settings if isinstance(settings, dict) else {})
    mode = source.get("equal_time_contour_preview_mode",
                      SETTINGS_DIAGNOSTIC_DEFAULTS["equal_time_contour_preview_mode"])
    warnings = []
    if mode not in ("off", "replace", "clear"):
        warnings.append("settings.equal_time_contour_preview_mode must be off, replace, or clear; contour preview disabled.")
        mode = "off"
    return {"mode": mode, "warnings": warnings}


def _empty(config, source, elevation):
    return {"enabled": config["mode"] != "off", "mode": config["mode"],
        "attempted": False, "available": False, "complete": False,
        "partial_success": False,
        "source_available": bool((source or {}).get("available")),
        "requested_level_count": 0, "created_level_count": 0,
        "created_element_count": 0, "created_element_ids": [],
        "deleted_element_count": 0,
        "measurement_plane_elevation_m": elevation, "geometry_kind": "Curve",
        "all_curves_on_measurement_plane": True, "groups": [], "blockers": [],
        "warnings": list(config["warnings"]), "permit_ready_certified": False}


def _block(result, code, warning=None):
    result["blockers"].append({"failure_code": code})
    if warning:
        result["warnings"].append(warning)
    return result


def _level_groups(source):
    groups = {}
    for contour in (source or {}).get("contours") or []:
        level = float(contour.get("level_minutes"))
        if not math.isfinite(level) or level <= 0:
            raise ValueError("contour_preview_non_finite_level")
        groups.setdefault(level, []).append(contour)
    return [(level, groups[level]) for level in sorted(groups)]


def _segments(contours, short_tolerance_m=0.0):
    """Return finite meter-coordinate segments, closing closed contours."""
    result = []
    tolerance = max(0.0, float(short_tolerance_m or 0.0))
    for contour in contours:
        points = contour.get("points_m") or []
        if len(points) < 2:
            continue
        pairs = [(points[i], points[i + 1]) for i in range(len(points) - 1)]
        if contour.get("closed") is True:
            pairs.append((points[-1], points[0]))
        for start, end in pairs:
            values = tuple(float(p[k]) for p in (start, end) for k in ("x", "y"))
            if not all(math.isfinite(value) for value in values):
                raise ValueError("contour_preview_non_finite_coordinate")
            x1, y1, x2, y2 = values
            if math.hypot(x2 - x1, y2 - y1) <= tolerance:
                continue
            result.append(((x1, y1), (x2, y2)))
    return result


def _curves(segments, elevation_m, short_tolerance_internal=0.0):
    z, _ = _meters_to_internal_length(elevation_m)
    curves = []
    for start, end in segments:
        x1, _ = _meters_to_internal_length(start[0]); y1, _ = _meters_to_internal_length(start[1])
        x2, _ = _meters_to_internal_length(end[0]); y2, _ = _meters_to_internal_length(end[1])
        a, b = XYZ(x1, y1, z), XYZ(x2, y2, z)
        if float(a.DistanceTo(b)) <= max(0.0, short_tolerance_internal):
            continue
        curves.append(Line.CreateBound(a, b))
    return curves


def _preview_element_name(level):
    return "Dynamo_Shadow_EqualTime_%04dmin" % int(round(level))


def _collect_owned_preview_ids(document):
    return _collect_preview_ids(document, APPLICATION_ID)


def _apply_override(view, element_id):
    if view is None or OverrideGraphicSettings is None or Color is None:
        return False
    override = OverrideGraphicSettings()
    override.SetProjectionLineColor(Color(35, 105, 230))
    override.SetProjectionLineWeight(6)
    view.SetElementOverrides(element_id, override)
    return True


def build_equal_time_contour_preview(equal_time_contours, measurement_plane, settings):
    config = normalize_equal_time_contour_preview_settings(settings)
    elevation = (measurement_plane or {}).get("elevation_m")
    result = _empty(config, equal_time_contours, elevation)
    if config["mode"] == "off":
        return result
    result["attempted"] = True
    if config["mode"] == "replace":
        if (equal_time_contours or {}).get("complete") is not True:
            return _block(result, "contour_preview_source_incomplete")
        try:
            elevation = float(elevation)
            if not math.isfinite(elevation): raise ValueError()
        except (TypeError, ValueError):
            return _block(result, "contour_preview_measurement_plane_missing")
        try:
            groups = _level_groups(equal_time_contours)
            prepared = [(level, contours, _segments(contours)) for level, contours in groups]
        except (TypeError, ValueError, KeyError) as exc:
            return _block(result, str(exc) or "contour_preview_source_invalid")
        result["requested_level_count"] = len(prepared)
    else:
        prepared = []

    required = (DocumentManager, TransactionManager, DirectShape, XYZ, Line,
                FilteredElementCollector, SubTransaction)
    if any(item is None for item in required):
        result["warnings"].append("Revit contour preview API is unavailable; preview skipped.")
        return result
    try:
        document = DocumentManager.Instance.CurrentDBDocument
        view = document.ActiveView
        cleanup = _collect_owned_preview_ids(document)
    except BaseException as exc:
        return _block(result, "contour_preview_document_access_failed", _safe_message(exc))
    if not cleanup.get("succeeded"):
        return _block(result, "contour_preview_cleanup_collection_failed")

    started = False; sub = None
    try:
        TransactionManager.Instance.EnsureInTransaction(document); started = True
        sub = SubTransaction(document); sub.Start()
        for ident in cleanup["element_ids"]:
            document.Delete(ident); result["deleted_element_count"] += 1
        if config["mode"] == "replace":
            tolerance = float(getattr(document.Application, "ShortCurveTolerance", 0.0))
            for level, contours, segments in prepared:
                group = {"level_minutes": level, "contour_count": len(contours),
                         "curve_count": 0, "created": False, "element_id": None}
                shape = None
                try:
                    curves = _curves(segments, elevation, tolerance)
                    group["curve_count"] = len(curves)
                    if not curves: raise ValueError("contour_preview_no_valid_curves")
                    shape = DirectShape.CreateElement(document, ElementId(BuiltInCategory.OST_GenericModel))
                    shape.SetShape(curves)
                    plan_diag = {"warnings": []}
                    _set_plan_curve_representation(shape, curves, plan_diag)
                    result["warnings"].extend(plan_diag["warnings"])
                    shape.Name = _preview_element_name(level)
                    shape.ApplicationId = APPLICATION_ID
                    shape.ApplicationDataId = "level_minutes=%s;output_kind=equal_time_contour" % level
                    group.update({"created": True, "element_id": _element_id(shape)})
                    result["created_element_ids"].append(group["element_id"])
                    try:
                        if not _apply_override(view, shape.Id):
                            result["warnings"].append("Contour projection-line override API is unavailable.")
                    except BaseException:
                        result["warnings"].append("Contour graphical override failed; curves were retained.")
                except BaseException as exc:
                    if shape is not None:
                        try: document.Delete(shape.Id)
                        except BaseException: pass
                    group["warning"] = _safe_message(exc)
                    result["warnings"].append(
                        "Equal-time contour level %s preview failed: %s" %
                        (level, group["warning"]))
                result["groups"].append(group)
            if not result["created_element_ids"]:
                raise ValueError("contour_preview_all_groups_failed")
        sub.Commit(); sub = None
    except BaseException as exc:
        if sub is not None:
            try: sub.RollBack(); result["deleted_element_count"] = 0
            except BaseException: pass
        _block(result, "contour_preview_write_failed", _safe_message(exc))
    finally:
        if started:
            try: TransactionManager.Instance.TransactionTaskDone()
            except BaseException as exc: _block(result, "contour_preview_transaction_close_failed", _safe_message(exc))

    result["created_element_count"] = len(result["created_element_ids"])
    result["created_level_count"] = sum(group["created"] for group in result["groups"])
    result["available"] = not result["blockers"]
    result["complete"] = result["available"] and (config["mode"] == "clear" or
        result["created_level_count"] == result["requested_level_count"])
    result["partial_success"] = result["available"] and not result["complete"]
    return result


_build_equal_time_contour_preview = build_equal_time_contour_preview
