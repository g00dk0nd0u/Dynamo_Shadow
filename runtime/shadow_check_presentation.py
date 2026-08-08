"""Revit presentation adapter for a Forward Shadow regulatory review set.

The adapter only presents established calculation outputs.  DirectShape Curve
groups are used because Revit 2024.3 displays them in plan and 3D without
creating one persistent ModelCurve/SketchPlane per segment.  Dedicated views
receive deterministic per-element overrides; no legal judgement is inferred.
"""
import math

from shadow_contour_preview import normalize_equal_time_contour_preview_settings, _segments, _curves
from shadow_site_result_preview import _marker_curves
from shadow_preview import _collect_owned_preview_ids, _element_id, _safe_message, _set_plan_curve_representation
from shadow_units import _meters_to_internal_length
from shadow_revit_api import (BuiltInCategory, BuiltInParameter, ElementId, DirectShape, XYZ, Line,
    FilteredElementCollector, OverrideGraphicSettings, Color, SubTransaction,
    ViewPlan, View3D, ViewFamilyType, ViewFamily, View, Level, PlanViewPlane,
    BoundingBoxXYZ, ViewDetailLevel, DisplayStyle, ViewDiscipline)

try:
    from RevitServices.Persistence import DocumentManager
except Exception:
    DocumentManager = None
try:
    from RevitServices.Transactions import TransactionManager
except Exception:
    TransactionManager = None

APPLICATION_ID = "Dynamo_Shadow.ShadowCheckPresentation"
VIEW_OWNER_MARKER = "Dynamo_Shadow Shadow Check managed view"
STYLE_SEMANTICS = {
    "site_boundary": {"name": "Dynamo_Shadow_SiteBoundary", "rgb": (0, 0, 0), "weight": 7},
    "near_limit": {"name": "Dynamo_Shadow_NearLimit", "rgb": (220, 30, 30), "weight": 6},
    "near_contour": {"name": "Dynamo_Shadow_NearContour", "rgb": (220, 30, 30), "weight": 5},
    "near_marker": {"name": "Dynamo_Shadow_NearMarker", "rgb": (220, 30, 30), "weight": 8},
    "far_limit": {"name": "Dynamo_Shadow_FarLimit", "rgb": (30, 90, 220), "weight": 6},
    "far_contour": {"name": "Dynamo_Shadow_FarContour", "rgb": (30, 90, 220), "weight": 5},
    "far_marker": {"name": "Dynamo_Shadow_FarMarker", "rgb": (30, 90, 220), "weight": 8},
    "neutral_contour": {"name": "Dynamo_Shadow_NeutralContour", "rgb": (130, 130, 130), "weight": 2},
}


def classify_contour_level(level_minutes, resolved_preset, tolerance=1e-6):
    """Return style from near/far regulatory semantics, never time magnitude."""
    preset = resolved_preset if isinstance(resolved_preset, dict) else {}
    if preset.get("comparison_ready") is not True:
        return "neutral_contour"
    level = float(level_minutes)
    near, far = preset.get("near_limit_minutes"), preset.get("far_limit_minutes")
    if near is not None and abs(level - float(near)) <= tolerance:
        return "near_contour"
    if far is not None and abs(level - float(far)) <= tolerance:
        return "far_contour"
    return "neutral_contour"


def build_shadow_check_groups(site_geometry, distance_contours, equal_contours,
                              masks, resolved_preset):
    """Build a JSON-safe semantic presentation plan for testing and Revit use."""
    groups = []
    loop = (site_geometry or {}).get("outer_loop") or []
    if len(loop) >= 2:
        contour = {"closed": True, "points_m": [
            {"x": p.get("x_m"), "y": p.get("y_m")} for p in loop]}
        groups.append({"kind": "site_boundary", "style": "site_boundary", "contours": [contour]})
    for contour in (distance_contours or {}).get("contours") or []:
        distance = float(contour.get("distance_m"))
        if abs(distance - 5.0) <= 1e-6:
            groups.append({"kind": "site_distance_5m", "style": "near_limit", "contours": [contour]})
        elif abs(distance - 10.0) <= 1e-6:
            groups.append({"kind": "site_distance_10m", "style": "far_limit", "contours": [contour]})
    for contour in (equal_contours or {}).get("contours") or []:
        level = float(contour.get("level_minutes"))
        groups.append({"kind": "equal_time_contour", "level_minutes": level,
            "style": classify_contour_level(level, resolved_preset), "contours": [contour]})
    for key, style in (("near", "near_marker"), ("far", "far_marker")):
        item = (masks or {}).get(key) or {}
        if item.get("point") is not None and item.get("available") is not False:
            groups.append({"kind": "%s_maximum_marker" % key, "style": style,
                           "point": item["point"]})
    return groups


