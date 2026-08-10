"""Optional Revit DirectShape Curve preview of unified time-slice shadows."""
import math
import re

import shadow_utils
from shadow_profiles import get_solar_profile
from shadow_policies import SETTINGS_DIAGNOSTIC_DEFAULTS
from shadow_units import _meters_to_internal_length
from shadow_graphical_override import (apply_and_readback, empty_readback_summary,
    add_to_readback_summary)
from shadow_revit_api import (BuiltInCategory, ElementId, XYZ, Line, GeometryObject, DirectShape,
    DirectShapeTargetViewType, FilteredElementCollector, OverrideGraphicSettings,
    Color, SubTransaction, ViewShapeBuilder, REVIT_API_CAPABILITIES)

try:
    from RevitServices.Persistence import DocumentManager
except Exception:
    DocumentManager = None
try:
    from RevitServices.Transactions import TransactionManager
except Exception:
    TransactionManager = None

APPLICATION_ID = "Dynamo_Shadow.FormalShadowPreview"
GENERATION_METHOD = "revit_extrusion_analyzer_curve_loop_line_exact"
HOURLY_SHADOW_COLOR = (0, 0, 0)
HOURLY_SHADOW_LINE_WEIGHT = 2


def _checkpoint(stage, detail=None):
    callback = getattr(shadow_utils, "RUNTIME_CHECKPOINT", None)
    if callback:
        try: callback(stage, detail)
        except BaseException: pass


def _canonical_time(value):
    if not isinstance(value, str): return None
    parts = value.strip().split(":")
    if len(parts) not in (2, 3): return None
    try: nums = [int(part) for part in parts]
    except Exception: return None
    if len(nums) == 2: nums.append(0)
    if not (0 <= nums[0] < 24 and 0 <= nums[1] < 60 and 0 <= nums[2] < 60): return None
    return "%02d:%02d:%02d" % tuple(nums)


