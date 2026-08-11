"""Pure-Python 5m/10m site distance display contours."""
import math

from shadow_contours import _cell_segments, _stitch
from shadow_site_masks import _dist_point_seg, _inside

METHOD = "signed_distance_grid_marching_squares_v1"
DISTANCE_LEVELS_M = [5.0, 10.0]
WARNING_APPROX = "Distance contours are grid-based display geometry, not exact statutory offset curves."
WARNING_NOT_GENERATED = "site_distance_contour_not_generated"
MAX_SITE_DISTANCE_GRID_POINTS = 250000


def _empty(blocker=None):
    return {
        "available": False,
        "complete": False,
        "method": METHOD,
        "source": {"site_boundary_method": None, "grid_source": "shadow_duration", "spatial_resolution_m": None},
        "approximation": {"grid_based": True, "linear_interpolation": True, "smoothing_applied": False, "polygon_offset_used": False},
        "requested_distances_m": list(DISTANCE_LEVELS_M),
        "generated_distances_m": [],
        "contour_count": 0,
        "closed_contour_count": 0,
        "open_contour_count": 0,
        "contours": [],
        "ready_for_revit_preview": False,
        "legal_judgement_generated": False,
        "ordinance_selection_certified": False,
        "permit_ready_certified": False,
        "blockers": [] if blocker is None else [{"failure_code": blocker}],
        "warnings": [WARNING_APPROX],
    }


def _finite(value):
    try:
        number = float(value)
    except Exception:
        return None
    return number if math.isfinite(number) else None


def _valid_polygon(site_boundary_geometry):
    if not (site_boundary_geometry or {}).get("complete"):
        return None
    polygon = []
    for point in site_boundary_geometry.get("outer_loop") or []:
        x = _finite((point or {}).get("x_m"))
        y = _finite((point or {}).get("y_m"))
        if x is None or y is None:
            return None
        polygon.append((x, y))
    return polygon if len(polygon) >= 3 else None


def _signed_distance(point, polygon, tolerance):
    distance = min(_dist_point_seg(point, polygon[index], polygon[(index + 1) % len(polygon)]) for index in range(len(polygon)))
    inside = _inside(point, polygon, tolerance)
    if inside is None:
        return 0.0
    return -distance if inside else distance


def _positive_grid_count(value):
    if isinstance(value, bool):
        raise ValueError("boolean_grid_count")
    numeric = float(value)
    if not math.isfinite(numeric) or numeric != int(numeric):
        raise ValueError("invalid_grid_count")
    result = int(numeric)
    if result < 2:
        raise ValueError("invalid_grid_count")
    return result


def _grid_spec(spec):
    nx = _positive_grid_count(spec["x_count"])
    ny = _positive_grid_count(spec["y_count"])
    ox = float(spec["origin_x_m"])
    oy = float(spec["origin_y_m"])
    resolution = float(spec["resolution_m"])
    if (not math.isfinite(ox) or not math.isfinite(oy) or not math.isfinite(resolution)
            or resolution <= 0.0 or spec.get("ordering") != "row_major_y_then_x"):
        raise ValueError("invalid_grid_spec")
    if not math.isfinite(ox + (nx - 1) * resolution) or not math.isfinite(oy + (ny - 1) * resolution):
        raise ValueError("invalid_grid_extent")
    return nx, ny, ox, oy, resolution