def _view_result(kind, elevation, height):
    return {"attempted": False, "available": False, "complete": False,
        "created": False, "reused": False, "view_id": None, "view_name": None,
        "view_type": kind, "measurement_plane_elevation_m": elevation,
        "measurement_height_m": height, "base_level_id": None,
        "base_level_name": None, "crop_or_section_box_applied": False,
        "blockers": [], "warnings": []}


def _owned_view(view):
    try:
        parameter = (view.get_Parameter(BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS)
                     if BuiltInParameter is not None else view.LookupParameter("Comments"))
        return parameter is not None and parameter.AsString() == VIEW_OWNER_MARKER
    except BaseException:
        return False


def _mark_view(view):
    try:
        parameter = (view.get_Parameter(BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS)
                     if BuiltInParameter is not None else view.LookupParameter("Comments"))
        if parameter is not None and not parameter.IsReadOnly:
            parameter.Set(VIEW_OWNER_MARKER)
            return True
    except BaseException:
        pass
    return False


def _collect(document, cls):
    return list(FilteredElementCollector(document).OfClass(cls).ToElements())


def _family_type(document, family):
    for item in _collect(document, ViewFamilyType):
        if item.ViewFamily == family:
            return item
    return None


def _base_level(document, elevation_internal):
    levels = _collect(document, Level)
    if not levels:
        return None
    below = [level for level in levels if float(level.Elevation) <= elevation_internal]
    return max(below, key=lambda x: float(x.Elevation)) if below else min(
        levels, key=lambda x: abs(float(x.Elevation) - elevation_internal))


def _unique_managed_name(document, desired):
    views = _collect(document, View)
    for view in views:
        if view.Name == desired and _owned_view(view):
            return desired, view
    occupied = {view.Name for view in views}
    candidate = desired if desired not in occupied else desired + "_Managed"
    index = 2
    while candidate in occupied:
        owned = next((v for v in views if v.Name == candidate and _owned_view(v)), None)
        if owned:
            return candidate, owned
        candidate = desired + "_Managed_%d" % index; index += 1
    return candidate, None


def _set_box(box, bounds, z0, z1, margin_m):
    margin, _ = _meters_to_internal_length(margin_m)
    xmin, ymin, xmax, ymax = bounds
    x0, _ = _meters_to_internal_length(xmin); y0, _ = _meters_to_internal_length(ymin)
    x1, _ = _meters_to_internal_length(xmax); y1, _ = _meters_to_internal_length(ymax)
    box.Min = XYZ(x0 - margin, y0 - margin, z0)
    box.Max = XYZ(x1 + margin, y1 + margin, z1)


def _bounds(groups):
    points = []
    for group in groups:
        for contour in group.get("contours") or []:
            for point in contour.get("points_m") or []:
                try: points.append((float(point.get("x", point.get("x_m"))), float(point.get("y", point.get("y_m")))))
                except (TypeError, ValueError): pass
        point = group.get("point") or {}
        if point:
            try: points.append((float(point["x_m"]), float(point["y_m"])))
            except (KeyError, TypeError, ValueError): pass
    return (min(p[0] for p in points), min(p[1] for p in points),
            max(p[0] for p in points), max(p[1] for p in points)) if points else None


