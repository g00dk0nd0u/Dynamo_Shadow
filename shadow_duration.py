"""Pure-Python grid accumulation for complete unified time-shadow slices.

This is a 30-minute (or configured slice interval) numerical approximation,
not a permit-certified legal judgement. Revit-native geometry has already been
unified before this explicit calculation-data-model boundary.
"""
import math

METHOD = "grid_trapezoidal_time_integration_v1"


def _empty():
    return {"available": False, "complete": False, "method": METHOD,
        "temporal_step_minutes": None, "spatial_resolution_m": None,
        "grid_point_count": 0, "requested_grid_point_count": None,
        "maximum_grid_point_count": None, "maximum_shadow_duration_minutes": 0.0,
        "shadowed_point_count": 0, "ready_for_equal_time_contour_generation": False,
        "permit_ready_certified": False, "duration_grid": [], "grid_spec": None,
        "bounds_m": None, "bounds_sources": [], "site_boundary_bounds_included": False,
        "site_boundary_expansion_m": None, "boundary_evaluation_coverage_complete": False,
        "core_bounds_preflight": None, "boundary_bounds_preflight": None,
        "boundary_evaluation_blockers": [], "blockers": [],
        "warnings": ["Duration values are a grid/trapezoidal numerical approximation at the configured temporal interval."]}


def _minutes(value):
    parts = str(value or "").split(":")
    if len(parts) not in (2, 3): raise ValueError("invalid_true_solar_time")
    nums = [int(part) for part in parts]
    return nums[0] * 60.0 + nums[1] + (nums[2] / 60.0 if len(nums) == 3 else 0.0)


def _on_segment(x, y, a, b, eps=1e-9):
    cross = (x-a[0])*(b[1]-a[1])-(y-a[1])*(b[0]-a[0])
    return abs(cross) <= eps and min(a[0],b[0])-eps <= x <= max(a[0],b[0])+eps and min(a[1],b[1])-eps <= y <= max(a[1],b[1])+eps


def _inside_loop(x, y, points):
    inside = False
    for index, a in enumerate(points):
        b = points[(index + 1) % len(points)]
        if _on_segment(x, y, a, b): return True
        if (a[1] > y) != (b[1] > y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]: inside = not inside
    return inside


def _slice_contains(polygons, x, y):
    groups = {}
    for polygon in polygons:
        points = [(float(p["x"]), float(p["y"])) for p in polygon.get("points_m", [])]
        if len(points) < 3: continue
        groups.setdefault(polygon.get("component_index", polygon.get("classification_group_key", 0)), []).append((polygon.get("role"), points))
    for loops in groups.values():
        outers = [points for role, points in loops if role == "outer"]
        inners = [points for role, points in loops if role == "inner"]
        if any(_inside_loop(x, y, outer) for outer in outers) and not any(_inside_loop(x, y, inner) for inner in inners):
            return True
    return False


def _preflight_bounds(min_x, min_y, max_x, max_y, resolution, maximum):
    nx = int(math.ceil((max_x - min_x) / resolution)) + 1
    ny = int(math.ceil((max_y - min_y) / resolution)) + 1
    count = nx * ny
    return {
        "bounds_m": {"min_x": min_x, "min_y": min_y,
            "max_x": min_x + (nx - 1) * resolution,
            "max_y": min_y + (ny - 1) * resolution},
        "x_count": nx, "y_count": ny,
        "requested_grid_point_count": count,
        "maximum_grid_point_count": maximum,
        "within_point_limit": count <= maximum,
    }


