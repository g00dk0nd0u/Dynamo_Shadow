"""Read-only Revit-native formal time-slice shadow polygon prototype.

Native objects accepted here are runtime-only.  Every returned value is JSON-safe;
there is deliberately no geometric fallback when a Revit operation fails.
"""
import math

from shadow_policies import FORMAL_SHADOW_PROJECTION_POLICY
from shadow_revit_api import (REVIT_API_CAPABILITIES, SolidUtils, ExtrusionAnalyzer,
    BooleanOperationsUtils, Plane, XYZ, Face)
from shadow_units import (_meters_to_internal_length, _internal_length_to_meters,
    _internal_volume_to_m3)
from shadow_utils import _runtime_checkpoint, _safe_text, _type_name

_ENGINE = "revit_extrusion_analyzer_v1"
_SCOPE = "positive_volume_extrusion_like_solids_line_loops"


def _failure(code, exc=None):
    result = {"failure_code": code}
    if exc is not None:
        result.update({"failure_type": type(exc).__name__, "failure_message": _safe_text(exc)[:240]})
    return result


def _formal_capability_blockers():
    required = {
        "revit_api_loaded": REVIT_API_CAPABILITIES.get("revit_api_loaded"),
        "solid_utils_split_volumes_expected": SolidUtils is not None and hasattr(SolidUtils, "SplitVolumes"),
        "extrusion_analyzer_create_expected": ExtrusionAnalyzer is not None and hasattr(ExtrusionAnalyzer, "Create"),
        "extrusion_analyzer_get_base_expected": ExtrusionAnalyzer is not None and hasattr(ExtrusionAnalyzer, "GetExtrusionBase"),
        "plane_xyz_available": Plane is not None and XYZ is not None,
        "face_get_edges_as_curve_loops_expected": Face is not None and hasattr(Face, "GetEdgesAsCurveLoops"),
        "boolean_cut_with_half_space_available": (
            BooleanOperationsUtils is not None
            and hasattr(BooleanOperationsUtils, "CutWithHalfSpace")
        ),
    }
    return [{"code": "required_revit_api_unavailable", "capability": key} for key in sorted(required) if not required[key]]


def _xyz_components(value):
    return tuple(float(getattr(value, key)) for key in ("X", "Y", "Z"))


def _new_xyz(x, y, z):
    return XYZ(float(x), float(y), float(z))


def _build_physical_shadow_ray_model(sun_slice, max_shadow_length_factor=100.0, xyz_type=None):
    """Build the physical light ray from the sun, through the caster, downward."""
    model = (sun_slice or {}).get("shadow_direction_model") or {}
    try:
        dx, dy = float(model.get("x")), float(model.get("y"))
        factor = float((sun_slice or {}).get("shadow_length_factor"))
        guard = float(max_shadow_length_factor)
    except (TypeError, ValueError, OverflowError):
        return None, _failure("invalid_shadow_direction_model_or_factor")
    if not all(math.isfinite(v) for v in (dx, dy, factor, guard)) or factor <= 0.0:
        return None, _failure("invalid_shadow_direction_model_or_factor")
    if factor > guard:
        return None, _failure("shadow_length_factor_exceeds_guard")
    raw = (dx * factor, dy * factor, -1.0)
    length = math.sqrt(sum(v * v for v in raw))
    if not math.isfinite(length) or length <= 0.0 or raw[2] >= 0.0:
        return None, _failure("invalid_shadow_direction_vector")
    values = tuple(v / length for v in raw)
    maker = xyz_type or XYZ
    native = maker(*values) if maker is not None else values
    return native, {
        "source": "shadow_direction_model", "x": values[0], "y": values[1], "z": values[2],
        "meaning": "physical_shadow_ray_model",
        "normalized": True, "true_north_rotation_already_applied": True,
    }


def _build_extrusion_analyzer_direction(physical_ray, xyz_type=None):
    """Convert only at the API boundary to ExtrusionAnalyzer's extrusion direction.

    ExtrusionAnalyzer describes a solid extruded from the measurement plane
    toward the source geometry.  That is the reverse of the physical downward
    ray used to project a shadow onto the plane.
    """
    try: values = tuple(-float(getattr(physical_ray, key)) for key in ("X", "Y", "Z"))
    except (TypeError, ValueError, AttributeError): return None, _failure("invalid_physical_shadow_ray_model")
    maker = xyz_type or XYZ
    return (maker(*values) if maker is not None else values), {
        "x": values[0], "y": values[1], "z": values[2], "normalized": True,
        "conversion": "negative_of_physical_shadow_ray_model_at_revit_api_boundary",
    }


def _build_shadow_direction(sun_slice, max_shadow_length_factor=100.0, xyz_type=None):
    """Backward-compatible name for the physical-ray builder."""
    return _build_physical_shadow_ray_model(sun_slice, max_shadow_length_factor, xyz_type)


def _expected_quadrant(ray, tolerance=1e-9):
    x, y = ray["x"], ray["y"]
    if abs(x) <= tolerance and y > 0: return "north"
    if x < 0 and y > 0: return "northwest"
    if x > 0 and y > 0: return "northeast"
    if abs(x) <= tolerance and y < 0: return "south"
    return "other"


