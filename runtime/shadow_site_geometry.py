"""Pure-Python Area site-boundary loop validation and polygon normalization."""
import math

METHOD = "revit_area_single_outer_loop_v1"


def _empty(blocker=None):
    blockers = [] if blocker is None else ([blocker] if isinstance(blocker, dict) else [{"failure_code": blocker}])
    return {"available": False, "complete": False, "method": METHOD, "source": "revit_area",
            "outer_loop": [], "vertex_count": 0, "segment_count": 0, "orientation": None,
            "signed_area_m2": 0.0, "area_m2": 0.0, "perimeter_m": 0.0, "bounds_m": None,
            "join_tolerance_m": None, "planarity_tolerance_m": None, "blockers": blockers,
            "warnings": [], "legal_judgement_generated": False, "permit_ready_certified": False}


def _finite(value):
    try:
        number = float(value)
    except Exception:
        return None
    return number if math.isfinite(number) else None


def _valid_tolerance(value):
    number = _finite(value)
    return number if number is not None and number > 0.0 else None


def _point(value):
    if not isinstance(value, dict):
        return None
    out = {}
    for key in ("x_m", "y_m", "z_m"):
        number = _finite(value.get(key))
        if number is None:
            return None
        out[key] = number
    return out


def _dist(a, b):
    return math.hypot(a["x_m"] - b["x_m"], a["y_m"] - b["y_m"])


def _area(pts):
    return 0.5 * sum(pts[i]["x_m"] * pts[(i + 1) % len(pts)]["y_m"] - pts[(i + 1) % len(pts)]["x_m"] * pts[i]["y_m"] for i in range(len(pts)))


def _seg_key(a, b, tol):
    qa = (round(a["x_m"] / tol), round(a["y_m"] / tol)); qb = (round(b["x_m"] / tol), round(b["y_m"] / tol))
    return (qa, qb)


def _orient(a, b, c):
    return (b["x_m"] - a["x_m"]) * (c["y_m"] - a["y_m"]) - (b["y_m"] - a["y_m"]) * (c["x_m"] - a["x_m"])


def _intersect(a, b, c, d, tol):
    def on(p, q, r):
        return (min(p["x_m"], r["x_m"]) - tol <= q["x_m"] <= max(p["x_m"], r["x_m"]) + tol and
                min(p["y_m"], r["y_m"]) - tol <= q["y_m"] <= max(p["y_m"], r["y_m"]) + tol and
                abs(_orient(p, q, r)) <= tol)
    o1, o2, o3, o4 = _orient(a, b, c), _orient(a, b, d), _orient(c, d, a), _orient(c, d, b)
    if o1 * o2 < -tol and o3 * o4 < -tol:
        return True
    return any([on(a, c, b), on(a, d, b), on(c, a, d), on(c, b, d)])