def _validate_grid_coordinates(grid, nx, ny, ox, oy, resolution):
    values = []
    for index, item in enumerate(grid):
        x = _finite((item or {}).get("x_m"))
        y = _finite((item or {}).get("y_m"))
        if x is None or y is None:
            raise ValueError("invalid_duration_grid_coordinates")
        expected_x = ox + (index % nx) * resolution
        expected_y = oy + (index // nx) * resolution
        if abs(x - expected_x) > max(1e-6, resolution * 1e-9) or abs(y - expected_y) > max(1e-6, resolution * 1e-9):
            raise ValueError("invalid_duration_grid_coordinates")
        values.append((x, y))
    return values


def build_site_distance_contours(shadow_duration, site_boundary_geometry, distance_tolerance_m=1e-6,
                                 duration_field=None, maximum_segment_count=2000000):
    tolerance = _finite(distance_tolerance_m)
    if tolerance is None or tolerance < 0.0:
        return _empty("invalid_site_distance_tolerance")
    polygon = _valid_polygon(site_boundary_geometry)
    if polygon is None:
        if (site_boundary_geometry or {}).get("complete"):
            return _empty("invalid_site_boundary_coordinates")
        return _empty("site_boundary_geometry_required")
    duration = shadow_duration or {}
    if duration.get("complete") is not True:
        return _empty("complete_shadow_duration_required")
    if duration.get("boundary_evaluation_coverage_complete") is not True:
        result = _empty("boundary_evaluation_coverage_complete_required")
        blockers = list(duration.get("boundary_evaluation_blockers") or [])
        if blockers:
            result["blockers"] = blockers
        return result
    spec = duration.get("grid_spec") or {}
    try:
        nx, ny, ox, oy, resolution = _grid_spec(spec)
    except Exception:
        return _empty("duration_grid_spec_missing_or_invalid")
    grid = duration.get("duration_grid") or []
    compact = getattr(duration_field, "values", None)
    if compact is None:
        if len(grid) != nx * ny:
            return _empty("duration_grid_size_mismatch")
        try:
            _validate_grid_coordinates(grid, nx, ny, ox, oy, resolution)
        except Exception:
            return _empty("invalid_duration_grid_coordinates")
    result = _empty()
    result.update({
        "available": True,
        "complete": True,
        "source": {"site_boundary_method": (site_boundary_geometry or {}).get("method"), "grid_source": "shadow_duration", "spatial_resolution_m": resolution},
        "row_streaming": compact is not None,
    })
    contours = []
    generated = set()
    for level in DISTANCE_LEVELS_M:
        segments = []
        previous = [_signed_distance((ox + ix*resolution, oy), polygon, tolerance) for ix in range(nx)]
        for iy in range(ny - 1):
            y0 = oy + iy * resolution; y1 = y0 + resolution
            current = [_signed_distance((ox + ix*resolution, y1), polygon, tolerance) for ix in range(nx)]
            for ix in range(nx - 1):
                x0 = ox + ix * resolution; x1 = x0 + resolution
                corners = [(x0, y0, previous[ix]), (x1, y0, previous[ix+1]),
                           (x1, y1, current[ix+1]), (x0, y1, current[ix])]
                segments.extend(_cell_segments(corners, level))
                if len(segments) > maximum_segment_count:
                    return _empty("site_distance_contour_segment_budget_exceeded")
            previous = current
        lines = _stitch(segments)
        if not lines:
            result["warnings"].append({"warning_code": WARNING_NOT_GENERATED, "distance_m": level})
            continue
        generated.add(level)
        for line in lines:
            closed = len(line) > 2 and line[0] == line[-1]
            length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(line, line[1:]))
            contours.append({"distance_m": level, "contour_index": 0, "closed": closed,
                             "point_count": len(line), "length_m": length,
                             "points_m": [{"x": p[0], "y": p[1]} for p in line]})
    contours.sort(key=lambda c: (c["distance_m"], c["points_m"][0]["x"], c["points_m"][0]["y"], c["point_count"]))
    per_distance = {}
    for contour in contours:
        distance = contour["distance_m"]
        contour["contour_index"] = per_distance.get(distance, 0)
        per_distance[distance] = contour["contour_index"] + 1
    result.update({"generated_distances_m": sorted(generated), "contour_count": len(contours),
                   "closed_contour_count": sum(1 for c in contours if c["closed"]),
                   "open_contour_count": sum(1 for c in contours if not c["closed"]),
                   "contours": contours, "ready_for_revit_preview": True})
    return result


