"""Opt-in, downstream Revit DirectShape preview for formal shadow polygons.

Nothing in this module is consumed by the formal calculation.  All returned
values are JSON-safe diagnostics; native objects remain local to this adapter.
"""
import math

import shadow_utils
from shadow_policies import SETTINGS_DIAGNOSTIC_DEFAULTS
from shadow_units import _meters_to_internal_length
from shadow_revit_api import (BuiltInCategory, ElementId, CurveLoop, XYZ, Line,
    DirectShape, GeometryCreationUtilities, FilteredElementCollector,
    FillPatternElement, OverrideGraphicSettings, Color)

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
STYLES = ((40, 120, 255), (255, 190, 0), (240, 70, 70))


def _checkpoint(stage, detail=None):
    callback = getattr(shadow_utils, "RUNTIME_CHECKPOINT", None)
    if callback is not None:
        try: callback(stage, detail)
        except BaseException: pass


def _canonical_time(value):
    if not isinstance(value, str): return None
    parts = value.strip().split(":")
    if len(parts) not in (2, 3): return None
    try: nums = [int(p) for p in parts]
    except Exception: return None
    if len(nums) == 2: nums.append(0)
    if not (0 <= nums[0] <= 23 and 0 <= nums[1] <= 59 and 0 <= nums[2] <= 59): return None
    return "%02d:%02d:%02d" % tuple(nums)


def normalize_preview_settings(settings):
    """Return isolated preview settings; any invalid value disables preview."""
    source = (settings or {}).get("normalized") if isinstance(settings, dict) else None
    source = source if isinstance(source, dict) else (settings if isinstance(settings, dict) else {})
    defaults = SETTINGS_DIAGNOSTIC_DEFAULTS
    warnings = []; valid = True
    mode = source.get("preview_mode", defaults["preview_mode"])
    if mode not in ("off", "replace", "clear"):
        warnings.append("settings.preview_mode must be off, replace, or clear; preview disabled."); valid = False
    raw_times = source.get("preview_true_solar_times", defaults["preview_true_solar_times"])
    if not isinstance(raw_times, (list, tuple)):
        warnings.append("settings.preview_true_solar_times must be a list of strings; preview disabled."); raw_times = []; valid = False
    times = []
    for value in raw_times:
        canonical = _canonical_time(value)
        if canonical is None:
            warnings.append("Each requested preview time must be a valid HH:MM or HH:MM:SS string; preview disabled."); valid = False; continue
        if canonical not in times: times.append(canonical)
    def number(key, positive):
        nonlocal valid
        value = source.get(key, defaults[key])
        try: value = float(value)
        except Exception: value = float("nan")
        if not math.isfinite(value) or (value <= 0 if positive else value < 0):
            warnings.append("settings.%s is outside the preview range; preview disabled." % key); valid = False
        return value if math.isfinite(value) else defaults[key]
    thickness = number("preview_thickness_mm", True)
    separation = number("preview_vertical_separation_mm", False)
    transparency = source.get("preview_transparency", defaults["preview_transparency"])
    if isinstance(transparency, bool) or not isinstance(transparency, int) or not 0 <= transparency <= 100:
        warnings.append("settings.preview_transparency must be an integer from 0 through 100; preview disabled."); valid = False
        transparency = defaults["preview_transparency"]
    return {"valid": valid, "mode": mode if valid else "off", "requested_true_solar_times": times,
            "preview_thickness_mm": thickness, "preview_vertical_separation_mm": separation,
            "preview_transparency": transparency, "warnings": warnings}


def _empty(config, formal, elevation):
    mode = config["mode"]
    return {"enabled": mode != "off", "mode": mode, "attempted": False, "available": False,
        "complete": False, "partial_success": False,
        "formal_shadow_source_available": bool((formal or {}).get("available")),
        "requested_true_solar_times": list(config["requested_true_solar_times"]),
        "matched_true_solar_times": [], "deleted_element_count": 0, "created_element_count": 0,
        "created_element_ids": [], "failed_group_count": 0,
        "measurement_plane_elevation_m": elevation,
        "preview_thickness_mm": config["preview_thickness_mm"],
        "preview_vertical_separation_mm": config["preview_vertical_separation_mm"],
        "active_view_id": None, "active_view_type": None,
        "graphical_overrides_attempted": False, "graphical_overrides_succeeded": False,
        "groups": [], "failure_reason_counts": {}, "warnings": list(config["warnings"])}


def _element_id(value):
    ident = getattr(value, "Id", value)
    for name in ("Value", "IntegerValue"):
        try: return int(getattr(ident, name))
        except BaseException: pass
    try: return int(ident)
    except BaseException: return None


def _owned_ids(document):
    collector = FilteredElementCollector(document).OfClass(DirectShape)
    result = []
    for element in collector:
        try:
            if element.ApplicationId == APPLICATION_ID: result.append(element.Id)
        except BaseException: pass
    return result