def _validate_direction_contract(physical, analyzer, factor, expected_quadrant=None, tolerance=1e-9):
    def component(value, key):
        return float(value.get(key)) if isinstance(value, dict) else float(getattr(value, key.upper()))
    p = {key: component(physical, key) for key in ("x","y","z")}
    a = {key: component(analyzer, key) for key in ("x","y","z")}
    quadrant = _expected_quadrant(p, tolerance)
    antiparallel = all(abs(p[key] + a[key]) <= tolerance for key in p)
    length_ok = math.isclose(math.hypot(p["x"], p["y"]) / abs(p["z"]), float(factor), rel_tol=1e-9, abs_tol=tolerance)
    passed = p["z"] < 0 < a["z"] and antiparallel and length_ok and (expected_quadrant is None or quadrant == expected_quadrant)
    return passed, {"quadrant": quadrant, "horizontal_projection_length_per_unit_height": math.hypot(p["x"], p["y"]) / abs(p["z"]),
        "expected_height_times_shadow_length_factor": float(factor), "antiparallel_api_conversion": antiparallel,
        "reason": "physical ray, API conversion, quadrant, and analytical length agree" if passed else "direction, sign, quadrant, or analytical length mismatch"}


def _build_native_measurement_plane(measurement_plane, plane_type=None, xyz_type=None):
    elevation_m = (measurement_plane or {}).get("elevation_m")
    elevation_internal, warnings = _meters_to_internal_length(elevation_m)
    diagnostics = {"elevation_m": elevation_m, "elevation_internal": elevation_internal,
                   "normal": [0, 0, 1], "conversion_backend": "shadow_units._meters_to_internal_length",
                   "conversion_warnings": warnings}
    ptype, xtype = plane_type or Plane, xyz_type or XYZ
    if elevation_internal is None:
        return None, diagnostics, _failure("measurement_plane_elevation_unavailable")
    if ptype is None or xtype is None:
        return None, diagnostics, _failure("native_plane_api_unavailable")
    try:
        basis_z = getattr(xtype, "BasisZ", None) or xtype(0.0, 0.0, 1.0)
        origin = xtype(0.0, 0.0, elevation_internal)
        return ptype.CreateByNormalAndOrigin(basis_z, origin), diagnostics, None
    except BaseException as exc:
        return None, diagnostics, _failure("native_measurement_plane_creation_failed", exc)


def _signed_area(points):
    return 0.5 * sum(points[i][0] * points[(i + 1) % len(points)][1] - points[(i + 1) % len(points)][0] * points[i][1] for i in range(len(points)))


def _segments_intersect(a, b, c, d, eps=1e-10):
    def cross(p, q, r): return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
    v = (cross(a,b,c), cross(a,b,d), cross(c,d,a), cross(c,d,b))
    return v[0]*v[1] < -eps and v[2]*v[3] < -eps


def _self_intersects(points):
    n = len(points)
    for i in range(n):
        for j in range(i + 1, n):
            if j in (i, i + 1) or (i == 0 and j == n - 1): continue
            if _segments_intersect(points[i], points[(i+1)%n], points[j], points[(j+1)%n]): return True
    return False


def _value_or_call(obj, name):
    value = getattr(obj, name)
    return value() if callable(value) else value


def _curve_points(curve):
    p0, p1 = curve.GetEndPoint(0), curve.GetEndPoint(1)
    return _xyz_components(p0), _xyz_components(p1)


def _inspect_native_curve_loop(loop, loop_index, measurement_z_internal, settings, short_curve_tolerance=0.0):
    """Exact Line-only adapter. The caller owns and disposes ``loop``."""
    blockers = []
    try:
        if bool(_value_or_call(loop, "IsOpen")): blockers.append("native_shadow_loop_is_open")
        if not bool(_value_or_call(loop, "HasPlane")): blockers.append("native_shadow_loop_is_non_planar")
    except BaseException as exc:
        return None, [_failure("native_shadow_loop_validation_exception", exc)]
    try: curves = list(loop)
    except BaseException as exc: return None, [_failure("native_shadow_loop_iteration_exception", exc)]
    if not curves: blockers.append("native_shadow_loop_has_no_curves")
    if len(curves) > int(settings.get("max_formal_shadow_loop_points", 2000)):
        blockers.append("formal_shadow_loop_point_cap_exceeded")
    points_raw, curve_types = [], []
    previous_end = None
    for curve in curves:
        curve_type = _type_name(curve)
        curve_types.append(curve_type)
        if curve_type != "Line" and not curve_type.endswith(".Line"):
            blockers.append("native_shadow_loop_contains_non_line_curve")
            continue
        try:
            p0, p1 = _curve_points(curve)
            length = float(getattr(curve, "Length", math.dist(p0, p1)))
            if length <= float(short_curve_tolerance or 0.0): blockers.append("native_shadow_loop_short_edge")
            if previous_end is not None and math.dist(previous_end, p0) > 1e-7: blockers.append("native_shadow_loop_discontinuous")
            if abs(p0[2] - measurement_z_internal) > 1e-6 or abs(p1[2] - measurement_z_internal) > 1e-6:
                blockers.append("native_shadow_loop_off_measurement_plane")
            points_raw.append(p0); previous_end = p1
        except BaseException as exc: blockers.append("native_shadow_line_endpoint_unavailable:" + type(exc).__name__)
    if points_raw and previous_end is not None and math.dist(previous_end, points_raw[0]) > 1e-7:
        blockers.append("native_shadow_loop_discontinuous")
    xy_raw = [(p[0], p[1]) for p in points_raw]
    if len(xy_raw) >= 3 and _self_intersects(xy_raw): blockers.append("native_shadow_loop_self_intersection")
    area_raw = _signed_area(xy_raw) if len(xy_raw) >= 3 else 0.0
    if abs(area_raw) <= 1e-12: blockers.append("native_shadow_loop_zero_area")
    if blockers: return None, sorted(set(blockers))
    points_m = []
    for x, y in xy_raw:
        mx, _ = _internal_length_to_meters(x); my, _ = _internal_length_to_meters(y)
        points_m.append({"x": mx, "y": my})
    area_m2 = abs(_signed_area([(p["x"], p["y"]) for p in points_m]))
    perimeter_m = sum(math.dist((points_m[i]["x"], points_m[i]["y"]), (points_m[(i+1)%len(points_m)]["x"], points_m[(i+1)%len(points_m)]["y"])) for i in range(len(points_m)))
    return {"source_loop_index": loop_index, "points_m": points_m, "point_count": len(points_m),
            "curve_count": len(curves), "closed": True, "area_m2": area_m2, "perimeter_m": perimeter_m,
            "contains_non_line_curve": False, "curve_types": curve_types,
            "orientation": "ccw" if _signed_area([(p["x"],p["y"]) for p in points_m]) > 0 else "cw"}, []


