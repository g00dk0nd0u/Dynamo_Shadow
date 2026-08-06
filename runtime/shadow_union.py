"""Revit-native, per-time-slice union of exact formal shadow Line loops.

The extrusion is an in-memory planar Boolean adapter.  This module neither
opens a transaction nor creates a document element, and it has no polygon
clipping fallback.  All native objects remain runtime-only.
"""
import math

from shadow_revit_api import (REVIT_API_CAPABILITIES, BooleanOperationsUtils,
    BooleanOperationsType, GeometryCreationUtilities, SolidUtils, CurveLoop,
    Line, XYZ, PlanarFace)
from shadow_units import _meters_to_internal_length, _internal_length_to_meters
from shadow_utils import _runtime_checkpoint

ENGINE = "revit_boolean_solid_union_v1"
UNION_ADAPTER_THICKNESS_M = 0.1
GENERATION_METHOD = "revit_extrusion_analyzer_curve_loop_line_exact"


def _checkpoint(stage, slice_index=None, **values):
    parts = []
    if slice_index is not None:
        parts.append("slice_index={0}".format(slice_index))
    for key in sorted(values):
        parts.append("{0}={1}".format(key, values[key]))
    _runtime_checkpoint(stage, ",".join(parts) if parts else None)


def _dispose_unique(values, disposed=None):
    disposed = disposed if disposed is not None else set()
    for value in values or []:
        identity = id(value)
        if value is None or identity in disposed:
            continue
        disposed.add(identity)
        method = getattr(value, "Dispose", None)
        if callable(method):
            try:
                method()
            except BaseException:
                pass
    return disposed


def _signed_area(points):
    return 0.5 * sum(points[i][0] * points[(i + 1) % len(points)][1]
                     - points[(i + 1) % len(points)][0] * points[i][1]
                     for i in range(len(points)))


def _xy(p):
    return float(p["x"]), float(p["y"])


def _valid_polygon(polygon):
    reasons = []
    if polygon.get("generation_method") != GENERATION_METHOD:
        reasons.append("unsupported_formal_polygon_generation_method")
    if polygon.get("closed") is not True:
        reasons.append("formal_polygon_not_closed")
    if polygon.get("role") not in ("outer", "inner"):
        reasons.append("formal_polygon_role_invalid")
    try:
        points = [_xy(p) for p in polygon.get("points_m") or []]
        if not all(math.isfinite(v) for point in points for v in point):
            reasons.append("formal_polygon_non_finite_coordinate")
        if len(set(points)) < 3:
            reasons.append("formal_polygon_insufficient_unique_points")
        if abs(_signed_area(points)) <= 0.0:
            reasons.append("formal_polygon_non_positive_absolute_area")
        for key in ("caster_index", "source_solid_index", "split_solid_index"):
            if int(polygon.get(key)) < 0:
                reasons.append("formal_polygon_invalid_" + key)
    except (KeyError, TypeError, ValueError, OverflowError):
        reasons.append("formal_polygon_contract_invalid")
    return sorted(set(reasons))


def _flatten(formal):
    records = []
    for slice_item in (formal or {}).get("slices") or []:
        try:
            slice_index = int(slice_item.get("slice_index"))
        except (TypeError, ValueError):
            slice_index = -1
        for caster in slice_item.get("casters") or []:
            for polygon in caster.get("polygons") or []:
                item = dict(polygon)
                item["slice_index"] = slice_index
                item["caster_index"] = caster.get("caster_index", item.get("caster_index"))
                item["true_solar_time"] = slice_item.get("true_solar_time")
                records.append(item)
    return records


def _group_slice(polygons):
    """One outer and its same-native-face inner loops form one adapter Solid."""
    outers = [p for p in polygons if p.get("role") == "outer"]
    inners = [p for p in polygons if p.get("role") == "inner"]
    groups = []
    for outer in outers:
        key = tuple(outer.get(k) for k in ("caster_index", "source_solid_index", "split_solid_index"))
        outer_index = int(outer.get("polygon_index", 0))
        group_inners = [p for p in inners if tuple(p.get(k) for k in key_names()) == key
                        and _contains(outer.get("points_m") or [], (p.get("points_m") or [{}])[0])]
        groups.append({"key": key + (outer_index,), "outer": outer, "inners": group_inners})
    return sorted(groups, key=lambda g: g["key"])


def key_names():
    return ("caster_index", "source_solid_index", "split_solid_index")


def _contains(points, point):
    try:
        x, y = _xy(point); xy = [_xy(p) for p in points]
    except (KeyError, TypeError, ValueError):
        return False
    inside = False
    for i, (x1, y1) in enumerate(xy):
        x2, y2 = xy[(i + 1) % len(xy)]
        if (y1 > y) != (y2 > y) and x < (x2-x1)*(y-y1)/(y2-y1)+x1:
            inside = not inside
    return inside


