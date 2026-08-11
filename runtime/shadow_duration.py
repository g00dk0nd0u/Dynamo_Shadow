"""Pure-Python grid accumulation for complete unified time-shadow slices.

This is a 30-minute (or configured slice interval) numerical approximation,
not a permit-certified legal judgement. Revit-native geometry has already been
unified before this explicit calculation-data-model boundary.
"""
import math
from array import array

from shadow_performance import get_process_memory_snapshot, select_duration_chunk_size

METHOD = "grid_trapezoidal_time_integration_v1"
LARGE_GRID_HARD_POINT_CAP = 2000000
LARGE_GRID_HARD_WORK_CAP = 100000000
LARGE_GRID_FALLBACK_MEMORY_BUDGET_BYTES = 64 * 1024 * 1024
DEFAULT_TILE_SIZE_CELLS = 32


class DurationField(object):
    """Internal-only row-major scalar field; never place this object in OUT."""
    def __init__(self, values, grid_spec, active_metadata):
        self.values = values
        self.grid_spec = dict(grid_spec)
        self.logical_point_count = len(values)
        self.active_tile_metadata = dict(active_metadata)


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
                          memory_snapshot=None, return_internal=False, sparse_tiles=True,
                          tile_size_cells=DEFAULT_TILE_SIZE_CELLS):
    result = _empty(); unified = unified_shadow_slices or {}
    slices = list(unified.get("slices") or [])
    if unified.get("complete") is not True or not slices or any(s.get("complete") is not True for s in slices):
        result["blockers"].append({"failure_code": "complete_unified_shadow_slices_required"}); return result
    normalized = (settings or {}).get("normalized") or settings or {}
    try:
        resolution = float(normalized.get("grid_resolution_m", 1.0)); margin = float(normalized.get("analysis_margin_m", 20.0))
        maximum = int(normalized.get("max_duration_grid_points", 250000))
        tile_size_cells = int(tile_size_cells)
        if resolution <= 0 or margin < 0 or maximum <= 0 or tile_size_cells <= 0: raise ValueError()
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

    large_path_enabled = maximum >= 250000
    if (core_preflight["requested_grid_point_count"] > LARGE_GRID_HARD_POINT_CAP or
            (not large_path_enabled and not core_preflight["within_point_limit"])):
        result.update({"grid_point_count": core_preflight["requested_grid_point_count"],
            "requested_grid_point_count": core_preflight["requested_grid_point_count"],
            "bounds_m": core_preflight["bounds_m"],
            "bounds_sources": ["unified_shadow_polygons", "analysis_margin"],
            "site_boundary_bounds_included": False,
            "boundary_evaluation_coverage_complete": False})
        result["blockers"].append({
            "failure_code": ("large_grid_memory_budget_exceeded" if large_path_enabled
                             else "max_duration_grid_points_exceeded"),
            "requested_grid_point_count": core_preflight["requested_grid_point_count"],
            "max_duration_grid_points": maximum,
            "selected_accuracy_preset": selected_accuracy_preset,
            "grid_resolution_m": resolution,
            "sun_time_step_minutes": normalized.get("sun_time_step_minutes"),
            "automatic_accuracy_fallback_used": False,
        }); return result

    use_boundary = site_available and (boundary_preflight["within_point_limit"] or
        (large_path_enabled and boundary_preflight["requested_grid_point_count"] <= LARGE_GRID_HARD_POINT_CAP))
    chosen = boundary_preflight if use_boundary else core_preflight
    boundary_blockers = []
    if site_available and not use_boundary:
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
    tx_count = int(math.ceil(float(nx) / tile_size_cells))
    ty_count = int(math.ceil(float(ny) / tile_size_cells))
    all_tiles = [(ty, tx) for ty in range(ty_count) for tx in range(tx_count)]
    active_tiles = set()
    if sparse_tiles:
        # A tile owns grid-point indices [tile*size, min((tile+1)*size, count)).
        # Expanded polygon bboxes are conservative candidate selectors only.
        for compiled in compiled_slices:
            for outers, inners in compiled:
                for _points, bbox in tuple(outers) + tuple(inners):
                    ix0 = max(0, int(math.floor((bbox[0] - min_x) / resolution)))
                    iy0 = max(0, int(math.floor((bbox[1] - min_y) / resolution)))
                    ix1 = min(nx - 1, int(math.ceil((bbox[2] - min_x) / resolution)))
                    iy1 = min(ny - 1, int(math.ceil((bbox[3] - min_y) / resolution)))
                    if ix0 <= ix1 and iy0 <= iy1:
                        for ty in range(iy0 // tile_size_cells, iy1 // tile_size_cells + 1):
                            for tx in range(ix0 // tile_size_cells, ix1 // tile_size_cells + 1):
                                active_tiles.add((ty, tx))
    else:
        active_tiles.update(all_tiles)
    ordered_tiles = sorted(active_tiles)
    active_count = sum((min(ny, (ty + 1) * tile_size_cells) - ty * tile_size_cells) *
                       (min(nx, (tx + 1) * tile_size_cells) - tx * tile_size_cells)
                       for ty, tx in ordered_tiles)
    snapshot = memory_snapshot if isinstance(memory_snapshot, dict) else get_process_memory_snapshot()
    compact_bytes = count * array("d").itemsize
    available = snapshot.get("available_physical_memory_bytes")
    memory_budget = LARGE_GRID_FALLBACK_MEMORY_BUDGET_BYTES
    if isinstance(available, (int, float)) and available >= 0:
        memory_budget = min(LARGE_GRID_FALLBACK_MEMORY_BUDGET_BYTES, int(available * 0.25))
    estimated_memory = compact_bytes + active_count // 8 + len(ordered_tiles) * 32
    estimated_work = active_count * len(slices)
    if count > maximum and estimated_memory > memory_budget:
        result["blockers"].append({"failure_code": "large_grid_memory_budget_exceeded"})
        result["engine_diagnostics"] = {"large_grid_preflight_status": "blocked_memory",
            "estimated_working_memory_bytes": estimated_memory, "memory_budget_bytes": memory_budget}
        return (result, None) if return_internal else result
    if count > maximum and estimated_work > LARGE_GRID_HARD_WORK_CAP:
        result["blockers"].append({"failure_code": "large_grid_work_budget_exceeded"})
        result["engine_diagnostics"] = {"large_grid_preflight_status": "blocked_work",
            "estimated_working_memory_bytes": estimated_memory, "memory_budget_bytes": memory_budget}
        return (result, None) if return_internal else result
    chunk_policy = select_duration_chunk_size(snapshot, requested_chunk_size=chunk_size)
    selected_chunk = chunk_policy["selected_chunk_size"]
    durations = array("d", [0.0]) * count
    max_duration = 0.0; shadowed = 0; counters = [0, 0]
    def active_index_stream():
        for ty, tx in ordered_tiles:
            for iy in range(ty * tile_size_cells, min(ny, (ty + 1) * tile_size_cells)):
                for ix in range(tx * tile_size_cells, min(nx, (tx + 1) * tile_size_cells)):
                    yield iy * nx + ix
    chunk = []
    for streamed_index in active_index_stream():
        chunk.append(streamed_index)
        if len(chunk) < selected_chunk:
            continue
        for index in chunk:
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
            durations[index] = duration
            if duration > 0: shadowed += 1
            max_duration = max(max_duration, duration)
        chunk = []
    for index in chunk:
        iy, ix = divmod(index, nx)
        x = min_x + ix * resolution; y = min_y + iy * resolution
        previous = _compiled_slice_contains(compiled_slices[0], x, y, bbox_pruning, counters)
        duration = 0.0
        for slice_index, interval in enumerate(intervals):
            current = _compiled_slice_contains(compiled_slices[slice_index + 1], x, y, bbox_pruning, counters)
            duration += interval * (float(previous) + float(current)) / 2.0
            previous = current
        durations[index] = duration
        if duration > 0: shadowed += 1
        max_duration = max(max_duration, duration)
    materialized = count <= maximum
    grid = []
    if materialized:
        for index, duration in enumerate(durations):
            iy, ix = divmod(index, nx)
            grid.append({"x_m": min_x + ix * resolution,
                "y_m": min_y + iy * resolution, "shadow_duration_minutes": duration})
    grid_spec = {"x_count": nx, "y_count": ny, "origin_x_m": min_x,
        "origin_y_m": min_y, "resolution_m": resolution, "ordering": "row_major_y_then_x"}
    total_tiles = len(all_tiles); selected_tiles = len(ordered_tiles)
    active_metadata = {"tile_size_cells": tile_size_cells, "active_tiles": ordered_tiles,
        "active_evaluation_point_count": active_count}
    field = DurationField(durations, grid_spec, active_metadata)
    result.update({"available": True, "complete": True, "maximum_shadow_duration_minutes": max_duration,
        "shadowed_point_count": shadowed, "ready_for_equal_time_contour_generation": True,
        "duration_grid": grid, "grid_spec": grid_spec,
        "storage_mode": "materialized_small_v1" if materialized else "compact_large_v1",
        "duration_grid_materialized": materialized,
        "engine_diagnostics": {
            "engine": "safe_duration_engine_v2_a",
            "compact_buffer_type": "array('d')",
            "compact_buffer_bytes": len(durations) * durations.itemsize,
            "storage_mode": "materialized_small_v1" if materialized else "compact_large_v1",
            "duration_grid_materialized": materialized,
            "logical_grid_point_count": count,
            "active_evaluation_point_count": active_count,
            "implicit_zero_point_count": count - active_count,
            "tile_size_cells": tile_size_cells, "total_logical_tile_count": total_tiles,
            "selected_active_tile_count": selected_tiles, "skipped_tile_count": total_tiles-selected_tiles,
            "active_tile_ratio": float(selected_tiles) / total_tiles if total_tiles else 0.0,
            "halo_point_or_cell_count": 0,
            "large_grid_preflight_status": "passed" if not materialized else "not_required_small",
            "estimated_working_memory_bytes": estimated_memory, "memory_budget_bytes": memory_budget,
            "dense_candidate_containment_estimate": count * len(slices),
            "actual_containment_evaluation_count": counters[1],
            "containment_reduction_ratio": 1.0 - float(active_count) / count if count else 0.0,
            "per_point_states_list_used": False,
            "bbox_pruning_enabled": bool(bbox_pruning),
            "bbox_reject_count": counters[0],
            "containment_evaluation_count": counters[1],
            "chunk_count": int(math.ceil(float(active_count) / selected_chunk)),
            "chunk_role": "execution_partition",
            "end_to_end_bounded_memory": False,
            "full_compact_duration_buffer_materialized": True,
            "legacy_duration_grid_materialized": materialized,
            "memory_aware_chunk": chunk_policy,
        }})
    return (result, field) if return_internal else result

_build_shadow_duration = build_shadow_duration