def _point_in_polygon(point, polygon):
    x, y = point; inside = False
    for i in range(len(polygon)):
        x1,y1 = polygon[i]; x2,y2 = polygon[(i+1)%len(polygon)]
        if (y1 > y) != (y2 > y) and x < (x2-x1)*(y-y1)/(y2-y1)+x1: inside = not inside
    return inside


def _classify_and_orient(polygons):
    for item in polygons:
        p = [(v["x"],v["y"]) for v in item["points_m"]]
        depth = sum(1 for other in polygons if other is not item and _point_in_polygon(p[0], [(v["x"],v["y"]) for v in other["points_m"]]))
        role = "outer" if depth % 2 == 0 else "inner"; desired = "ccw" if role == "outer" else "cw"
        if item["orientation"] != desired:
            item["points_m"].reverse(); item["orientation"] = desired
        item.update({"role": role, "containment_depth": depth})
    return polygons


def _validate_actual_polygon_direction(section_polygons, shadow_polygons, physical_ray,
                                       tolerance_m=1e-6):
    """Validate extracted geometry along the horizontal down-shadow axis."""
    try:
        dx, dy = float(physical_ray["x"]), float(physical_ray["y"])
        length = math.hypot(dx, dy)
        axis = (dx / length, dy / length)
        section_values = [float(p["x"]) * axis[0] + float(p["y"]) * axis[1]
            for polygon in section_polygons for p in polygon.get("points_m", [])]
        shadow_values = [float(p["x"]) * axis[0] + float(p["y"]) * axis[1]
            for polygon in shadow_polygons for p in polygon.get("points_m", [])]
    except (TypeError, ValueError, KeyError, ZeroDivisionError):
        section_values, shadow_values = [], []
    result = {"section_axis_min_m": min(section_values) if section_values else None,
        "section_axis_max_m": max(section_values) if section_values else None,
        "shadow_axis_min_m": min(shadow_values) if shadow_values else None,
        "shadow_axis_max_m": max(shadow_values) if shadow_values else None,
        "sunward_overflow_m": None, "downshadow_extension_m": None,
        "passed": False, "reason": "measurement-plane section or shadow polygon unavailable"}
    if not section_values or not shadow_values:
        return result
    overflow = max(0.0, result["section_axis_min_m"] - result["shadow_axis_min_m"])
    extension = max(0.0, result["shadow_axis_max_m"] - result["section_axis_max_m"])
    result.update({"sunward_overflow_m": overflow, "downshadow_extension_m": extension})
    result["passed"] = overflow <= float(tolerance_m) and extension > float(tolerance_m)
    result["reason"] = ("shadow polygon stays out of the sunward side and extends down-shadow"
        if result["passed"] else "shadow polygon extends sunward or has no down-shadow extension")
    return result


