"""Pure-Python grid accumulation for complete unified time-shadow slices.

This is a 30-minute (or configured slice interval) numerical approximation,
not a permit-certified legal judgement. Revit-native geometry has already been
unified before this explicit calculation-data-model boundary.
"""
import math
from array import array

from shadow_performance import get_process_memory_snapshot, select_duration_chunk_size

METHOD = "grid_trapezoidal_time_integration_v1"


def integrate_shadow_states_trapezoidal(states, sample_minutes):
    """Integrate boolean shadow samples using the production duration semantics."""
    if len(states) != len(sample_minutes) or len(states) < 2:
        raise ValueError("states and sample_minutes must have matching lengths of at least two")
    intervals = [float(sample_minutes[i + 1]) - float(sample_minutes[i])
                 for i in range(len(sample_minutes) - 1)]
    if any(value <= 0.0 for value in intervals):
        raise ValueError("sample_minutes must be strictly increasing")
    return sum(intervals[i] * (float(states[i]) + float(states[i + 1])) / 2.0
               for i in range(len(intervals)))


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


BOUNDARY_EPSILON_M = 1e-9


def _bbox(points):
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return (min(xs) - BOUNDARY_EPSILON_M, min(ys) - BOUNDARY_EPSILON_M,
            max(xs) + BOUNDARY_EPSILON_M, max(ys) + BOUNDARY_EPSILON_M)


def _compile_slice_polygons(polygons):
    groups = {}
    for polygon in polygons:
        points = tuple((float(p["x"]), float(p["y"])) for p in polygon.get("points_m", []))
        if len(points) < 3: continue
        groups.setdefault(polygon.get("component_index", polygon.get("classification_group_key", 0)), []).append((polygon.get("role"), points, _bbox(points)))
    return tuple((
        tuple((points, bounds) for role, points, bounds in loops if role == "outer"),
        tuple((points, bounds) for role, points, bounds in loops if role == "inner"),
    ) for loops in groups.values())


def _bbox_contains(bounds, x, y):
    return bounds[0] <= x <= bounds[2] and bounds[1] <= y <= bounds[3]


def _compiled_slice_contains(compiled_polygons, x, y, bbox_pruning=True, counters=None):
    for outers, inners in compiled_polygons:
        outer_inside = False
        for outer, bounds in outers:
            if bbox_pruning and not _bbox_contains(bounds, x, y):
                if counters is not None: counters[0] += 1
                continue
            if counters is not None: counters[1] += 1
            if _inside_loop(x, y, outer):
                outer_inside = True
                break
        if not outer_inside:
            continue
        inner_inside = False
        for inner, bounds in inners:
            if bbox_pruning and not _bbox_contains(bounds, x, y):
                if counters is not None: counters[0] += 1
                continue
            if counters is not None: counters[1] += 1
            if _inside_loop(x, y, inner):
                inner_inside = True
                break
        if not inner_inside:
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


def build_shadow_duration(unified_shadow_slices, settings=None, selected_accuracy_preset=None,
                          site_boundary_geometry=None, chunk_size=None, bbox_pruning=True,
                          memory_snapshot=None):
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

    compiled_slices = [_compile_slice_polygons(s.get("polygons") or []) for s in slices]
    snapshot = memory_snapshot if isinstance(memory_snapshot, dict) else get_process_memory_snapshot()
    chunk_policy = select_duration_chunk_size(snapshot, requested_chunk_size=chunk_size)
    selected_chunk = chunk_policy["selected_chunk_size"]
    durations = array("d")
    max_duration = 0.0; shadowed = 0; counters = [0, 0]
    for chunk_start in range(0, count, selected_chunk):
        chunk_end = min(count, chunk_start + selected_chunk)
        for index in range(chunk_start, chunk_end):
            iy, ix = divmod(index, nx)
            x = min_x + ix * resolution
            y = min_y + iy * resolution
            previous = _compiled_slice_contains(compiled_slices[0], x, y, bbox_pruning, counters)
            duration = 0.0
            for slice_index, interval in enumerate(intervals):
                current = _compiled_slice_contains(
                    compiled_slices[slice_index + 1], x, y, bbox_pruning, counters)
                duration += interval * (float(previous) + float(current)) / 2.0
                previous = current
            durations.append(duration)
            if duration > 0: shadowed += 1
            max_duration = max(max_duration, duration)
    grid = []
    for index, duration in enumerate(durations):
        iy, ix = divmod(index, nx)
        grid.append({"x_m": min_x + ix * resolution,
            "y_m": min_y + iy * resolution, "shadow_duration_minutes": duration})
    result.update({"available": True, "complete": True, "maximum_shadow_duration_minutes": max_duration,
        "shadowed_point_count": shadowed, "ready_for_equal_time_contour_generation": True,
        "duration_grid": grid,
        "grid_spec": {"x_count": nx, "y_count": ny, "origin_x_m": min_x,
            "origin_y_m": min_y, "resolution_m": resolution,
            "ordering": "row_major_y_then_x"},
        "engine_diagnostics": {
            "engine": "safe_duration_engine_v2_a",
            "compact_buffer_type": "array('d')",
            "compact_buffer_bytes": len(durations) * durations.itemsize,
            "per_point_states_list_used": False,
            "bbox_pruning_enabled": bool(bbox_pruning),
            "bbox_reject_count": counters[0],
            "containment_evaluation_count": counters[1],
            "chunk_count": int(math.ceil(float(count) / selected_chunk)),
            "memory_aware_chunk": chunk_policy,
        }})
    return result

_build_shadow_duration = build_shadow_duration