def _selected_groups(formal, requested, warnings):
    by_time = {}
    for item in (formal or {}).get("slices") or []:
        key = _canonical_time(item.get("true_solar_time"))
        if key is not None: by_time[key] = item
    groups = []; matched = []
    for order, key in enumerate(requested):
        item = by_time.get(key)
        if item is None:
            warnings.append("Requested preview true solar time %s was not found; no nearest slice was selected." % key); continue
        matched.append(key)
        for caster in item.get("casters") or []:
            buckets = {}
            for polygon in caster.get("polygons") or []:
                group_key = (polygon.get("source_solid_index"), polygon.get("split_solid_index"))
                buckets.setdefault(group_key, []).append(polygon)
            for (source_index, split_index), polygons in sorted(buckets.items(), key=lambda pair: str(pair[0])):
                groups.append({"slice_index": item.get("slice_index"), "true_solar_time": key,
                    "caster_index": caster.get("caster_index"), "source_solid_index": source_index,
                    "split_solid_index": split_index, "polygons": polygons, "style_index": order})
    return groups, matched


def _curve_loops(polygons, elevation_m, z_offset_mm, short_tolerance):
    ordered = sorted(polygons, key=lambda p: 0 if p.get("role") == "outer" else 1)
    if not ordered or ordered[0].get("role") != "outer": raise ValueError("preview_missing_outer_loop")
    loops = []
    z, _ = _meters_to_internal_length(elevation_m + z_offset_mm / 1000.0)
    try:
        for polygon in ordered:
            points = polygon.get("points_m") or []
            if (polygon.get("generation_method") != GENERATION_METHOD or polygon.get("closed") is not True or
                    polygon.get("role") not in ("outer", "inner") or len(points) < 3 or
                    polygon.get("point_count") != len(points) or not float(polygon.get("area_m2", 0)) > 0):
                raise ValueError("preview_polygon_validation_failed")
            native = []
            for point in points:
                x = float(point.get("x")); y = float(point.get("y"))
                if not math.isfinite(x) or not math.isfinite(y): raise ValueError("preview_non_finite_coordinate")
                xi, _ = _meters_to_internal_length(x); yi, _ = _meters_to_internal_length(y)
                native.append(XYZ(xi, yi, z))
            loop = CurveLoop()
            loops.append(loop)
            for index, start in enumerate(native):
                end = native[(index + 1) % len(native)]
                try: length = float(start.DistanceTo(end))
                except BaseException: length = math.sqrt(sum((float(getattr(start, a))-float(getattr(end, a)))**2 for a in ("X","Y","Z")))
                if length <= max(0.0, short_tolerance): raise ValueError("preview_short_segment")
                loop.Append(Line.CreateBound(start, end))
        return loops
    except BaseException:
        _dispose_loops(loops); raise


def _dispose_loops(loops):
    for loop in loops:
        try: loop.Dispose()
        except BaseException: pass


def _solid_fill_id(document):
    for pattern in FilteredElementCollector(document).OfClass(FillPatternElement):
        try:
            if pattern.GetFillPattern().IsSolidFill: return pattern.Id
        except BaseException: pass
    return None


def _apply_override(document, view, element_id, style_index, transparency):
    if view is None or OverrideGraphicSettings is None or Color is None: return False, "Active view does not support preview overrides."
    fill_id = _solid_fill_id(document)
    if fill_id is None: return False, "No API IsSolidFill pattern was available; DirectShape was retained."
    rgb = STYLES[style_index % len(STYLES)]; color = Color(*rgb); override = OverrideGraphicSettings()
    override.SetProjectionLineColor(color); override.SetProjectionLineWeight(4)
    override.SetSurfaceForegroundPatternId(fill_id); override.SetSurfaceForegroundPatternColor(color)
    override.SetSurfaceTransparency(transparency); view.SetElementOverrides(element_id, override)
    return True, None