def _validate_projection_extents(source_points_m, shadow_polygons, physical_ray,
                                 shadow_length_factor, measurement_plane_z_m,
                                 tolerance_m=1e-6):
    """Independently compare analytical endpoint projection with analyzer output."""
    result = {"expected_shadow_axis_min_m": None, "expected_shadow_axis_max_m": None,
        "actual_shadow_axis_min_m": None, "actual_shadow_axis_max_m": None,
        "extent_error_min_m": None, "extent_error_max_m": None,
        "extent_validation_tolerance_m": None,
        "extent_validation_attempted": False, "extent_validation_passed": None,
        "extent_validation_status": "unverified",
        "extent_validation_reason": "source_points_unavailable"}
    try:
        tolerance = float(tolerance_m)
        if not math.isfinite(tolerance): raise ValueError("non-finite tolerance")
        result["extent_validation_tolerance_m"] = tolerance
    except (TypeError, ValueError, OverflowError):
        result["extent_validation_reason"] = "numeric_conversion_failed"
        return result
    if not source_points_m:
        return result
    polygon_points = [p for polygon in (shadow_polygons or [])
        for p in polygon.get("points_m", [])]
    if not polygon_points:
        result["extent_validation_reason"] = "shadow_polygon_points_unavailable"
        return result
    try:
        dx, dy = float(physical_ray["x"]), float(physical_ray["y"])
        axis_length = math.hypot(dx, dy)
        if not math.isfinite(axis_length) or axis_length == 0:
            result["extent_validation_reason"] = "physical_ray_unavailable_or_invalid"
            return result
        axis = (dx / axis_length, dy / axis_length)
    except (TypeError, ValueError, KeyError, ZeroDivisionError, OverflowError):
        result["extent_validation_reason"] = "physical_ray_unavailable_or_invalid"
        return result
    try:
        factor = float(shadow_length_factor); plane_z = float(measurement_plane_z_m)
        if not math.isfinite(factor) or not math.isfinite(plane_z):
            result["extent_validation_reason"] = "measurement_plane_or_factor_invalid"
            return result
    except (TypeError, ValueError, OverflowError):
        result["extent_validation_reason"] = "measurement_plane_or_factor_invalid"
        return result
    try:
        expected = [float(p["x"]) * axis[0] + float(p["y"]) * axis[1]
            + (float(p["z"]) - plane_z) * factor for p in source_points_m]
        actual = [float(p["x"]) * axis[0] + float(p["y"]) * axis[1]
            for p in polygon_points]
    except (TypeError, ValueError, KeyError, ZeroDivisionError, OverflowError):
        result["extent_validation_reason"] = "numeric_conversion_failed"
        return result
    if not expected or not actual or not all(math.isfinite(value) for value in expected + actual):
        result["extent_validation_reason"] = "numeric_conversion_failed"
        return result
    result["extent_validation_attempted"] = True
    result.update({"expected_shadow_axis_min_m": min(expected),
        "expected_shadow_axis_max_m": max(expected), "actual_shadow_axis_min_m": min(actual),
        "actual_shadow_axis_max_m": max(actual)})
    result["extent_error_min_m"] = result["actual_shadow_axis_min_m"] - result["expected_shadow_axis_min_m"]
    result["extent_error_max_m"] = result["actual_shadow_axis_max_m"] - result["expected_shadow_axis_max_m"]
    result["extent_validation_passed"] = (abs(result["extent_error_min_m"]) <= tolerance
        and abs(result["extent_error_max_m"]) <= tolerance)
    result["extent_validation_status"] = ("passed" if result["extent_validation_passed"] else "failed")
    result["extent_validation_reason"] = "projection_extent_compared"
    return result


def _aggregate_runtime_checks(checks):
    """Build one stable tri-state result for any analyzer count."""
    states = []
    for check in checks:
        direction_attempted = check.get("direction_validation_attempted") is True
        extent_attempted = check.get("extent_validation_attempted") is True
        failed = ((direction_attempted and check.get("direction_validation_passed") is False)
                  or (extent_attempted and check.get("extent_validation_passed") is False))
        verified = (direction_attempted and check.get("direction_validation_passed") is True
                    and extent_attempted and check.get("extent_validation_passed") is True)
        states.append("failed" if failed else ("verified" if verified else "unverified"))
    status = "failed" if "failed" in states else (
        "verified" if states and all(state == "verified" for state in states) else "unverified")
    result = {"passed": True if status == "verified" else (False if status == "failed" else None),
        "reason": {"verified":"all_runtime_projection_checks_verified",
                   "failed":"one_or_more_runtime_projection_checks_failed",
                   "unverified":"one_or_more_runtime_projection_checks_unverified"}[status],
        "runtime_validation_status": status, "runtime_validation_verified": status == "verified",
        "runtime_validation_failed": status == "failed", "runtime_validation_unverified": status == "unverified",
        "check_count": len(checks), "verified_check_count": states.count("verified"),
        "failed_check_count": states.count("failed"), "unverified_check_count": states.count("unverified"),
        "checks": checks}
    if len(checks) == 1:
        for key, value in checks[0].items():
            if key != "passed": result[key] = value
    return result


def _runtime_validation_blocker(aggregate, runtime_check_required):
    if not runtime_check_required or aggregate["runtime_validation_status"] == "verified":
        return None
    code = ("runtime_projection_validation_failed" if aggregate["runtime_validation_failed"]
        else "runtime_projection_validation_unverified")
    return {"failure_code": code,
        "runtime_validation_status": aggregate["runtime_validation_status"],
        "failed_check_count": aggregate["failed_check_count"],
        "unverified_check_count": aggregate["unverified_check_count"]}


def _solid_edge_endpoints_m(solid):
    """Read clipped Solid edge endpoints for validation only; never serialize natives."""
    points = []
    try: edges = list(getattr(solid, "Edges"))
    except BaseException: return points
    for edge in edges:
        try:
            curve = edge.AsCurve()
            for index in (0, 1):
                x, y, z = _xyz_components(curve.GetEndPoint(index))
                mx, _ = _internal_length_to_meters(x); my, _ = _internal_length_to_meters(y)
                mz, _ = _internal_length_to_meters(z)
                points.append({"x": mx, "y": my, "z": mz})
        except BaseException:
            continue
    return points