def build_site_boundary_geometry(extracted_area_boundary, join_tolerance_m=0.005, planarity_tolerance_m=0.005):
    join_tolerance_m = _valid_tolerance(join_tolerance_m)
    planarity_tolerance_m = _valid_tolerance(planarity_tolerance_m)
    result = _empty()
    result["join_tolerance_m"] = join_tolerance_m
    result["planarity_tolerance_m"] = planarity_tolerance_m
    if join_tolerance_m is None or planarity_tolerance_m is None:
        result["blockers"].append({"failure_code": "invalid_site_boundary_geometry_tolerance"})
        return result

    src = extracted_area_boundary or {}
    if src.get("complete") is not True:
        result["blockers"] = list(src.get("blockers") or [{"failure_code": "site_boundary_geometry_missing"}])
        return result
    loops = src.get("loops") or []
    if len(loops) != 1:
        result["blockers"].append({"failure_code": "site_boundary_area_multiple_loops_unsupported", "loop_count": len(loops)})
        return result
    z_diff = _finite(src.get("maximum_z_difference_m"))
    if z_diff is None or z_diff > planarity_tolerance_m:
        result["blockers"].append({"failure_code": "site_boundary_area_nonplanar", "maximum_z_difference_m": src.get("maximum_z_difference_m")})
        return result

    segments = loops[0].get("segments") or []
    if len(segments) < 3:
        result["blockers"].append({"failure_code": "site_boundary_open_loop"})
        return result
    pts = []
    seen = set()
    for index, segment in enumerate(segments):
        if segment.get("curve_type") != "Line":
            result["blockers"].append({"failure_code": "unsupported_site_boundary_curve_type", "curve_type": segment.get("curve_type"), "segment_index": index})
            return result
        start = _point(segment.get("start")); end = _point(segment.get("end"))
        if start is None or end is None:
            result["blockers"].append({"failure_code": "invalid_site_boundary_segment_coordinates", "segment_index": index})
            return result
        if _dist(start, end) <= 1e-12:
            result["blockers"].append({"failure_code": "site_boundary_zero_length_segment", "segment_index": index})
            return result
        if _dist(start, end) < join_tolerance_m:
            result["blockers"].append({"failure_code": "site_boundary_short_segment", "segment_index": index})
            return result
        key = _seg_key(start, end, join_tolerance_m); reverse_key = _seg_key(end, start, join_tolerance_m)
        if key in seen:
            result["blockers"].append({"failure_code": "site_boundary_duplicate_segment", "segment_index": index})
            return result
        if reverse_key in seen:
            result["blockers"].append({"failure_code": "site_boundary_duplicate_segment", "segment_index": index, "reverse": True})
            return result
        seen.add(key); pts.append({"x_m": start["x_m"], "y_m": start["y_m"]})
        if index < len(segments) - 1:
            next_start = _point((segments[index + 1] or {}).get("start"))
            if next_start is None:
                result["blockers"].append({"failure_code": "invalid_site_boundary_segment_coordinates", "segment_index": index + 1})
                return result
            if _dist(end, next_start) > join_tolerance_m:
                result["blockers"].append({"failure_code": "site_boundary_disconnected_segments", "segment_index": index})
                return result
    last_end = _point(segments[-1].get("end")); first_start = _point(segments[0].get("start"))
    if last_end is None or first_start is None:
        result["blockers"].append({"failure_code": "invalid_site_boundary_segment_coordinates"})
        return result
    if _dist(last_end, first_start) > join_tolerance_m:
        result["blockers"].append({"failure_code": "site_boundary_open_loop"})
        return result

    vertex_keys = set()
    for index, point in enumerate(pts):
        key = (round(point["x_m"] / join_tolerance_m), round(point["y_m"] / join_tolerance_m))
        if key in vertex_keys:
            result["blockers"].append({"failure_code": "site_boundary_repeated_vertex", "vertex_index": index})
            return result
        vertex_keys.add(key)
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            if abs(i - j) <= 1 or {i, j} == {0, len(pts) - 1}:
                continue
            if _intersect(pts[i], pts[(i + 1) % len(pts)], pts[j], pts[(j + 1) % len(pts)], join_tolerance_m):
                result["blockers"].append({"failure_code": "site_boundary_self_intersection", "segment_index": i, "other_segment_index": j})
                return result
    signed = _area(pts)
    if abs(signed) <= 1e-12:
        result["blockers"].append({"failure_code": "site_boundary_zero_area"})
        return result
    if signed < 0:
        pts = list(reversed(pts)); signed = -signed
    start_index = min(range(len(pts)), key=lambda i: (pts[i]["x_m"], pts[i]["y_m"]))
    pts = pts[start_index:] + pts[:start_index]
    perimeter = sum(math.hypot(pts[i]["x_m"] - pts[(i + 1) % len(pts)]["x_m"], pts[i]["y_m"] - pts[(i + 1) % len(pts)]["y_m"]) for i in range(len(pts)))
    result.update({"available": True, "complete": True, "outer_loop": pts, "vertex_count": len(pts),
                   "segment_count": len(pts), "orientation": "counter_clockwise", "signed_area_m2": signed,
                   "area_m2": signed, "perimeter_m": perimeter,
                   "bounds_m": {"min_x": min(p["x_m"] for p in pts), "min_y": min(p["y_m"] for p in pts),
                                  "max_x": max(p["x_m"] for p in pts), "max_y": max(p["y_m"] for p in pts)}})
    return result