def build_shadow_preview(formal_shadow_polygons, measurement_plane, settings):
    config = normalize_preview_settings(settings); elevation = (measurement_plane or {}).get("elevation_m")
    result = _empty(config, formal_shadow_polygons, elevation); _checkpoint("SHADOW_PREVIEW_BEGIN", "mode=" + config["mode"])
    if config["mode"] == "off": _checkpoint("SHADOW_PREVIEW_END", "ok"); return result
    result["attempted"] = True
    if DocumentManager is None or TransactionManager is None or any(x is None for x in (DirectShape, GeometryCreationUtilities, CurveLoop, XYZ, Line, FilteredElementCollector)):
        result["warnings"].append("Revit DocumentManager, TransactionManager, or preview API is unavailable; preview skipped.")
        _checkpoint("SHADOW_PREVIEW_END", "failure"); return result
    try: document = DocumentManager.Instance.CurrentDBDocument; view = document.ActiveView
    except BaseException:
        result["warnings"].append("Current Revit document or active view is unavailable; preview skipped."); _checkpoint("SHADOW_PREVIEW_END", "failure"); return result
    result["active_view_id"] = _element_id(view)
    try: result["active_view_type"] = str(view.ViewType)
    except BaseException: result["active_view_type"] = None
    groups, matched = _selected_groups(formal_shadow_polygons, config["requested_true_solar_times"], result["warnings"])
    result["matched_true_solar_times"] = matched
    transaction_open = False
    try:
        TransactionManager.Instance.EnsureInTransaction(document); transaction_open = True
        _checkpoint("SHADOW_PREVIEW_CLEANUP_BEFORE", "mode=" + config["mode"])
        owned = _owned_ids(document)
        if owned: document.Delete(owned)
        result["deleted_element_count"] = len(owned); _checkpoint("SHADOW_PREVIEW_CLEANUP_AFTER", "deleted count=%d" % len(owned))
        if config["mode"] == "replace":
            thickness, _ = _meters_to_internal_length(config["preview_thickness_mm"] / 1000.0)
            short_tol = 0.0
            try: short_tol = float(document.Application.ShortCurveTolerance)
            except BaseException: pass
            for group in groups:
                detail = "slice_index={0},caster_index={1},split_solid_index={2}".format(group["slice_index"], group["caster_index"], group["split_solid_index"])
                diagnostic = {k: group[k] for k in ("slice_index","true_solar_time","caster_index","source_solid_index","split_solid_index","style_index")}
                diagnostic.update({"outer_loop_count":sum(p.get("role")=="outer" for p in group["polygons"]), "inner_loop_count":sum(p.get("role")=="inner" for p in group["polygons"]), "direct_shape_created":False, "element_id":None, "z_offset_mm":group["style_index"]*config["preview_vertical_separation_mm"], "warnings":[]})
                loops = []
                try:
                    _checkpoint("SHADOW_PREVIEW_GROUP_BEFORE", detail)
                    loops = _curve_loops(group["polygons"], elevation, diagnostic["z_offset_mm"], short_tol); _checkpoint("SHADOW_PREVIEW_CURVELOOPS_AFTER", detail+",ok")
                    solid = GeometryCreationUtilities.CreateExtrusionGeometry(loops, XYZ.BasisZ, thickness)
                    if solid is None: raise RuntimeError("preview_extrusion_creation_failed")
                    try:
                        if float(solid.Volume) <= 0: raise RuntimeError("preview_extrusion_creation_failed")
                    except AttributeError: pass
                    _checkpoint("SHADOW_PREVIEW_EXTRUSION_AFTER", detail+",ok")
                    shape = DirectShape.CreateElement(document, ElementId(BuiltInCategory.OST_GenericModel))
                    shape.ApplicationId = APPLICATION_ID
                    shape.ApplicationDataId = "slice={0};caster={1};solid={2}".format(group["slice_index"],group["caster_index"],group["split_solid_index"])
                    shape.Name = "Dynamo_Shadow Preview " + group["true_solar_time"]
                    shape.SetShape([solid]); diagnostic["element_id"] = _element_id(shape); diagnostic["direct_shape_created"] = True
                    result["created_element_ids"].append(diagnostic["element_id"]); _checkpoint("SHADOW_PREVIEW_DIRECTSHAPE_AFTER", detail+",ok")
                    result["graphical_overrides_attempted"] = True
                    try:
                        ok, warning = _apply_override(document, view, shape.Id, group["style_index"], config["preview_transparency"])
                        result["graphical_overrides_succeeded"] = result["graphical_overrides_succeeded"] or ok
                        if warning: diagnostic["warnings"].append(warning); result["warnings"].append(warning)
                    except BaseException:
                        diagnostic["warnings"].append("Active-view graphical override failed; DirectShape was retained."); result["warnings"].append(diagnostic["warnings"][-1])
                    _checkpoint("SHADOW_PREVIEW_OVERRIDE_AFTER", detail+",ok")
                    _checkpoint("SHADOW_PREVIEW_GROUP_AFTER", detail+",ok")
                except BaseException as exc:
                    reason = "preview_extrusion_creation_failed" if "extrusion" in str(exc).lower() else str(exc)
                    if not reason.startswith("preview_"): reason = "preview_group_creation_failed"
                    result["failure_reason_counts"][reason] = result["failure_reason_counts"].get(reason, 0) + 1
                    diagnostic["warnings"].append(reason); _checkpoint("SHADOW_PREVIEW_GROUP_AFTER", detail+",failure")
                finally: _dispose_loops(loops)
                result["groups"].append(diagnostic)
        result["created_element_count"] = len(result["created_element_ids"])
    except BaseException:
        result["warnings"].append("Preview transaction failed; formal shadow output remains unchanged.")
    finally:
        if transaction_open:
            try: TransactionManager.Instance.TransactionTaskDone()
            except BaseException: result["warnings"].append("Preview transaction could not be closed normally.")
        _checkpoint("SHADOW_PREVIEW_TRANSACTION_AFTER", "created count=%d,deleted count=%d" % (result["created_element_count"], result["deleted_element_count"]))
    result["failed_group_count"] = sum(result["failure_reason_counts"].values())
    result["available"] = config["mode"] == "clear" or result["created_element_count"] > 0
    result["complete"] = result["available"] and result["failed_group_count"] == 0
    result["partial_success"] = result["available"] and not result["complete"]
    _checkpoint("SHADOW_PREVIEW_END", "ok" if result["available"] else "failure")
    return result


_build_shadow_preview = build_shadow_preview
