"""Optional Revit DirectShape Curve preview for site result outputs.

This Revit Adapter visualizes existing site-distance contour and maximum-duration
point outputs only. It does not recalculate distances, points, limits, or legal
pass/fail status.
"""
import math

from shadow_contour_preview import normalize_equal_time_contour_preview_settings, _segments, _curves
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

APPLICATION_ID = "Dynamo_Shadow.SiteResultPreview"
MARKER_HALF_SIZE_M = 0.5
STYLE_SEMANTICS = "visual_distinction_only_no_legal_pass_fail_meaning"
NEAR_DISTANCE_COLOR = (220, 30, 30)
FAR_DISTANCE_COLOR = (30, 90, 220)
DISTANCE_LINE_WEIGHT = 5
_DISTANCE_STYLES = {
    5.0: (NEAR_DISTANCE_COLOR, DISTANCE_LINE_WEIGHT),
    10.0: (FAR_DISTANCE_COLOR, DISTANCE_LINE_WEIGHT),
}
_MARKER_STYLES = {"near_5_to_10m": ((245, 145, 30), 8), "far_over_10m": ((210, 80, 140), 8)}


def _empty(config, site_distance_contours, measurement_masks, selected_limit_comparison, elevation):
    return {"enabled": config["mode"] != "off", "mode": config["mode"],
        "mode_source": "equal_time_contour_preview_mode", "attempted": False,
        "available": False, "complete": False, "partial_success": False,
        "source_status": {
            "site_distance_contours_complete": (site_distance_contours or {}).get("complete") is True,
            "measurement_masks_complete": (measurement_masks or {}).get("complete") is True,
            "selected_limit_comparison_complete": (selected_limit_comparison or {}).get("complete") is True,
        },
        "measurement_plane_elevation_m": elevation, "geometry_kind": "Curve",
        "all_curves_on_measurement_plane": True, "requested_group_count": 0,
        "created_group_count": 0, "created_element_count": 0,
        "created_element_ids": [], "deleted_element_count": 0, "groups": [],
        "style_semantics": STYLE_SEMANTICS, "legal_judgement_generated": False,
        "ordinance_selection_certified": False, "permit_ready_certified": False,
        "blockers": [], "warnings": list(config["warnings"])}


def _block(result, code, warning=None):
    result["blockers"].append({"failure_code": code})
    if warning:
        result["warnings"].append(warning)
    return result


def _collect_owned_preview_ids(document):
    return _collect_preview_ids(document, APPLICATION_ID)


def _distance_groups(source):
    by_distance = {5.0: [], 10.0: []}
    for contour in (source or {}).get("contours") or []:
        try: distance = float(contour.get("distance_m"))
        except (TypeError, ValueError): continue
        for target in (5.0, 10.0):
            if abs(distance - target) <= 1e-9:
                by_distance[target].append(contour)
    groups = []
    for distance in (5.0, 10.0):
        contours = by_distance[distance]
        if contours:
            groups.append({"output_kind": "site_distance_contour", "distance_m": distance,
                "contours": contours, "contour_count": len(contours),
                "name": "Dynamo_Shadow_SiteDistance_%02dm" % int(distance),
                "application_data_id": "output_kind=site_distance_contour;distance_m=%s" % int(distance)})
    return groups


def _point_xy(point):
    if not isinstance(point, dict):
        raise ValueError("site_result_preview_marker_point_missing")
    try:
        x = float(point.get("x_m")); y = float(point.get("y_m"))
    except (TypeError, ValueError):
        raise ValueError("site_result_preview_non_finite_coordinate")
    if not (math.isfinite(x) and math.isfinite(y)):
        raise ValueError("site_result_preview_non_finite_coordinate")
    return x, y


def _comparison_meta(selected_limit_comparison, key):
    item = (selected_limit_comparison or {}).get(key) if isinstance(selected_limit_comparison, dict) else None
    item = item if isinstance(item, dict) else {}
    status = item.get("status") if item.get("status") in ("within_selected_limit", "exceeds_selected_limit") else "undetermined"
    return {"selected_limit_status": status,
        "selected_limit_minutes": item.get("selected_limit_minutes"),
        "excess_minutes": item.get("excess_minutes")}