def _new_loop(polygon, elevation_internal, short_tolerance):
    loop = CurveLoop()
    points = polygon["points_m"]
    for index, point in enumerate(points):
        following = points[(index + 1) % len(points)]
        x1, _ = _meters_to_internal_length(point["x"]); y1, _ = _meters_to_internal_length(point["y"])
        x2, _ = _meters_to_internal_length(following["x"]); y2, _ = _meters_to_internal_length(following["y"])
        a, b = XYZ(x1, y1, elevation_internal), XYZ(x2, y2, elevation_internal)
        length = math.sqrt((x2-x1)**2 + (y2-y1)**2)
        if length <= short_tolerance:
            raise ValueError("adapter_short_curve")
        loop.Append(Line.CreateBound(a, b))
    return loop


def _create_adapter(group, elevation_internal, thickness_internal, short_tolerance, slice_index):
    loops = []
    _checkpoint("FORMAL_UNION_ADAPTER_BEFORE", slice_index, component_count=1)
    try:
        loops.append(_new_loop(group["outer"], elevation_internal, short_tolerance))
        loops.extend(_new_loop(p, elevation_internal, short_tolerance) for p in group["inners"])
        solid = GeometryCreationUtilities.CreateExtrusionGeometry(loops, XYZ.BasisZ, thickness_internal)
        if solid is None or float(getattr(solid, "Volume", 0.0)) <= 0.0:
            raise ValueError("adapter_solid_invalid")
        _checkpoint("FORMAL_UNION_ADAPTER_AFTER", slice_index, success=True)
        return solid
    finally:
        _dispose_unique(loops)


def _split(solid, slice_index):
    values = list(SolidUtils.SplitVolumes(solid))
    if not values or any(float(getattr(value, "Volume", 0.0)) <= 0.0 for value in values):
        raise ValueError("split_volume_invalid")
    _checkpoint("FORMAL_UNION_SPLIT_AFTER", slice_index, component_count=len(values), success=True)
    return values


def _union_pair(a, b, slice_index, stats):
    successes = []
    errors = []
    for left, right, retry in ((a, b, False), (b, a, True)):
        stats["attempts"] += 1
        if retry:
            stats["retries"] += 1
        _checkpoint("FORMAL_UNION_BOOLEAN_BEFORE", slice_index, operation_attempt_count=stats["attempts"])
        try:
            solid = BooleanOperationsUtils.ExecuteBooleanOperation(left, right, BooleanOperationsType.Union)
            parts = _split(solid, slice_index)
            stats["successes"] += 1
            successes.append((solid, parts))
            _checkpoint("FORMAL_UNION_BOOLEAN_AFTER", slice_index, component_count=len(parts), success=True)
            if not retry:
                break
        except BaseException as exc:
            errors.append(type(exc).__name__); stats["failures"] += 1
            _checkpoint("FORMAL_UNION_BOOLEAN_AFTER", slice_index, success=False, exception_type=type(exc).__name__)
    if not successes:
        raise RuntimeError("revit_boolean_union_failed")
    return successes[0]


def _normal_z(face):
    normal = getattr(face, "FaceNormal", None) or getattr(face, "Normal", None)
    if normal is None and hasattr(face, "ComputeNormal"):
        try: normal = face.ComputeNormal(None)
        except BaseException: normal = None
    return float(getattr(normal, "Z", 0.0)) if normal is not None else 0.0


def _face_elevation(face):
    origin = getattr(face, "Origin", None)
    return float(getattr(origin, "Z", float("inf")))


def _serialize_component(solid, elevation_internal, settings, slice_index, component_index):
    faces = [f for f in list(getattr(solid, "Faces", []))
             if (PlanarFace is None or isinstance(f, PlanarFace)) and abs(abs(_normal_z(f))-1.0) <= 1e-7]
    if not faces:
        raise ValueError("union_base_planar_face_unavailable")
    face = min(faces, key=lambda f: (abs(_face_elevation(f)-elevation_internal), _face_elevation(f)))
    _checkpoint("FORMAL_UNION_FACE_AFTER", slice_index, success=True)
    loops = list(face.GetEdgesAsCurveLoops())
    try:
        polygons = []
        for loop_index, loop in enumerate(loops):
            points = []
            for curve in list(loop):
                if type(curve).__name__ != "Line" and not type(curve).__name__.endswith("Line"):
                    raise ValueError("union_output_non_line_loop")
                p = curve.GetEndPoint(0)
                x, _ = _internal_length_to_meters(p.X); y, _ = _internal_length_to_meters(p.Y)
                points.append({"x": x, "y": y})
            if len(set((p["x"], p["y"]) for p in points)) < 3:
                raise ValueError("union_output_loop_invalid")
            area = _signed_area([_xy(p) for p in points])
            role = "outer" if area > 0 else "inner"
            desired_positive = role == "outer"
            # Base faces may reverse all loops; classify the largest loop outer below.
            polygons.append({"points_m": points, "signed": area, "source_loop_index": loop_index})
        if not polygons:
            raise ValueError("union_output_has_no_loops")
        largest = max(range(len(polygons)), key=lambda i: abs(polygons[i]["signed"]))
        for index, item in enumerate(polygons):
            role = "outer" if index == largest else ("inner" if _contains(polygons[largest]["points_m"], item["points_m"][0]) else "outer")
            desired = 1 if role == "outer" else -1
            if item["signed"] * desired < 0:
                item["points_m"].reverse(); item["signed"] *= -1
            item.update({"polygon_index": index, "component_index": component_index, "role": role,
                         "orientation": "ccw" if role == "outer" else "cw", "closed": True,
                         "point_count": len(item["points_m"]), "area_m2": abs(item["signed"]),
                         "generation_method": "revit_boolean_union_curve_loop_line_exact"})
            del item["signed"]
        _checkpoint("FORMAL_UNION_CURVELOOPS_AFTER", slice_index, component_count=1, success=True)
        return polygons
    finally:
        _dispose_unique(loops)