def _prepare_views(document, measurement_plane, groups):
    elevation = float(measurement_plane["elevation_m"])
    height = measurement_plane.get("measurement_height_m")
    elevation_i, _ = _meters_to_internal_length(elevation)
    plan = _view_result("FloorPlan", elevation, height); three = _view_result("ThreeDimensional", elevation, height)
    plan["attempted"] = three["attempted"] = True
    level = _base_level(document, elevation_i)
    bounds = _bounds(groups)
    if level is None:
        plan["blockers"].append({"failure_code": "shadow_check_base_level_unavailable"})
    else:
        plan.update({"base_level_id": _element_id(level), "base_level_name": level.Name})
        name = "Dynamo_Shadow_ShadowCheck_%.1fm" % float(height)
        actual, view = _unique_managed_name(document, name)
        if view is None:
            typ = _family_type(document, ViewFamily.FloorPlan)
            if typ is None: plan["blockers"].append({"failure_code": "shadow_check_floor_plan_type_unavailable"})
            else:
                view = ViewPlan.Create(document, typ.Id, level.Id); view.Name = actual
                plan["created"] = True; _mark_view(view)
        else: plan["reused"] = True
        if view is not None:
            plan.update({"view_id": _element_id(view), "view_name": view.Name})
            try:
                view.DetailLevel = ViewDetailLevel.Fine; view.DisplayStyle = DisplayStyle.HiddenLine
                if ViewDiscipline is not None: view.Discipline = ViewDiscipline.Coordination
            except BaseException as exc: plan["warnings"].append(_safe_message(exc))
            try:
                vr = view.GetViewRange()
                offsets = {PlanViewPlane.BottomClipPlane: -0.5, PlanViewPlane.CutPlane: 0.1,
                           PlanViewPlane.TopClipPlane: 0.75, PlanViewPlane.ViewDepthPlane: -1.0}
                for plane, delta in offsets.items():
                    vr.SetLevelId(plane, level.Id)
                    absolute, _ = _meters_to_internal_length(elevation + delta)
                    vr.SetOffset(plane, absolute - float(level.Elevation))
                view.SetViewRange(vr)
            except BaseException as exc: plan["warnings"].append("View range: " + _safe_message(exc))
            if bounds and BoundingBoxXYZ is not None:
                try:
                    below, _ = _meters_to_internal_length(elevation - 0.5)
                    above, _ = _meters_to_internal_length(elevation + 1.0)
                    box = BoundingBoxXYZ(); _set_box(box, bounds, below, above, 7.5)
                    view.CropBox = box; view.CropBoxActive = True; view.CropBoxVisible = True
                    plan["crop_or_section_box_applied"] = True
                except BaseException as exc: plan["warnings"].append("Crop: " + _safe_message(exc))
            plan["available"] = plan["complete"] = not plan["blockers"]
    name, view = _unique_managed_name(document, "Dynamo_Shadow_ShadowCheck_3D")
    if view is None:
        typ = _family_type(document, ViewFamily.ThreeDimensional)
        if typ is None: three["blockers"].append({"failure_code": "shadow_check_3d_type_unavailable"})
        else:
            view = View3D.CreateIsometric(document, typ.Id); view.Name = name
            three["created"] = True; _mark_view(view)
    else: three["reused"] = True
    if view is not None:
        three.update({"view_id": _element_id(view), "view_name": view.Name})
        if bounds and BoundingBoxXYZ is not None:
            try:
                box = BoundingBoxXYZ(); below, _ = _meters_to_internal_length(elevation - 5.0); above, _ = _meters_to_internal_length(elevation + 20.0)
                _set_box(box, bounds, below, above, 7.5); view.SetSectionBox(box); view.IsSectionBoxActive = True
                three["crop_or_section_box_applied"] = True
            except BaseException as exc: three["warnings"].append("Section box: " + _safe_message(exc))
        three["available"] = three["complete"] = not three["blockers"]
    return {"plan": plan, "three_d": three}, {"plan": locals().get("view")}


def _override(view, element_id, style):
    if view is None or OverrideGraphicSettings is None or Color is None: return False
    spec = STYLE_SEMANTICS[style]; settings = OverrideGraphicSettings()
    settings.SetProjectionLineColor(Color(*spec["rgb"])); settings.SetProjectionLineWeight(spec["weight"])
    view.SetElementOverrides(element_id, settings); return True