def _measurement_section_polygons(solid, measurement_z_internal, settings, short_tolerance):
    """Read the horizontal face introduced by the half-space cut."""
    polygons = []
    try: faces = list(getattr(solid, "Faces"))
    except BaseException: return polygons
    for face in faces:
        try:
            normal = getattr(face, "FaceNormal")
            origin = getattr(face, "Origin")
            if abs(abs(float(normal.Z)) - 1.0) > 1e-7 or abs(float(origin.Z) - measurement_z_internal) > 1e-6:
                continue
            loops = list(face.GetEdgesAsCurveLoops())
        except BaseException:
            continue
        for index, loop in enumerate(loops):
            try:
                polygon, _ = _inspect_native_curve_loop(loop, index, measurement_z_internal,
                    settings, short_tolerance)
                if polygon: polygons.append(polygon)
            finally:
                try: loop.Dispose()
                except BaseException: pass
    return _classify_and_orient(polygons)


def _volume_m3(solid):
    try:
        raw = float(getattr(solid, "Volume"))
    except BaseException:
        return None, None
    converted, _ = _internal_volume_to_m3(raw)
    return raw, converted


def _dispose_owned_solids(owned):
    diagnostics = []
    seen = set()
    for solid in reversed(owned):
        if solid is None or id(solid) in seen:
            continue
        seen.add(id(solid)); item = {"dispose_attempted": True, "dispose_succeeded": False}
        try:
            solid.Dispose(); item["dispose_succeeded"] = True
        except BaseException as exc:
            item.update(_failure("clipped_solid_dispose_failure", exc))
        diagnostics.append(item)
    return diagnostics


def _split_and_clip_runtime_geometry(runtime_geometry, native_plane, measurement_elevation_m):
    casters, blockers, count = [], [], 0
    owned = []
    for caster in sorted((runtime_geometry or {}).get("casters") or [], key=lambda x: x.get("caster_index", 0)):
        output = {"caster_index": caster.get("caster_index"), "element_id": caster.get("element_id"), "source_solid_count": len(caster.get("solids") or []), "solids": [], "blockers": []}
        for source in sorted(caster.get("solids") or [], key=lambda x: x.get("solid_index", 0)):
            si = source.get("solid_index", 0); _runtime_checkpoint("FORMAL_SHADOW_SPLIT_BEFORE", "caster_index={0},split_solid_index=0".format(output["caster_index"]))
            original = source.get("native_solid")
            try: split = list(SolidUtils.SplitVolumes(original))
            except BaseException as exc:
                output["blockers"].append(dict(_failure("solid_split_exception", exc), source_solid_index=si)); _runtime_checkpoint("FORMAL_SHADOW_SPLIT_AFTER", "failure"); continue
            accepted = 0
            for split_index, solid in enumerate(split):
                if solid is not original: owned.append(solid)
                volume, source_volume_m3 = _volume_m3(solid)
                if volume is None or volume <= 0.0:
                    output["blockers"].append({"failure_code":"split_solid_zero_or_unknown_volume", "source_solid_index":si, "split_solid_index":split_index}); continue
                clip = {"measurement_plane_elevation_m": measurement_elevation_m,
                    "half_space_normal": {"x": 0.0, "y": 0.0, "z": 1.0},
                    "half_space_retained_side": "positive_z_above_measurement_plane",
                    "half_space_clip_attempted": True, "half_space_clip_succeeded": False,
                    "source_volume_m3": source_volume_m3, "clipped_volume_m3": None,
                    "below_plane_volume_removed_m3": None, "clipped_component_count": 0,
                    "clipped_min_z_m": None, "clipped_max_z_m": None,
                    "retained_side": "positive_z_above_measurement_plane", "disposal_succeeded": None,
                    "analyzer_input_geometry": "clipped_above_measurement_plane",
                    "skipped_because_not_above_measurement_plane": False}
                try:
                    clipped = BooleanOperationsUtils.CutWithHalfSpace(solid, native_plane)
                    clip["half_space_clip_succeeded"] = clipped is not None
                    if clipped is None: raise RuntimeError("CutWithHalfSpace returned no Solid")
                    owned.append(clipped)
                    clipped_raw, clipped_m3 = _volume_m3(clipped)
                    clip["clipped_volume_m3"] = clipped_m3
                    if source_volume_m3 is not None and clipped_m3 is not None:
                        clip["below_plane_volume_removed_m3"] = max(0.0, source_volume_m3 - clipped_m3)
                    if clipped_raw is None or clipped_raw <= 0.0:
                        clip["skipped_because_not_above_measurement_plane"] = True
                        output["solids"].append(dict(clip, source_solid_index=si,
                            split_solid_index=split_index, components=[]))
                        accepted += 1; continue
                    components = list(SolidUtils.SplitVolumes(clipped))
                    positive = []
                    for component in components:
                        if component is not clipped: owned.append(component)
                        component_raw, _ = _volume_m3(component)
                        if component_raw is not None and component_raw > 0.0: positive.append(component)
                    clip["clipped_component_count"] = len(positive)
                    endpoint_z = [p["z"] for component in positive for p in _solid_edge_endpoints_m(component)]
                    clip["clipped_min_z_m"] = min(endpoint_z) if endpoint_z else None
                    clip["clipped_max_z_m"] = max(endpoint_z) if endpoint_z else None
                    clip["skipped_because_not_above_measurement_plane"] = not positive
                    output["solids"].append(dict(clip, source_solid_index=si,
                        split_solid_index=split_index, components=positive))
                    accepted += 1; count += len(positive)
                except BaseException as exc:
                    # A failed clip is a formal blocker. Never analyze the uncut Solid.
                    output["blockers"].append(dict(_failure("half_space_clip_failed", exc),
                        source_solid_index=si, split_solid_index=split_index))
                    output["solids"].append(dict(clip, source_solid_index=si,
                        split_solid_index=split_index, components=[]))
            _runtime_checkpoint("FORMAL_SHADOW_SPLIT_AFTER", "ok" if accepted else "failure")
        casters.append(output)
    return casters, blockers, count, owned