def build_site_distance_contours_from_site(site_boundary_geometry, resolution_m=1.0,
                                           maximum_grid_point_count=MAX_SITE_DISTANCE_GRID_POINTS,
                                           distance_tolerance_m=1e-6):
    """Build approximate outside distance contours without a shadow-duration grid."""
    tolerance = _finite(distance_tolerance_m)
    resolution = _finite(resolution_m)
    polygon = _valid_polygon(site_boundary_geometry)
    if polygon is None:
        return _empty("site_boundary_geometry_required")
    if tolerance is None or tolerance < 0.0 or resolution is None or resolution < 1.0:
        return _empty("invalid_site_distance_generated_grid_resolution")
    try:
        maximum = int(maximum_grid_point_count)
        if maximum <= 0 or maximum != float(maximum_grid_point_count):
            raise ValueError()
    except Exception:
        return _empty("invalid_site_distance_generated_grid_limit")
    margin = 10.0 + 2.0 * resolution
    min_x, max_x = min(p[0] for p in polygon), max(p[0] for p in polygon)
    min_y, max_y = min(p[1] for p in polygon), max(p[1] for p in polygon)
    ox = math.floor((min_x - margin) / resolution) * resolution
    oy = math.floor((min_y - margin) / resolution) * resolution
    end_x = math.ceil((max_x + margin) / resolution) * resolution
    end_y = math.ceil((max_y + margin) / resolution) * resolution
    nx = int(round((end_x - ox) / resolution)) + 1
    ny = int(round((end_y - oy) / resolution)) + 1
    count = nx * ny
    if count > maximum:
        result = _empty("site_distance_generated_grid_limit_exceeded")
        result["grid_spec"] = {"x_count": nx, "y_count": ny, "point_count": count,
                               "origin_x_m": ox, "origin_y_m": oy, "resolution_m": resolution,
                               "ordering": "row_major_y_then_x"}
        return result
    points = [(ox + ix * resolution, oy + iy * resolution)
              for iy in range(ny) for ix in range(nx)]
    signed_values = [_signed_distance(point, polygon, tolerance) for point in points]
    result = _empty()
    result.update({"available": True, "complete": True,
                   "source": {"site_boundary_method": site_boundary_geometry.get("method"),
                              "grid_source": "site_boundary_generated_grid",
                              "spatial_resolution_m": resolution},
                   "grid_spec": {"x_count": nx, "y_count": ny, "point_count": count,
                                 "origin_x_m": ox, "origin_y_m": oy, "resolution_m": resolution,
                                 "ordering": "row_major_y_then_x"}})
    result["approximation"]["exact_statutory_offset"] = False
    contours, generated = [], set()
    for level in DISTANCE_LEVELS_M:
        segments = []
        for iy in range(ny - 1):
            for ix in range(nx - 1):
                indices = (iy * nx + ix, iy * nx + ix + 1,
                           (iy + 1) * nx + ix + 1, (iy + 1) * nx + ix)
                corners = [(points[i][0], points[i][1], signed_values[i]) for i in indices]
                segments.extend(_cell_segments(corners, level))
        lines = _stitch(segments)
        if not lines:
            result["complete"] = False
            result["blockers"].append({"failure_code": "site_distance_{0}m_contour_missing".format(int(level))})
            continue
        generated.add(level)
        for line in lines:
            closed = len(line) > 2 and line[0] == line[-1]
            length = sum(math.hypot(b[0]-a[0], b[1]-a[1]) for a, b in zip(line, line[1:]))
            contours.append({"distance_m": level, "contour_index": 0, "closed": closed,
                             "point_count": len(line), "length_m": length,
                             "points_m": [{"x": p[0], "y": p[1]} for p in line]})
            if not closed:
                result["complete"] = False
                result["blockers"].append({"failure_code": "site_distance_open_contour_unsupported_for_reverse_shadow",
                                           "distance_m": level})
    contours.sort(key=lambda c: (c["distance_m"], c["points_m"][0]["x"], c["points_m"][0]["y"], c["point_count"]))
    indices = {}
    for contour in contours:
        level = contour["distance_m"]
        contour["contour_index"] = indices.get(level, 0)
        indices[level] = contour["contour_index"] + 1
    result.update({"generated_distances_m": sorted(generated), "contour_count": len(contours),
                   "closed_contour_count": sum(c["closed"] for c in contours),
                   "open_contour_count": sum(not c["closed"] for c in contours),
                   "contours": contours, "ready_for_revit_preview": False})
    return result