def _marker_groups(measurement_masks, selected_limit_comparison):
    groups = []
    for key, zone, name in (("near", "near_5_to_10m", "Dynamo_Shadow_MaxPoint_Near"),
                            ("far", "far_over_10m", "Dynamo_Shadow_MaxPoint_Far")):
        item = (measurement_masks or {}).get(key) if isinstance(measurement_masks, dict) else None
        if not isinstance(item, dict) or item.get("available") is False:
            continue
        point = item.get("point")
        if point is None:
            continue
        meta = _comparison_meta(selected_limit_comparison, key)
        groups.append({"output_kind": "maximum_shadow_duration_marker", "zone": zone,
            "point": point, "name": name,
            "maximum_shadow_duration_minutes": item.get("maximum_shadow_duration_minutes"),
            "application_data_id": "output_kind=maximum_shadow_duration_marker;zone=%s" % zone,
            **meta})
    return groups


def _marker_curves(point, elevation_m, short_tolerance_internal=0.0):
    x, y = _point_xy(point); h = MARKER_HALF_SIZE_M
    return _curves([((x - h, y - h), (x + h, y + h)), ((x - h, y + h), (x + h, y - h))],
                   elevation_m, short_tolerance_internal)


def _apply_override(view, element_id, group):
    if view is None or OverrideGraphicSettings is None or Color is None:
        return False
    if group.get("output_kind") == "site_distance_contour":
        rgb, weight = _DISTANCE_STYLES.get(float(group.get("distance_m")), ((0, 0, 0), 5))
    else:
        rgb, weight = _MARKER_STYLES.get(group.get("zone"), ((0, 0, 0), 8))
    override = OverrideGraphicSettings(); override.SetProjectionLineColor(Color(*rgb)); override.SetProjectionLineWeight(weight)
    view.SetElementOverrides(element_id, override); return True


def _sanitize_group(group):
    return {k: v for k, v in group.items() if k not in ("contours", "point", "application_data_id", "name")}