def _empty_result(measurement_plane, slices, runtime_geometry):
    return {"available": False, "complete": False, "partial_success": False, "engine": _ENGINE, "prototype_scope": _SCOPE,
            "formal_geometry": True, "diagnostic_convex_hull_used_as_fallback": False, "permit_ready_certified": False,
            "site_boundary_required": False, "measurement_plane_elevation_m": (measurement_plane or {}).get("elevation_m"),
            "time_slice_count": len(slices or []), "caster_count": len((runtime_geometry or {}).get("casters") or []),
            "split_solid_count": 0, "polygon_count": 0, "successful_slice_caster_count": 0, "failed_slice_caster_count": 0,
            "union_performed": False, "overlap_double_counting_resolved": False, "slices": [], "blockers": [], "warnings": []}


def _build_formal_shadow_polygons(runtime_geometry, measurement_plane, sun_time_slices, settings_normalized=None, diagnostic_projection=None):
    settings = (settings_normalized or {}).get("normalized") or settings_normalized or {}
    slices = list(sun_time_slices or []); result = _empty_result(measurement_plane, slices, runtime_geometry)
    _runtime_checkpoint("FORMAL_SHADOW_BEGIN")
    blockers = _formal_capability_blockers()
    if blockers: result["blockers"] = blockers; _runtime_checkpoint("FORMAL_SHADOW_END", "failure"); return result
    native_plane, plane_diag, plane_error = _build_native_measurement_plane(measurement_plane)
    result["measurement_plane"] = plane_diag
    if plane_error: result["blockers"].append(plane_error); _runtime_checkpoint("FORMAL_SHADOW_END", "failure"); return result
    split_casters, split_blockers, split_count, owned_solids = _split_and_clip_runtime_geometry(
        runtime_geometry, native_plane, (measurement_plane or {}).get("elevation_m"))
    result["split_solid_count"] = split_count; result["blockers"].extend(split_blockers)
    max_factor = settings.get("max_shadow_length_factor", 100.0)
    short_tol = settings.get("short_curve_tolerance_internal", 0.0)
    for slice_index, sun_slice in enumerate(slices):
        _runtime_checkpoint("FORMAL_SHADOW_SLICE_BEFORE", "slice_index={0}".format(slice_index))
        physical_direction, physical_info = _build_physical_shadow_ray_model(sun_slice, max_factor)
        direction, direction_info = (None, None)
        if physical_direction is not None:
            direction, direction_info = _build_extrusion_analyzer_direction(physical_direction)
        expected = _expected_quadrant(physical_info) if physical_info else None
        validation_passed, validation = (False, {"reason":"direction unavailable"})
        if direction is not None:
            validation_passed, validation = _validate_direction_contract(
                physical_direction, direction, sun_slice.get("shadow_length_factor"), expected)
        slice_out = {"slice_index": slice_index, "input_time": sun_slice.get("input_time"), "true_solar_time": sun_slice.get("true_solar_time"),
                     "solar_altitude_deg": sun_slice.get("solar_altitude_deg"), "solar_azimuth_deg": sun_slice.get("solar_azimuth_deg"),
                     "shadow_azimuth_true_north_deg": sun_slice.get("shadow_azimuth_true_north_deg"),
                     "shadow_azimuth_model_deg": sun_slice.get("shadow_azimuth_model_deg"),
                     "shadow_length_factor": sun_slice.get("shadow_length_factor"),
                     "physical_shadow_ray_model": physical_info, "extrusion_analyzer_input_direction": direction_info,
                     "expected_shadow_quadrant": expected,
                     "direction_vector_contract_check": validation,
                     "actual_polygon_direction_check": {"passed":False, "reason":"runtime polygon not yet verified"},
                     "direction_validation_passed": validation_passed,
                     "direction_validation_reason": validation.get("reason"),
                     "pure_python_verified": validation_passed, "revit_runtime_direction_verified": False,
                     "casters": [], "complete": True, "blockers": [], "warnings": []}
        if direction is None:
            slice_out["complete"] = False; slice_out["blockers"].append(direction_info or physical_info); result["slices"].append(slice_out); _runtime_checkpoint("FORMAL_SHADOW_SLICE_AFTER", "failure"); continue
        if not validation_passed:
            slice_out["complete"] = False
            slice_out["blockers"].append({"failure_code":"direction_validation_failed", "reason":validation.get("reason")})
        for caster in split_casters:
            caster_out = {k: caster.get(k) for k in ("caster_index","element_id","source_solid_count")}
            caster_out.update({"split_solid_count":len(caster["solids"]), "complete":True, "polygons":[], "analyzers":[], "blockers":list(caster["blockers"]), "warnings":[]})
            for split in caster["solids"]:
                if split.get("skipped_because_not_above_measurement_plane"):
                    caster_out["analyzers"].append({k:v for k,v in split.items() if k != "components"})
                    continue
                for component_index, component in enumerate(split.get("components") or []):
                  analyzer = None
                  ad = {"create_attempted":True, "create_succeeded":False, "get_extrusion_base_succeeded":False,
                      "extrusion_direction_xyz": {k: direction_info[k] for k in ("x","y","z")}, "dispose_attempted":False, "dispose_succeeded":False,
                      "source_solid_index":split["source_solid_index"], "split_solid_index":split["split_solid_index"],
                      "clipped_component_index":component_index}
                  ad.update({k:v for k,v in split.items() if k != "components"})
                  detail = "slice_index={0},caster_index={1},split_solid_index={2},clipped_component_index={3}".format(slice_index,caster["caster_index"],split["split_solid_index"],component_index)
                  try:
                    _runtime_checkpoint("FORMAL_SHADOW_ANALYZER_CREATE_BEFORE", detail)
                    analyzer = ExtrusionAnalyzer.Create(component, native_plane, direction); ad["create_succeeded"] = True
                    _runtime_checkpoint("FORMAL_SHADOW_ANALYZER_CREATE_AFTER", detail+",ok")
                    for name, key in (("GetStartParameter","start_parameter_internal"),("GetEndParameter","end_parameter_internal")):
                        try: ad[key] = float(getattr(analyzer,name)()); ad[key.replace("internal","m")], _ = _internal_length_to_meters(ad[key])
                        except BaseException: ad[key] = ad[key.replace("internal","m")] = None
                    ad["analyzer_start_parameter_m"] = ad.get("start_parameter_m")
                    ad["analyzer_end_parameter_m"] = ad.get("end_parameter_m")
                    tolerance_m = float(settings.get("closure_tolerance_m", 1e-6) or 1e-6)
                    ad["analyzer_start_parameter_nonnegative"] = (ad.get("start_parameter_m") is not None
                        and ad["start_parameter_m"] >= -tolerance_m)
                    if ad.get("start_parameter_m") is not None and not ad["analyzer_start_parameter_nonnegative"]:
                        caster_out["blockers"].append({"failure_code":"analyzer_start_parameter_below_measurement_plane",
                            "start_parameter_m":ad["start_parameter_m"]})
                    _runtime_checkpoint("FORMAL_SHADOW_BASE_FACE_BEFORE", detail)
                    face = analyzer.GetExtrusionBase(); ad["get_extrusion_base_succeeded"] = face is not None
                    _runtime_checkpoint("FORMAL_SHADOW_BASE_FACE_AFTER", detail + (",ok" if face is not None else ",failure"))
                    if face is None: raise RuntimeError("GetExtrusionBase returned no face")
                    _runtime_checkpoint("FORMAL_SHADOW_CURVELOOPS_BEFORE", detail)
                    loops = list(face.GetEdgesAsCurveLoops()); extracted = []
                    for loop_index, loop in enumerate(loops):
                        try:
                            polygon, loop_blockers = _inspect_native_curve_loop(loop, loop_index, plane_diag["elevation_internal"], settings, short_tol)
                            if polygon: extracted.append(polygon)
                            else:
                                for blocker in loop_blockers: caster_out["blockers"].append({"failure_code": blocker} if isinstance(blocker,str) else blocker)
                        finally:
                            try: loop.Dispose()
                            except BaseException as exc: caster_out["warnings"].append(_failure("curve_loop_dispose_failed", exc))
                    _runtime_checkpoint("FORMAL_SHADOW_CURVELOOPS_AFTER", detail+",ok")
                    classified = _classify_and_orient(extracted)
                    section = _measurement_section_polygons(component,
                        plane_diag["elevation_internal"], settings, short_tol)
                    polygon_check = _validate_actual_polygon_direction(section, classified,
                        physical_info, tolerance_m)
                    direction_attempted = (polygon_check.get("section_axis_min_m") is not None
                        and polygon_check.get("shadow_axis_min_m") is not None)
                    polygon_check.update({"direction_validation_attempted": direction_attempted,
                        "direction_validation_passed": (polygon_check.get("passed") if direction_attempted else None),
                        "direction_validation_status": (("passed" if polygon_check.get("passed") else "failed")
                            if direction_attempted else "unverified")})
                    extent_check = _validate_projection_extents(_solid_edge_endpoints_m(component),
                        classified, physical_info, sun_slice.get("shadow_length_factor"),
                        (measurement_plane or {}).get("elevation_m"), tolerance_m)
                    polygon_check.update(extent_check)
                    for polygon in classified:
                        polygon.update({"polygon_index":len(caster_out["polygons"]), "source_solid_index":split["source_solid_index"],
                                        "split_solid_index":split["split_solid_index"], "generation_method":"revit_extrusion_analyzer_curve_loop_line_exact",
                                        "direction_validation_passed":validation_passed,
                                        "direction_validation_reason":validation.get("reason")})
                        caster_out["polygons"].append(polygon)
                    ad["actual_polygon_direction_check"] = polygon_check
                    if not extracted: ad.update(_failure("no_valid_native_line_shadow_loop"))
                  except BaseException as exc:
                    code = "extrusion_analyzer_exception" if not ad["create_succeeded"] else ("get_extrusion_base_failure" if not ad["get_extrusion_base_succeeded"] else "native_curve_loop_acquisition_failure")
                    ad.update(_failure(code, exc)); caster_out["blockers"].append(_failure(code, exc))
                  finally:
                    if analyzer is not None:
                        ad["dispose_attempted"] = True
                        try: analyzer.Dispose(); ad["dispose_succeeded"] = True
                        except BaseException as exc: ad.update(_failure("extrusion_analyzer_dispose_failure", exc))
                    _runtime_checkpoint("FORMAL_SHADOW_ANALYZER_DISPOSE_AFTER", detail + (",ok" if ad["dispose_succeeded"] else ",failure"))
                  caster_out["analyzers"].append(ad)
            all_skipped = bool(caster["solids"]) and all(
                item.get("skipped_because_not_above_measurement_plane") for item in caster["solids"])
            caster_out["complete"] = (bool(caster_out["polygons"]) or all_skipped) and not caster_out["blockers"]
            if caster_out["polygons"]: result["successful_slice_caster_count"] += 1
            else: result["failed_slice_caster_count"] += 1
            slice_out["casters"].append(caster_out)
        checks = [a.get("actual_polygon_direction_check") for c in slice_out["casters"]
            for a in c["analyzers"] if a.get("actual_polygon_direction_check")]
        aggregate = _aggregate_runtime_checks(checks)
        slice_out["actual_polygon_direction_check"] = aggregate
        slice_out["revit_runtime_direction_verified"] = aggregate["runtime_validation_verified"]
        runtime_check_required = any(split.get("components") for caster in split_casters for split in caster["solids"])
        caster_pipeline_complete = (bool(slice_out["casters"])
            and all(caster.get("complete") is True for caster in slice_out["casters"]))
        runtime_validation_complete = (aggregate["runtime_validation_status"] == "verified"
            or not runtime_check_required)
        slice_out["complete"] = (validation_passed and caster_pipeline_complete
            and runtime_validation_complete)
        blocker_codes = {b.get("failure_code") for b in slice_out["blockers"] if isinstance(b, dict)}
        runtime_blocker = _runtime_validation_blocker(aggregate, runtime_check_required)
        if runtime_blocker and runtime_blocker["failure_code"] not in blocker_codes:
            slice_out["blockers"].append(runtime_blocker)
            blocker_codes.add(runtime_blocker["failure_code"])
        if not caster_pipeline_complete and "one_or_more_caster_or_analyzer_operations_failed" not in blocker_codes:
            slice_out["blockers"].append({"failure_code":"one_or_more_caster_or_analyzer_operations_failed"})
        diagnostic_slices = (diagnostic_projection or {}).get("slices") or []
        diagnostic_slice = diagnostic_slices[slice_index] if slice_index < len(diagnostic_slices) else {}
        hull = diagnostic_slice.get("convex_shadow_envelope_v0") or {}
        formal_area = sum(p.get("area_m2", 0.0) * (-1.0 if p.get("role") == "inner" else 1.0)
                          for c in slice_out["casters"] for p in c["polygons"])
        hull_area = hull.get("area_m2") if hull.get("available") else None
        slice_out["comparison"] = {
            "formal_polygon_available": any(c["polygons"] for c in slice_out["casters"]),
            "diagnostic_convex_hull_available": hull.get("available") is True,
            "formal_outer_area_sum_m2": formal_area,
            "diagnostic_convex_hull_area_m2": hull_area,
            "area_difference_m2": (hull_area - formal_area) if hull_area is not None else None,
            "diagnostic_minus_formal_area_m2": (hull_area - formal_area) if hull_area is not None else None,
            "comparison_is_validation_only": True,
            "formal_area_is_not_union_area": True,
        }
        result["slices"].append(slice_out); _runtime_checkpoint("FORMAL_SHADOW_SLICE_AFTER", "ok" if slice_out["complete"] else "failure")
    result["polygon_count"] = sum(len(c["polygons"]) for s in result["slices"] for c in s["casters"])
    result["available"] = result["polygon_count"] > 0
    result["complete"] = bool(result["slices"]) and all(s["complete"] for s in result["slices"])
    result["partial_success"] = result["available"] and not result["complete"]
    result["owned_solid_disposal"] = _dispose_owned_solids(owned_solids)
    disposal_succeeded = all(item.get("dispose_succeeded") is True
        for item in result["owned_solid_disposal"])
    for caster in split_casters:
        for split in caster.get("solids") or []:
            split["disposal_succeeded"] = disposal_succeeded
    _runtime_checkpoint("FORMAL_SHADOW_END", "ok" if result["available"] else "failure")
    return result


build_formal_shadow_polygons = _build_formal_shadow_polygons