def _hourly_profile_times(profile_name):
    profile = get_solar_profile(profile_name) or get_solar_profile("standard_8_16")
    start = int(profile["window_start"].split(":")[0]) * 60 + int(profile["window_start"].split(":")[1])
    end = int(profile["window_end"].split(":")[0]) * 60 + int(profile["window_end"].split(":")[1])
    step = int(profile.get("reference_shape_interval_minutes", 60))
    return ["%02d:%02d:00" % (minute // 60, minute % 60) for minute in range(start, end + 1, step)]


def normalize_preview_settings(settings):
    source = (settings or {}).get("normalized") if isinstance(settings, dict) else None
    source = source if isinstance(source, dict) else (settings if isinstance(settings, dict) else {})
    warnings = []; valid = True
    mode = source.get("preview_mode", SETTINGS_DIAGNOSTIC_DEFAULTS["preview_mode"])
    if mode not in ("off", "replace", "clear"):
        warnings.append("settings.preview_mode must be off, replace, or clear; preview disabled."); valid = False
    raw = source.get("preview_true_solar_times")
    raw = _hourly_profile_times(source.get("profile", "standard_8_16")) if raw is None else raw
    if not isinstance(raw, (list, tuple)):
        warnings.append("settings.preview_true_solar_times must be a list; preview disabled."); raw = []; valid = False
    times = []
    for value in raw:
        canonical = _canonical_time(value)
        if canonical is None:
            warnings.append("Each preview time must be HH:MM or HH:MM:SS; preview disabled."); valid = False
        elif canonical not in times: times.append(canonical)
    return {"valid": valid, "mode": mode if valid else "off", "requested_true_solar_times": times, "warnings": warnings}


def _empty(config, unified, elevation):
    return {"enabled": config["mode"] != "off", "mode": config["mode"], "attempted": False,
        "available": False, "complete": False, "partial_success": False,
        "unified_shadow_source_available": bool((unified or {}).get("available")),
        "formal_shadow_source_available": False,
        "requested_true_solar_times": list(config["requested_true_solar_times"]), "matched_true_solar_times": [],
        "created_element_count": 0, "created_element_ids": [], "deleted_element_count": 0,
        "failed_group_count": 0, "measurement_plane_elevation_m": elevation,
        "geometry_kind": "Curve", "all_curves_on_measurement_plane": True,
        "active_view_id": None, "active_view_type": None, "plan_north_mode": None,
        "active_view_is_plan": False, "active_view_is_3d": False,
        "direction_readable_as_north_up": False, "non_plan_view_warning": None,
        "view_up_direction_model": None, "true_north_direction_model": None,
        "target_view_type_available": REVIT_API_CAPABILITIES["direct_shape_target_view_type_available"],
        "view_shape_builder_available": REVIT_API_CAPABILITIES["view_shape_builder_available"],
        "plan_representation_available": REVIT_API_CAPABILITIES["direct_shape_plan_representation_available"],
        "graphical_overrides_attempted": False, "graphical_overrides_succeeded": False,
        "graphical_overrides_write_succeeded": False,
        "graphical_overrides_readback_succeeded": False,
        "graphical_overrides_verified": False,
        "graphical_override_readback": empty_readback_summary(),
        "groups": [], "failure_reason_counts": {}, "warnings": list(config["warnings"]),
        "failure_stage": None, "failure_code": None, "failure_type": None, "sanitized_failure_message": None,
        "transaction_begin_attempted": False, "transaction_begin_succeeded": False,
        "transaction_close_attempted": False, "transaction_close_succeeded": False,
        "cleanup_collection_attempted": False, "cleanup_collection_succeeded": False,
        "cleanup_collector_method": None, "cleanup_collector_fallback_used": False,
        "cleanup_candidate_count": 0, "cleanup_owned_count": 0, "cleanup_delete_attempted": False,
        "cleanup_delete_succeeded": False, "requested_delete_count": 0, "successful_delete_count": 0,
        "failed_delete_count": 0, "cleanup_collection_attempts": []}


def _element_id(value):
    ident = getattr(value, "Id", value)
    for name in ("Value", "IntegerValue"):
        try: return int(getattr(ident, name))
        except BaseException: pass
    try: return int(ident)
    except BaseException: return None


def _safe_message(exc):
    text = re.sub(r"\s+", " ", str(exc)).strip()
    text = re.sub(r"[A-Za-z]:[\\/][^ ]+|/(?:Users|home)/[^ ]+", "<redacted_path>", text)
    return text[:240]


def _is_direct_shape(element):
    try:
        if isinstance(element, DirectShape): return True
    except BaseException: pass
    try: return element.GetType().FullName == "Autodesk.Revit.DB.DirectShape"
    except BaseException: return False


def _collect_owned_preview_ids(document, application_id=APPLICATION_ID):
    result = {"succeeded": False, "element_ids": [], "collector_method": None, "scanned_element_count": 0,
        "direct_shape_candidate_count": 0, "owned_element_count": 0, "fallback_used": False, "attempts": [],
        "failure_code": None, "failure_type": None, "failure_message": None}
    last = None
    for method, fallback in (("of_class_direct_shape", False), ("generic_model_category_fallback", True)):
        try:
            collector = FilteredElementCollector(document)
            collector = collector.OfCategory(BuiltInCategory.OST_GenericModel) if fallback else collector.OfClass(DirectShape)
            elements = list(collector.WhereElementIsNotElementType().ToElements())
            candidates = [item for item in elements if _is_direct_shape(item)]
            owned = [item.Id for item in candidates if getattr(item, "ApplicationId", None) == application_id]
            result.update({"succeeded": True, "element_ids": owned, "collector_method": method,
                "scanned_element_count": len(elements), "direct_shape_candidate_count": len(candidates),
                "owned_element_count": len(owned), "fallback_used": fallback})
            result["attempts"].append({"collector_method": method, "succeeded": True, "candidate_count": len(candidates),
                "owned_count": len(owned), "fallback_used": fallback, "failure_type": None})
            return result
        except BaseException as exc:
            last = exc; result["attempts"].append({"collector_method": method, "succeeded": False,
                "candidate_count": 0, "owned_count": 0, "fallback_used": fallback, "failure_type": type(exc).__name__})
    result.update({"collector_method": "generic_model_category_fallback", "fallback_used": True,
        "failure_code": "preview_cleanup_collection_failed", "failure_type": type(last).__name__, "failure_message": _safe_message(last)})
    return result


def _selected_groups(unified, requested, warnings):
    by_time = {_canonical_time(item.get("true_solar_time")): item for item in (unified or {}).get("slices") or []}
    groups = []; matched = []
    for style_index, key in enumerate(requested):
        item = by_time.get(key)
        if item is None:
            warnings.append("Requested preview true solar time %s was not found; no nearest slice was selected." % key); continue
        if item.get("complete") is not True or not item.get("polygons"):
            warnings.append("Unified shadow slice %s is incomplete or empty; preview skipped." % key); continue
        matched.append(key)
        groups.append({"slice_index": item.get("slice_index"), "true_solar_time": key,
            "polygons": item.get("polygons"), "style_index": style_index,
            "physical_shadow_ray_model": item.get("physical_shadow_ray_model")})
    return groups, matched


def _curves(polygons, elevation_m, short_tolerance):
    z, _ = _meters_to_internal_length(elevation_m); curves = []
    for polygon in polygons:
        points = polygon.get("points_m") or []
        if polygon.get("closed") is not True or polygon.get("role") not in ("outer", "inner") or len(points) < 3:
            raise ValueError("preview_polygon_validation_failed")
        native = []
        for point in points:
            x, y = float(point["x"]), float(point["y"])
            if not math.isfinite(x) or not math.isfinite(y): raise ValueError("preview_non_finite_coordinate")
            xi, _ = _meters_to_internal_length(x); yi, _ = _meters_to_internal_length(y); native.append(XYZ(xi, yi, z))
        for index, start in enumerate(native):
            end = native[(index + 1) % len(native)]
            length = float(start.DistanceTo(end))
            if length <= max(0.0, short_tolerance): raise ValueError("preview_short_segment")
            curves.append(Line.CreateBound(start, end))
    return curves


def _geometry_object_list(curves):
    """Create the exact ICollection<GeometryObject> overload expected by Revit."""
    system = __import__("System")
    values = system.Collections.Generic.List[GeometryObject]()
    for curve in curves: values.Add(curve)
    return values

# Compatibility alias used by focused pure-Python tests.
def _curve_loops(polygons, elevation_m, z_offset_mm=0.0, short_tolerance=0.0):
    if z_offset_mm: raise ValueError("preview_vertical_offset_not_supported")
    return _curves(polygons, elevation_m, short_tolerance)


def _preview_element_name(group):
    return "Dynamo_Shadow_TimeLine_%s" % group["true_solar_time"][:5].replace(":", "")


def _apply_override(view, element_id, style_index):
    # Every time slice is deliberately subordinate to the regulatory contours.
    return apply_and_readback(view, element_id, HOURLY_SHADOW_COLOR,
        HOURLY_SHADOW_LINE_WEIGHT, OverrideGraphicSettings, Color)


def _view_diagnostics(view, true_north_deg):
    result = {"active_view_type": None, "plan_north_mode": None, "view_up_direction_model": None,
        "active_view_is_plan": False, "active_view_is_3d": False,
        "direction_readable_as_north_up": False, "non_plan_view_warning": None,
        "true_north_direction_model": {"x": math.sin(math.radians(true_north_deg)), "y": math.cos(math.radians(true_north_deg)), "z": 0.0}}
    if view is None: return result
    try: result["active_view_type"] = str(view.ViewType)
    except BaseException: pass
    view_type = (result["active_view_type"] or "").lower()
    class_name = type(view).__name__.lower()
    result["active_view_is_3d"] = "three" in view_type or "3d" in view_type or "view3d" in class_name
    result["active_view_is_plan"] = ("plan" in view_type or "viewplan" in class_name) and not result["active_view_is_3d"]
    try:
        up = view.UpDirection; result["view_up_direction_model"] = {"x": float(up.X), "y": float(up.Y), "z": float(up.Z)}
    except BaseException: pass
    if result["active_view_is_plan"]:
        try: result["plan_north_mode"] = str(view.GetOrientation())
        except BaseException: pass
    else:
        result["non_plan_view_warning"] = "Active view is not a Plan view; Plan North mode is not applicable."
    up = result.get("view_up_direction_model"); north = result["true_north_direction_model"]
    if result["active_view_is_plan"] and up:
        result["direction_readable_as_north_up"] = (up["x"]*north["x"] + up["y"]*north["y"]) >= 0.999
    return result


def _set_plan_curve_representation(shape, curves, diag):
    diag["invalid_plan_curve_indices"] = []
    if ViewShapeBuilder is None or DirectShapeTargetViewType is None or not hasattr(DirectShapeTargetViewType, "Plan"):
        diag["plan_representation_set"] = False; return
    builder = None
    try:
        builder = ViewShapeBuilder(DirectShapeTargetViewType.Plan)
        for index, curve in enumerate(curves):
            try:
                # Revit 2024.3 exposes this as the static two-argument overload.
                valid = bool(ViewShapeBuilder.ValidateCurve(
                    curve, DirectShapeTargetViewType.Plan))
            except BaseException as exc:
                # Some CPython/pythonnet builds cannot bind ValidateCurve.  Let
                # AddCurve perform the per-curve validation in that case.
                try:
                    builder.AddCurve(curve)
                    continue
                except BaseException as add_exc:
                    valid = False
                    reason = (type(exc).__name__ + ": " + _safe_message(exc)
                              + "; AddCurve " + type(add_exc).__name__ + ": "
                              + _safe_message(add_exc))
            else: reason = "ValidateCurve returned false"
            if not valid:
                diag["invalid_plan_curve_indices"].append({"index": index, "reason": reason}); continue
            builder.AddCurve(curve)
        if diag["invalid_plan_curve_indices"]:
            diag["plan_representation_set"] = False
            diag["warnings"].append("One or more Plan curves were invalid; Default Curve representation retained."); return
        # ViewShapeBuilder is itself the ShapeBuilder passed to DirectShape;
        # its constructor already records the Plan target representation.
        shape.SetShape(builder)
        diag["plan_representation_set"] = True
    except BaseException as exc:
        diag["plan_representation_set"] = False; diag["plan_representation_failure_type"] = type(exc).__name__
        diag["plan_representation_failure_message"] = _safe_message(exc)
        diag["warnings"].append("Plan Curve representation failed; Default Curve representation retained.")
    finally:
        if builder is not None:
            try: builder.Dispose()
            except BaseException: pass


def _screen_relative(ray, view_up):
    if not ray or not view_up: return None
    ux, uy = view_up["x"], view_up["y"]; right = (uy, -ux)
    return {"right": ray["x"] * right[0] + ray["y"] * right[1], "up": ray["x"] * ux + ray["y"] * uy,
        "note": "screen direction is distinct from true north"}


def build_shadow_preview(unified_shadow_slices, measurement_plane, settings):
    config = normalize_preview_settings(settings); elevation = (measurement_plane or {}).get("elevation_m")
    result = _empty(config, unified_shadow_slices, elevation)
    if config["mode"] == "off": return result
    result["attempted"] = True
    required = (DocumentManager, TransactionManager, DirectShape, XYZ, Line, FilteredElementCollector, SubTransaction)
    if any(item is None for item in required): result["warnings"].append("Revit preview API is unavailable; preview skipped."); return result
    try: document = DocumentManager.Instance.CurrentDBDocument; view = document.ActiveView
    except BaseException as exc:
        result.update({"failure_stage":"document_access", "failure_code":"preview_document_access_failed", "failure_type":type(exc).__name__, "sanitized_failure_message":_safe_message(exc)}); return result
    result["active_view_id"] = _element_id(view)
    normalized = (settings or {}).get("normalized") or settings or {}
    result.update(_view_diagnostics(view, float(normalized.get("true_north_deg", 0.0) or 0.0)))
    groups, result["matched_true_solar_times"] = _selected_groups(unified_shadow_slices, config["requested_true_solar_times"], result["warnings"])
    cleanup = _collect_owned_preview_ids(document); result["cleanup_collection_attempted"] = True
    result.update({"cleanup_collection_succeeded":cleanup["succeeded"], "cleanup_collector_method":cleanup["collector_method"],
        "cleanup_collector_fallback_used":cleanup["fallback_used"], "cleanup_candidate_count":cleanup["direct_shape_candidate_count"],
        "cleanup_owned_count":cleanup["owned_element_count"], "cleanup_collection_attempts":cleanup["attempts"]})
    if not cleanup["succeeded"]:
        result.update({"failure_stage":"cleanup_collection", "failure_code":cleanup["failure_code"], "failure_type":cleanup["failure_type"], "sanitized_failure_message":cleanup["failure_message"]}); return result
    started = False; sub = None; committed = False
    try:
        result["transaction_begin_attempted"] = True; TransactionManager.Instance.EnsureInTransaction(document); started = True; result["transaction_begin_succeeded"] = True
        if config["mode"] == "replace": sub = SubTransaction(document); sub.Start()
        owned = cleanup["element_ids"]; result["cleanup_delete_attempted"] = bool(owned); result["requested_delete_count"] = len(owned)
        deletion_error = None
        for ident in owned:
            try: document.Delete(ident); result["successful_delete_count"] += 1
            except BaseException as exc: deletion_error = deletion_error or exc; result["failed_delete_count"] += 1
        result["cleanup_delete_succeeded"] = deletion_error is None; result["deleted_element_count"] = result["successful_delete_count"]
        if deletion_error: raise deletion_error
        if config["mode"] == "replace":
            short = float(getattr(document.Application, "ShortCurveTolerance", 0.0))
            for group in groups:
                diag = {"slice_index":group["slice_index"], "true_solar_time":group["true_solar_time"],
                    "style_index":group["style_index"], "outer_loop_count":sum(p.get("role")=="outer" for p in group["polygons"]),
                    "inner_loop_count":sum(p.get("role")=="inner" for p in group["polygons"]), "curve_count":0,
                    "geometry_kind":"Curve", "z_elevation_m":elevation, "direct_shape_created":False, "element_id":None,
                    "screen_relative_shadow_direction":_screen_relative(group.get("physical_shadow_ray_model"), result["view_up_direction_model"]), "warnings":[]}
                shape = None
                try:
                    curves = _curves(group["polygons"], elevation, short); diag["curve_count"] = len(curves)
                    shape = DirectShape.CreateElement(document, ElementId(BuiltInCategory.OST_GenericModel))
                    shape.SetShape(curves)
                    _set_plan_curve_representation(shape, curves, diag)
                    shape.Name = _preview_element_name(group); shape.ApplicationId = APPLICATION_ID
                    shape.ApplicationDataId = "true_solar_time=%s;slice_index=%s;output_kind=time_shadow_line" % (group["true_solar_time"], group["slice_index"])
                    diag.update({"element_id": _element_id(shape), "element_name": shape.Name,
                        "application_id": APPLICATION_ID, "application_data_id": shape.ApplicationDataId,
                        "output_kind": "time_shadow_line",
                        "default_curve_representation_retained": not diag.get("plan_representation_set", False),
                        "active_view_is_3d": result["active_view_is_3d"]})
                    diag["direct_shape_created"] = True; result["created_element_ids"].append(diag["element_id"])
                    result["graphical_overrides_attempted"] = True
                    try:
                        override_diag = _apply_override(view, shape.Id, group["style_index"])
                        diag["graphical_override"] = override_diag
                        add_to_readback_summary(result["graphical_override_readback"], override_diag)
                        ok = override_diag["set_succeeded"]
                        result["graphical_overrides_succeeded"] |= ok
                        result["graphical_overrides_write_succeeded"] |= ok
                        if not ok:
                            warning = "Projection-line graphical override API is unavailable."
                            diag["warnings"].append(warning); result["warnings"].append(warning)
                    except BaseException:
                        warning = "graphical_override failed; time-shadow curves were retained."
                        diag["warnings"].append(warning); result["warnings"].append(warning)
                except BaseException as exc:
                    if shape is not None:
                        try: document.Delete(shape.Id)
                        except BaseException: pass
                    code = str(exc) if str(exc).startswith("preview_") else "preview_group_creation_failed"
                    result["failure_reason_counts"][code] = result["failure_reason_counts"].get(code, 0) + 1; diag["warnings"].append(code)
                    result.update({"failure_stage":"direct_shape_create", "failure_code":code, "failure_type":type(exc).__name__, "sanitized_failure_message":_safe_message(exc)})
                for warning in diag["warnings"]:
                    if warning not in result["warnings"]: result["warnings"].append(warning)
                result["groups"].append(diag)
            if not result["created_element_ids"]:
                sub.RollBack(); sub = None; result["successful_delete_count"] = result["deleted_element_count"] = 0
                result["cleanup_delete_succeeded"] = False; result["warnings"].append("All Curve creation failed; old previews were retained by rollback.")
            else: sub.Commit(); sub = None; committed = True
    except BaseException as exc:
        if sub is not None:
            try: sub.RollBack(); result["successful_delete_count"] = result["deleted_element_count"] = 0
            except BaseException: pass
        if result["failure_stage"] is None:
            result.update({"failure_stage":"cleanup_delete", "failure_code":"preview_write_failed", "failure_type":type(exc).__name__, "sanitized_failure_message":_safe_message(exc)})
    finally:
        if started:
            result["transaction_close_attempted"] = True
            try: TransactionManager.Instance.TransactionTaskDone(); result["transaction_close_succeeded"] = True
            except BaseException as exc: result.update({"failure_stage":"transaction_close", "failure_code":"preview_transaction_close_failed", "failure_type":type(exc).__name__, "sanitized_failure_message":_safe_message(exc)})
    result["created_element_count"] = len(result["created_element_ids"]); result["failed_group_count"] = sum(result["failure_reason_counts"].values())
    readback = result["graphical_override_readback"]
    result["graphical_overrides_readback_succeeded"] = (readback["attempted_element_count"] > 0 and readback["readback_failure_count"] == 0)
    result["graphical_overrides_verified"] = (readback["attempted_element_count"] > 0 and readback["verified_element_count"] == readback["attempted_element_count"])
    result["available"] = result["transaction_close_succeeded"] and result["cleanup_delete_succeeded"] and (config["mode"] == "clear" or result["created_element_count"] > 0)
    result["complete"] = result["available"] and result["failed_group_count"] == 0
    result["partial_success"] = result["available"] and not result["complete"]
    return result


_build_shadow_preview = build_shadow_preview