def build_shadow_check_presentation(site_geometry, distance_contours, equal_contours,
                                    masks, resolved_preset, measurement_plane, settings):
    config = normalize_equal_time_contour_preview_settings(settings)
    elevation = (measurement_plane or {}).get("elevation_m")
    result = {"enabled": config["mode"] != "off", "mode": config["mode"], "attempted": False,
        "available": False, "complete": False, "created_element_count": 0,
        "deleted_element_count": 0, "created_element_ids": [], "groups": [],
        "style_semantics": STYLE_SEMANTICS, "measurement_plane_elevation_m": elevation,
        "blockers": [], "warnings": list(config["warnings"]), "legal_judgement_generated": False,
        "ordinance_selection_certified": False, "permit_ready_certified": False}
    views = {"plan": _view_result("FloorPlan", elevation, (measurement_plane or {}).get("measurement_height_m")),
             "three_d": _view_result("ThreeDimensional", elevation, (measurement_plane or {}).get("measurement_height_m"))}
    if config["mode"] == "off": return result, views
    result["attempted"] = True
    groups = build_shadow_check_groups(site_geometry, distance_contours, equal_contours, masks, resolved_preset) if config["mode"] == "replace" else []
    required = (DocumentManager, TransactionManager, DirectShape, FilteredElementCollector, SubTransaction, XYZ, Line)
    if any(item is None for item in required):
        result["warnings"].append("Revit Shadow Check presentation API is unavailable; presentation skipped.")
        return result, views
    view_required = (ViewPlan, View3D, ViewFamilyType, ViewFamily, View, Level,
                     PlanViewPlane, BoundingBoxXYZ)
    if config["mode"] == "replace" and any(item is None for item in view_required):
        result["blockers"].append({"failure_code": "shadow_check_view_api_unavailable"})
        result["warnings"].append("Revit 2024.3 Shadow Check view API is unavailable; presentation skipped.")
        return result, views
    document = DocumentManager.Instance.CurrentDBDocument
    cleanup = _collect_owned_preview_ids(document, APPLICATION_ID)
    if not cleanup.get("succeeded"):
        result["blockers"].append({"failure_code": "shadow_check_cleanup_collection_failed"}); return result, views
    started = False; sub = None
    try:
        TransactionManager.Instance.EnsureInTransaction(document); started = True
        sub = SubTransaction(document); sub.Start()
        for ident in cleanup["element_ids"]: document.Delete(ident); result["deleted_element_count"] += 1
        view_objects = []
        if config["mode"] == "replace":
            views, _ = _prepare_views(document, measurement_plane, groups)
            ids = {views[k].get("view_id") for k in views}
            view_objects = [v for v in _collect(document, View) if _element_id(v) in ids]
            tolerance = float(getattr(document.Application, "ShortCurveTolerance", 0.0))
            for index, group in enumerate(groups):
                curves = (_marker_curves(group["point"], elevation, tolerance) if group.get("point") is not None
                          else _curves(_segments(group.get("contours") or []), elevation, tolerance))
                if not curves: continue
                shape = DirectShape.CreateElement(document, ElementId(BuiltInCategory.OST_GenericModel)); shape.SetShape(curves)
                diag = {"warnings": []}; _set_plan_curve_representation(shape, curves, diag); result["warnings"].extend(diag["warnings"])
                shape.Name = STYLE_SEMANTICS[group["style"]]["name"]; shape.ApplicationId = APPLICATION_ID
                shape.ApplicationDataId = "kind=%s;index=%d" % (group["kind"], index)
                for view in view_objects: _override(view, shape.Id, group["style"])
                ident = _element_id(shape); result["created_element_ids"].append(ident)
                result["groups"].append({k: v for k, v in group.items() if k not in ("contours", "point")})
        sub.Commit(); sub = None
    except BaseException as exc:
        if sub is not None:
            try: sub.RollBack(); result["deleted_element_count"] = 0
            except BaseException: pass
        result["blockers"].append({"failure_code": "shadow_check_write_failed"}); result["warnings"].append(_safe_message(exc))
    finally:
        if started:
            try: TransactionManager.Instance.TransactionTaskDone()
            except BaseException as exc: result["warnings"].append(_safe_message(exc))
    result["created_element_count"] = len(result["created_element_ids"])
    result["available"] = not result["blockers"]
    result["complete"] = result["available"] and (config["mode"] == "clear" or result["created_element_count"] == len(groups))
    return result, views