def build_shadow_duration(unified_shadow_slices, settings=None, selected_accuracy_preset=None, site_boundary_geometry=None):
    result = _empty(); unified = unified_shadow_slices or {}
    slices = list(unified.get("slices") or [])
    if unified.get("complete") is not True or not slices or any(s.get("complete") is not True for s in slices):
        result["blockers"].append({"failure_code": "complete_unified_shadow_slices_required"}); return result
    normalized = (settings or {}).get("normalized") or settings or {}
    try:
        resolution = float(normalized.get("grid_resolution_m", 1.0)); margin = float(normalized.get("analysis_margin_m", 20.0))
        maximum = int(normalized.get("max_duration_grid_points", 250000))
        if resolution <= 0 or margin < 0 or maximum <= 0: raise ValueError()
        times = [_minutes(s.get("true_solar_time")) for s in slices]
        intervals = [times[i+1]-times[i] for i in range(len(times)-1)]
        if not intervals or any(value <= 0 for value in intervals): raise ValueError()
        points = [(float(p["x"]), float(p["y"])) for s in slices for polygon in s.get("polygons") or [] for p in polygon.get("points_m") or []]
        if not points or any(not math.isfinite(x) or not math.isfinite(y) for x, y in points): raise ValueError()
    except (TypeError, ValueError, KeyError, OverflowError):
        result["blockers"].append({"failure_code": "invalid_duration_input_or_settings"}); return result

    shadow_min_x, shadow_max_x = min(p[0] for p in points), max(p[0] for p in points)
    shadow_min_y, shadow_max_y = min(p[1] for p in points), max(p[1] for p in points)
    core_min_x, core_max_x = shadow_min_x - margin, shadow_max_x + margin
    core_min_y, core_max_y = shadow_min_y - margin, shadow_max_y + margin
    core_preflight = _preflight_bounds(core_min_x, core_min_y, core_max_x, core_max_y, resolution, maximum)

    boundary_sources = ["unified_shadow_polygons"]
    boundary_min_x, boundary_max_x = shadow_min_x, shadow_max_x
    boundary_min_y, boundary_max_y = shadow_min_y, shadow_max_y
    site_available = False
    if (site_boundary_geometry or {}).get("complete") is True and isinstance((site_boundary_geometry or {}).get("bounds_m"), dict):
        try:
            sb = site_boundary_geometry["bounds_m"]; expansion = 10.0
            boundary_min_x = min(boundary_min_x, float(sb["min_x"]) - expansion)
            boundary_min_y = min(boundary_min_y, float(sb["min_y"]) - expansion)
            boundary_max_x = max(boundary_max_x, float(sb["max_x"]) + expansion)
            boundary_max_y = max(boundary_max_y, float(sb["max_y"]) + expansion)
            boundary_sources.append("site_boundary_area_expanded_10m")
            site_available = True
        except (TypeError, ValueError, KeyError, OverflowError):
            site_available = False
    boundary_sources.append("analysis_margin")
    boundary_preflight = _preflight_bounds(boundary_min_x - margin, boundary_min_y - margin,
        boundary_max_x + margin, boundary_max_y + margin, resolution, maximum)

    result.update({"temporal_step_minutes": intervals[0] if all(abs(v-intervals[0]) <= 1e-9 for v in intervals) else None,
        "spatial_resolution_m": resolution,
        "maximum_grid_point_count": maximum,
        "core_bounds_preflight": core_preflight,
        "boundary_bounds_preflight": boundary_preflight,
        "site_boundary_expansion_m": 10.0 if site_available else None})

    if not core_preflight["within_point_limit"]:
        result.update({"grid_point_count": core_preflight["requested_grid_point_count"],
            "requested_grid_point_count": core_preflight["requested_grid_point_count"],
            "bounds_m": core_preflight["bounds_m"],
            "bounds_sources": ["unified_shadow_polygons", "analysis_margin"],
            "site_boundary_bounds_included": False,
            "boundary_evaluation_coverage_complete": False})
        result["blockers"].append({
            "failure_code": "max_duration_grid_points_exceeded",
            "requested_grid_point_count": core_preflight["requested_grid_point_count"],
            "max_duration_grid_points": maximum,
            "selected_accuracy_preset": selected_accuracy_preset,
            "grid_resolution_m": resolution,
            "sun_time_step_minutes": normalized.get("sun_time_step_minutes"),
            "automatic_accuracy_fallback_used": False,
        }); return result

    use_boundary = site_available and boundary_preflight["within_point_limit"]
    chosen = boundary_preflight if use_boundary else core_preflight
    boundary_blockers = []
    if site_available and not boundary_preflight["within_point_limit"]:
        boundary_blockers.append({
            "failure_code": "site_boundary_evaluation_grid_points_exceeded",
            "requested_grid_point_count": boundary_preflight["requested_grid_point_count"],
            "maximum_grid_point_count": maximum,
            "automatic_accuracy_fallback_used": False,
        })

    bounds = chosen["bounds_m"]
    min_x, min_y = bounds["min_x"], bounds["min_y"]
    nx, ny, count = chosen["x_count"], chosen["y_count"], chosen["requested_grid_point_count"]
    result.update({"grid_point_count": count, "requested_grid_point_count": count,
        "bounds_sources": boundary_sources if use_boundary else ["unified_shadow_polygons", "analysis_margin"],
        "site_boundary_bounds_included": use_boundary,
        "boundary_evaluation_coverage_complete": (not site_available) or use_boundary,
        "boundary_evaluation_blockers": boundary_blockers,
        "bounds_m": bounds})

    grid = []; max_duration = 0.0; shadowed = 0
    for iy in range(ny):
        y = min_y + iy * resolution
        for ix in range(nx):
            x = min_x + ix * resolution
            states = [_slice_contains(s.get("polygons") or [], x, y) for s in slices]
            duration = sum(intervals[i] * (float(states[i])+float(states[i+1])) / 2.0 for i in range(len(intervals)))
            if duration > 0: shadowed += 1
            max_duration = max(max_duration, duration)
            grid.append({"x_m": x, "y_m": y, "shadow_duration_minutes": duration})
    result.update({"available": True, "complete": True, "maximum_shadow_duration_minutes": max_duration,
        "shadowed_point_count": shadowed, "ready_for_equal_time_contour_generation": True,
        "duration_grid": grid,
        "grid_spec": {"x_count": nx, "y_count": ny, "origin_x_m": min_x,
            "origin_y_m": min_y, "resolution_m": resolution,
            "ordering": "row_major_y_then_x"}})
    return result

_build_shadow_duration = build_shadow_duration
