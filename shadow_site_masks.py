"""Pure-Python 5m/10m point-distance masks for duration grids."""
import math

METHOD = "point_to_area_boundary_distance_v1"
ZONES = ["inside_site", "on_site_boundary", "outside_0_to_5m", "near_5_to_10m", "far_over_10m"]


def _empty(blocker=None):
    return {"available": False, "complete": False, "method": METHOD, "duration_grid_point_count": 0,
            "zone_counts": {zone: 0 for zone in ZONES}, "near": {"available": False}, "far": {"available": False},
            "boundary_dependent_ready": False, "legal_judgement_generated": False,
            "ordinance_selection_certified": False, "permit_ready_certified": False,
            "blockers": [] if blocker is None else [{"failure_code": blocker}], "warnings": []}


def _finite(value):
    try:
        number = float(value)
    except Exception:
        return None
    return number if math.isfinite(number) else None


def _dist_point_seg(point, start, end):
    vx, vy = end[0] - start[0], end[1] - start[1]
    wx, wy = point[0] - start[0], point[1] - start[1]
    denominator = vx * vx + vy * vy
    t = 0.0 if denominator == 0 else max(0.0, min(1.0, (wx * vx + wy * vy) / denominator))
    nearest = (start[0] + t * vx, start[1] + t * vy)
    return math.hypot(point[0] - nearest[0], point[1] - nearest[1])


def _inside(point, polygon, tolerance):
    x, y = point
    inside = False
    for index, start in enumerate(polygon):
        end = polygon[(index + 1) % len(polygon)]
        if _dist_point_seg(point, start, end) <= tolerance:
            return None
        if (start[1] > y) != (end[1] > y) and x < (end[0] - start[0]) * (y - start[1]) / (end[1] - start[1]) + start[0]:
            inside = not inside
    return inside


def _classify(point, polygon, tolerance):
    distance = min(_dist_point_seg(point, polygon[index], polygon[(index + 1) % len(polygon)]) for index in range(len(polygon)))
    inside = _inside(point, polygon, tolerance)
    if inside is None:
        return "on_site_boundary", distance
    if inside:
        return "inside_site", distance
    if distance <= 5.0 + tolerance:
        return "outside_0_to_5m", distance
    if distance <= 10.0 + tolerance:
        return "near_5_to_10m", distance
    return "far_over_10m", distance


def _best(current, point):
    if current is None:
        return point
    key = lambda item: (-item["maximum_shadow_duration_minutes"], item["point"]["x_m"], item["point"]["y_m"])
    return point if key(point) < key(current) else current


def _valid_polygon(site_boundary_geometry):
    if not (site_boundary_geometry or {}).get("complete"):
        return None
    polygon = []
    for point in site_boundary_geometry.get("outer_loop") or []:
        x = _finite((point or {}).get("x_m")); y = _finite((point or {}).get("y_m"))
        if x is None or y is None:
            return None
        polygon.append((x, y))
    return polygon if len(polygon) >= 3 else None


def build_measurement_masks(shadow_duration, site_boundary_geometry, distance_tolerance_m=1e-6):
    tolerance = _finite(distance_tolerance_m)
    if tolerance is None or tolerance < 0.0:
        return _empty("invalid_measurement_mask_distance_tolerance")
    polygon = _valid_polygon(site_boundary_geometry)
    if polygon is None:
        return _empty("site_boundary_geometry_required")
    if not (shadow_duration or {}).get("complete"):
        return _empty("complete_shadow_duration_required")
    grid = shadow_duration.get("duration_grid") or []
    if not grid:
        return _empty("shadow_duration_grid_missing")

    result = _empty()
    result.update({"available": True, "complete": True, "boundary_dependent_ready": True,
                   "distance_tolerance_m": tolerance, "duration_grid_point_count": len(grid)})
    near = None
    far = None
    for index, grid_point in enumerate(grid):
        x = _finite((grid_point or {}).get("x_m")); y = _finite((grid_point or {}).get("y_m"))
        duration = _finite((grid_point or {}).get("shadow_duration_minutes"))
        if x is None or y is None or duration is None:
            invalid = _empty()
            invalid["blockers"].append({"failure_code": "invalid_shadow_duration_grid_point", "point_index": index})
            return invalid
        zone, distance = _classify((x, y), polygon, tolerance)
        result["zone_counts"][zone] += 1
        candidate = {"available": True, "maximum_shadow_duration_minutes": duration,
                     "point": {"x_m": x, "y_m": y, "distance_from_site_boundary_m": distance}}
        if zone == "near_5_to_10m":
            near = _best(near, candidate)
        if zone == "far_over_10m":
            far = _best(far, candidate)
    result["near"] = near or {"available": False}
    result["far"] = far or {"available": False}
    return result