def _empty(formal):
    return {"engine": ENGINE, "available": False, "complete": False, "partial_success": False,
            "time_slice_count": len((formal or {}).get("slices") or []), "successful_slice_count": 0,
            "failed_slice_count": 0, "input_polygon_count": 0, "output_polygon_count": 0,
            "input_component_count": 0, "output_component_count": 0,
            "boolean_operation_attempt_count": 0, "boolean_operation_success_count": 0,
            "boolean_operation_failure_count": 0, "adapter_thickness_m": UNION_ADAPTER_THICKNESS_M,
            "ready_for_duration_accumulation": False, "failure_reason_counts": {}, "slices": [],
            "blockers": [], "warnings": []}


def _build_unified_shadow_slices(formal_shadow_polygons, measurement_plane, settings):
    result = _empty(formal_shadow_polygons); _checkpoint("FORMAL_UNION_BEGIN")
    if not REVIT_API_CAPABILITIES.get("formal_shadow_union_api_available"):
        result["blockers"].append({"failure_code": "formal_shadow_union_api_unavailable"})
        _checkpoint("FORMAL_UNION_END", success=False); return result
    records = _flatten(formal_shadow_polygons)
    normalized = (settings or {}).get("normalized") or settings or {}
    elevation, _ = _meters_to_internal_length((measurement_plane or {}).get("elevation_m"))
    thickness, _ = _meters_to_internal_length(UNION_ADAPTER_THICKNESS_M)
    short_tol = float(normalized.get("short_curve_tolerance_internal", 0.0) or 0.0)
    closure = float(normalized.get("closure_tolerance_m", 0.01) or 0.01)
    area_tolerance = max(1e-9, closure * closure)
    disposed = set()
    indices = sorted(set(p.get("slice_index") for p in records))
    for slice_index in indices:
        polygons = [p for p in records if p.get("slice_index") == slice_index]
        _checkpoint("FORMAL_UNION_SLICE_BEFORE", slice_index, input_group_count=len(polygons))
        stats = {"attempts": 0, "successes": 0, "failures": 0, "retries": 0}
        blockers = []
        invalid = [(p.get("polygon_index"), _valid_polygon(p)) for p in polygons if _valid_polygon(p)]
        groups = _group_slice(polygons) if not invalid else []
        components = []; all_native = []
        try:
            if invalid: raise ValueError("invalid_formal_polygon")
            for group in groups:
                solid = _create_adapter(group, elevation, thickness, short_tol, slice_index)
                all_native.append(solid); components.append(solid)
                changed = True
                while changed:
                    changed = False
                    for i in range(len(components)):
                        for j in range(i + 1, len(components)):
                            merged, parts = _union_pair(components[i], components[j], slice_index, stats)
                            all_native.extend([merged] + parts)
                            if len(parts) < 2:
                                components = components[:i] + parts + components[i+1:j] + components[j+1:]
                                changed = True
                            break
                        if changed: break
            final_parts = []
            for component in components: final_parts.extend(_split(component, slice_index))
            all_native.extend(final_parts)
            output = []
            for component_index, component in enumerate(final_parts):
                output.extend(_serialize_component(component, elevation, normalized, slice_index, component_index))
            input_area = sum(float(p.get("area_m2", 0.0)) * (-1 if p.get("role") == "inner" else 1) for p in polygons)
            unified_area = sum(p["area_m2"] * (-1 if p["role"] == "inner" else 1) for p in output)
            largest = max([sum(float(g["outer"].get("area_m2", 0.0)) for _ in [0]) - sum(float(p.get("area_m2", 0.0)) for p in g["inners"]) for g in groups] or [0.0])
            if unified_area <= 0 or unified_area > input_area + area_tolerance or unified_area < largest - area_tolerance:
                raise ValueError("union_area_validation_failed")
            slice_out = {"slice_index": slice_index, "true_solar_time": polygons[0].get("true_solar_time") if polygons else None,
                "complete": True, "input_caster_count": len(set(p["caster_index"] for p in polygons)),
                "input_group_count": len(groups), "input_polygon_count": len(polygons),
                "output_component_count": len(final_parts), "output_polygon_count": len(output),
                "outer_loop_count": sum(p["role"] == "outer" for p in output), "inner_loop_count": sum(p["role"] == "inner" for p in output),
                "input_area_m2_sum": input_area, "unified_area_m2": unified_area,
                "overlap_removed_area_m2": input_area-unified_area, "area_balance_error_m2": max(0.0, unified_area-input_area),
                "source_caster_indices": sorted(set(p["caster_index"] for p in polygons)),
                "boolean_operation_attempt_count": stats["attempts"], "boolean_operation_success_count": stats["successes"],
                "boolean_operation_failure_count": stats["failures"], "retry_count": stats["retries"],
                "polygons": output, "blockers": [], "warnings": []}
            source_slice = next((item for item in (formal_shadow_polygons or {}).get("slices") or [] if item.get("slice_index") == slice_index), {})
            for key in ("solar_azimuth_deg", "shadow_azimuth_true_north_deg", "shadow_azimuth_model_deg",
                        "physical_shadow_ray_model", "extrusion_analyzer_input_direction", "expected_shadow_quadrant",
                        "actual_polygon_direction_check", "direction_validation_passed", "direction_validation_reason",
                        "pure_python_verified", "revit_runtime_direction_verified"):
                slice_out[key] = source_slice.get(key)
        except BaseException as exc:
            code = str(exc) if str(exc) in ("revit_boolean_union_failed", "invalid_formal_polygon", "union_area_validation_failed") else "formal_shadow_union_slice_failed"
            blockers = [{"failure_code": code, "failure_type": type(exc).__name__}]
            slice_out = {"slice_index": slice_index, "true_solar_time": polygons[0].get("true_solar_time") if polygons else None,
                "complete": False, "input_caster_count": len(set(p.get("caster_index") for p in polygons)), "input_group_count": len(groups),
                "input_polygon_count": len(polygons), "output_component_count": 0, "output_polygon_count": 0,
                "outer_loop_count": 0, "inner_loop_count": 0, "input_area_m2_sum": sum(float(p.get("area_m2",0)) for p in polygons),
                "unified_area_m2": 0.0, "overlap_removed_area_m2": None, "area_balance_error_m2": None,
                "source_caster_indices": sorted(set(p.get("caster_index") for p in polygons)),
                "boolean_operation_attempt_count": stats["attempts"], "boolean_operation_success_count": stats["successes"],
                "boolean_operation_failure_count": stats["failures"], "retry_count": stats["retries"], "polygons": [], "blockers": blockers, "warnings": []}
        finally:
            _dispose_unique(all_native, disposed)
        result["slices"].append(slice_out)
        _checkpoint("FORMAL_UNION_SLICE_AFTER", slice_index, success=slice_out["complete"], component_count=slice_out["output_component_count"])
    result["input_polygon_count"] = sum(s["input_polygon_count"] for s in result["slices"])
    result["output_polygon_count"] = sum(s["output_polygon_count"] for s in result["slices"])
    result["input_component_count"] = sum(s["input_group_count"] for s in result["slices"])
    result["output_component_count"] = sum(s["output_component_count"] for s in result["slices"])
    result["successful_slice_count"] = sum(s["complete"] for s in result["slices"])
    result["failed_slice_count"] = len(result["slices"])-result["successful_slice_count"]
    for key, source in (("boolean_operation_attempt_count","boolean_operation_attempt_count"),("boolean_operation_success_count","boolean_operation_success_count"),("boolean_operation_failure_count","boolean_operation_failure_count")):
        result[key] = sum(s[source] for s in result["slices"])
    result["complete"] = bool(result["slices"]) and result["failed_slice_count"] == 0 and len(result["slices"]) == result["time_slice_count"]
    result["available"] = result["successful_slice_count"] > 0
    result["partial_success"] = result["available"] and not result["complete"]
    result["ready_for_duration_accumulation"] = result["complete"]
    result["blockers"] = [b for s in result["slices"] for b in s["blockers"]]
    for blocker in result["blockers"]:
        code = blocker["failure_code"]; result["failure_reason_counts"][code] = result["failure_reason_counts"].get(code, 0)+1
    _checkpoint("FORMAL_UNION_END", success=result["complete"])
    return result


build_unified_shadow_slices = _build_unified_shadow_slices