def build_site_result_preview(site_distance_contours, measurement_masks, selected_limit_comparison, measurement_plane, settings):
    config = normalize_equal_time_contour_preview_settings(settings)
    elevation = (measurement_plane or {}).get("elevation_m")
    result = _empty(config, site_distance_contours, measurement_masks, selected_limit_comparison, elevation)
    if config["mode"] == "off": return result
    result["attempted"] = True
    prepared = []
    if config["mode"] == "replace":
        distance_available = (site_distance_contours or {}).get("complete") is True and bool((site_distance_contours or {}).get("contours"))
        masks_available = (measurement_masks or {}).get("complete") is True and (bool((measurement_masks or {}).get("near")) or bool((measurement_masks or {}).get("far")))
        if not distance_available and not masks_available:
            return _block(result, "site_result_preview_sources_unavailable")
        try:
            elevation = float(elevation)
            if not math.isfinite(elevation): raise ValueError()
        except (TypeError, ValueError):
            return _block(result, "site_result_preview_measurement_plane_missing")
        source_complete_for_preview = True
        if distance_available:
            distance_groups = _distance_groups(site_distance_contours)
            prepared.extend(distance_groups)
            missing_distances = [value for value in (5.0, 10.0)
                if not any(group.get("distance_m") == value for group in distance_groups)]
            if missing_distances:
                source_complete_for_preview = False
                result["warnings"].append("Site distance contour source is missing one or more fixed 5m/10m contours; distance preview is partial.")
        else:
            source_complete_for_preview = False
            result["warnings"].append("Site distance contour source unavailable; distance preview skipped.")
        if masks_available:
            marker_groups = _marker_groups(measurement_masks, selected_limit_comparison)
            prepared.extend(marker_groups)
            for zone_key, zone_name in (("near", "near_5_to_10m"), ("far", "far_over_10m")):
                item = (measurement_masks or {}).get(zone_key) or {}
                marker_created_from_source = any(group.get("zone") == zone_name for group in marker_groups)
                if item.get("available") is False or not marker_created_from_source:
                    source_complete_for_preview = False
                    result["warnings"].append("Maximum point source for %s is unavailable; marker skipped." % zone_name)
        else:
            source_complete_for_preview = False
            result["warnings"].append("Measurement mask maximum-point source unavailable; marker preview skipped.")
        if not prepared:
            return _block(result, "site_result_preview_sources_unavailable")
        result["requested_group_count"] = len(prepared)
        result["_source_complete_for_preview"] = source_complete_for_preview
    required = (DocumentManager, TransactionManager, DirectShape, XYZ, Line, FilteredElementCollector, SubTransaction)
    if any(item is None for item in required):
        result["warnings"].append("Revit site result preview API is unavailable; preview skipped."); return result
    try:
        document = DocumentManager.Instance.CurrentDBDocument; view = document.ActiveView
        cleanup = _collect_owned_preview_ids(document)
    except BaseException as exc:
        return _block(result, "site_result_preview_document_access_failed", _safe_message(exc))
    if not cleanup.get("succeeded"):
        return _block(result, "site_result_preview_cleanup_collection_failed")
    started = False; sub = None
    try:
        TransactionManager.Instance.EnsureInTransaction(document); started = True
        sub = SubTransaction(document); sub.Start()
        for ident in cleanup["element_ids"]:
            document.Delete(ident); result["deleted_element_count"] += 1
        if config["mode"] == "replace":
            tolerance = float(getattr(document.Application, "ShortCurveTolerance", 0.0))
            for source_group in prepared:
                group = _sanitize_group(source_group); group.update({"curve_count": 0, "created": False, "element_id": None})
                shape = None
                try:
                    if source_group["output_kind"] == "site_distance_contour":
                        segs = _segments(source_group["contours"])
                        curves = _curves(segs, elevation, tolerance)
                    else:
                        curves = _marker_curves(source_group["point"], elevation, tolerance)
                    group["curve_count"] = len(curves)
                    if not curves: raise ValueError("site_result_preview_no_valid_curves")
                    shape = DirectShape.CreateElement(document, ElementId(BuiltInCategory.OST_GenericModel))
                    shape.SetShape(curves)
                    plan_diag = {"warnings": []}; _set_plan_curve_representation(shape, curves, plan_diag)
                    result["warnings"].extend(plan_diag["warnings"])
                    shape.Name = source_group["name"]; shape.ApplicationId = APPLICATION_ID; shape.ApplicationDataId = source_group["application_data_id"]
                    group.update({"created": True, "element_id": _element_id(shape)})
                    result["created_element_ids"].append(group["element_id"])
                    try:
                        if not _apply_override(view, shape.Id, source_group):
                            result["warnings"].append("Site result projection-line override API is unavailable.")
                    except BaseException:
                        result["warnings"].append("Site result graphical override failed; curves were retained.")
                except BaseException as exc:
                    if shape is not None:
                        try: document.Delete(shape.Id)
                        except BaseException: pass
                    group["warning"] = _safe_message(exc)
                    result["warnings"].append("Site result preview group failed: %s" % group["warning"])
                result["groups"].append(group)
            if prepared and not result["created_element_ids"]:
                raise ValueError("site_result_preview_all_groups_failed")
        sub.Commit(); sub = None
    except BaseException as exc:
        if sub is not None:
            try: sub.RollBack(); result["deleted_element_count"] = 0
            except BaseException: pass
        _block(result, "site_result_preview_write_failed", _safe_message(exc))
    finally:
        if started:
            try: TransactionManager.Instance.TransactionTaskDone()
            except BaseException as exc: _block(result, "site_result_preview_transaction_close_failed", _safe_message(exc))
    result["created_element_count"] = len(result["created_element_ids"])
    result["created_group_count"] = sum(1 for group in result["groups"] if group.get("created") is True)
    result["available"] = not result["blockers"]
    source_complete = result.pop("_source_complete_for_preview", True)
    result["complete"] = result["available"] and (config["mode"] == "clear" or (source_complete and result["created_group_count"] == result["requested_group_count"]))
    result["partial_success"] = result["available"] and not result["complete"] and result["created_group_count"] > 0
    return result
