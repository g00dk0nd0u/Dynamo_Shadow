"""Read-only Revit-native formal time-slice shadow polygon prototype.

Native objects accepted here are runtime-only.  Every returned value is JSON-safe;
there is deliberately no geometric fallback when a Revit operation fails.
"""
import math

from shadow_policies import FORMAL_SHADOW_PROJECTION_POLICY
from shadow_revit_api import REVIT_API_CAPABILITIES, SolidUtils, ExtrusionAnalyzer, Plane, XYZ, Face
from shadow_units import _meters_to_internal_length, _internal_length_to_meters
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


def _split_runtime_geometry(runtime_geometry):
    casters, blockers, count = [], [], 0
    for caster in sorted((runtime_geometry or {}).get("casters") or [], key=lambda x: x.get("caster_index", 0)):
        output = {"caster_index": caster.get("caster_index"), "element_id": caster.get("element_id"), "source_solid_count": len(caster.get("solids") or []), "solids": [], "blockers": []}
        for source in sorted(caster.get("solids") or [], key=lambda x: x.get("solid_index", 0)):
            si = source.get("solid_index", 0); _runtime_checkpoint("FORMAL_SHADOW_SPLIT_BEFORE", "caster_index={0},split_solid_index=0".format(output["caster_index"]))
            try: split = list(SolidUtils.SplitVolumes(source.get("native_solid")))
            except BaseException as exc:
                output["blockers"].append(dict(_failure("solid_split_exception", exc), source_solid_index=si)); _runtime_checkpoint("FORMAL_SHADOW_SPLIT_AFTER", "failure"); continue
            accepted = 0
            for split_index, solid in enumerate(split):
                try: volume = float(getattr(solid, "Volume"))
                except BaseException: volume = None
                if volume is None or volume <= 0.0:
                    output["blockers"].append({"failure_code":"split_solid_zero_or_unknown_volume", "source_solid_index":si, "split_solid_index":split_index}); continue
                output["solids"].append({"source_solid_index":si, "split_solid_index":split_index, "native_solid":solid}); accepted += 1; count += 1
            _runtime_checkpoint("FORMAL_SHADOW_SPLIT_AFTER", "ok" if accepted else "failure")
        casters.append(output)
    return casters, blockers, count


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
    split_casters, split_blockers, split_count = _split_runtime_geometry(runtime_geometry)
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
                     "expected_shadow_quadrant": expected, "actual_polygon_direction_check": validation,
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
                analyzer = None
                ad = {"create_attempted":True, "create_succeeded":False, "get_extrusion_base_succeeded":False,
                      "extrusion_direction_xyz": {k: direction_info[k] for k in ("x","y","z")}, "dispose_attempted":False, "dispose_succeeded":False,
                      "source_solid_index":split["source_solid_index"], "split_solid_index":split["split_solid_index"]}
                detail = "slice_index={0},caster_index={1},split_solid_index={2}".format(slice_index,caster["caster_index"],split["split_solid_index"])
                try:
                    _runtime_checkpoint("FORMAL_SHADOW_ANALYZER_CREATE_BEFORE", detail)
                    analyzer = ExtrusionAnalyzer.Create(split["native_solid"], native_plane, direction); ad["create_succeeded"] = True
                    _runtime_checkpoint("FORMAL_SHADOW_ANALYZER_CREATE_AFTER", detail+",ok")
                    for name, key in (("GetStartParameter","start_parameter_internal"),("GetEndParameter","end_parameter_internal")):
                        try: ad[key] = float(getattr(analyzer,name)()); ad[key.replace("internal","m")], _ = _internal_length_to_meters(ad[key])
                        except BaseException: ad[key] = ad[key.replace("internal","m")] = None
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
                    for polygon in _classify_and_orient(extracted):
                        polygon.update({"polygon_index":len(caster_out["polygons"]), "source_solid_index":split["source_solid_index"],
                                        "split_solid_index":split["split_solid_index"], "generation_method":"revit_extrusion_analyzer_curve_loop_line_exact",
                                        "direction_validation_passed":validation_passed,
                                        "direction_validation_reason":validation.get("reason")})
                        caster_out["polygons"].append(polygon)
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
            caster_out["complete"] = bool(caster_out["polygons"]) and not caster_out["blockers"]
            if caster_out["polygons"]: result["successful_slice_caster_count"] += 1
            else: result["failed_slice_caster_count"] += 1
            slice_out["casters"].append(caster_out)
        slice_out["complete"] = validation_passed and bool(slice_out["casters"]) and all(c["complete"] for c in slice_out["casters"])
        if not slice_out["complete"]: slice_out["blockers"].append({"failure_code":"one_or_more_caster_splits_failed"})
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
    _runtime_checkpoint("FORMAL_SHADOW_END", "ok" if result["available"] else "failure")
    return result


build_formal_shadow_polygons = _build_formal_shadow_polygons
