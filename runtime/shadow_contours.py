"""Deterministic pure-Python equal-time contour generation v1."""
import math
from shadow_utils import _is_sequence

METHOD = "marching_squares_linear_interpolation_v1"
SOURCE_METHOD = "grid_trapezoidal_time_integration_v1"
EPSILON = 1e-9
FIXED_HARD_SEGMENT_CAP = 100000
CONSERVATIVE_BYTES_PER_SEGMENT = 512
FALLBACK_SEGMENT_MEMORY_BUDGET_BYTES = 64 * 1024 * 1024


def _effective_segment_cap(duration, requested_cap=None):
    diagnostics = (duration or {}).get("engine_diagnostics") or {}
    budget = diagnostics.get("memory_budget_bytes")
    if not isinstance(budget, (int, float)) or budget <= 0:
        budget = FALLBACK_SEGMENT_MEMORY_BUDGET_BYTES
    memory_cap = max(1, int(budget) // CONSERVATIVE_BYTES_PER_SEGMENT)
    requested = FIXED_HARD_SEGMENT_CAP if requested_cap is None else max(1, int(requested_cap))
    return min(FIXED_HARD_SEGMENT_CAP, memory_cap, requested)


def _empty():
    return {"available": False, "complete": False, "method": METHOD,
            "source_duration_method": SOURCE_METHOD,
            "requested_levels_minutes": [], "generated_levels_minutes": [],
            "contour_count": 0, "closed_contour_count": 0,
            "open_contour_count": 0, "contours": [], "blockers": [],
            "warnings": ["Contour levels are technical/diagnostic time levels, not statutory thresholds."],
            "permit_ready_certified": False}


def _block(result, code):
    result["blockers"].append({"failure_code": code})
    return result


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


def _levels(settings, maximum):
    normalized = (settings or {}).get("normalized") or settings or {}
    invalid = set((settings or {}).get("invalid_keys") or [])
    if invalid.intersection({"equal_time_contour_interval_minutes",
                             "equal_time_contour_levels_minutes",
                             "max_equal_time_contour_levels"}):
        raise ValueError("invalid")
    limit = int(normalized.get("max_equal_time_contour_levels", 100))
    explicit = normalized.get("equal_time_contour_levels_minutes")
    if explicit is not None:
        if not _is_sequence(explicit):
            raise ValueError("invalid")
        values = [float(value) for value in list(explicit)]
    else:
        interval = float(normalized.get("equal_time_contour_interval_minutes", 60.0))
        if not math.isfinite(interval) or interval <= 0:
            raise ValueError("invalid")
        values = [interval * index for index in range(1, int(maximum // interval) + 1)]
    if limit <= 0 or any(not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError("invalid")
    values = sorted(set(values))
    if len(values) > limit:
        raise OverflowError("maximum")
    return values


def _interpolate(a, b, level):
    x1, y1, v1 = a; x2, y2, v2 = b
    delta = v2 - v1
    t = 0.5 if abs(delta) <= EPSILON else (level - v1) / delta
    t = min(1.0, max(0.0, t))
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))


def _cell_segments(corners, level):
    case = sum((1 << index) for index, corner in enumerate(corners) if corner[2] >= level)
    if case in (0, 15): return []
    edges = [(0, 1), (1, 2), (2, 3), (3, 0)]
    points = {edge: _interpolate(corners[a], corners[b], level) for edge, (a, b) in enumerate(edges)
              if (corners[a][2] >= level) != (corners[b][2] >= level)}
    active = sorted(points)
    if len(active) == 2: return [(points[active[0]], points[active[1]])]
    if len(active) != 4: return []
    center_high = sum(c[2] for c in corners) / 4.0 >= level
    # Asymptotic-decider-style deterministic pairing using the cell mean.
    if (case == 5 and center_high) or (case == 10 and not center_high):
        pairs = ((0, 1), (2, 3))
    else:
        pairs = ((0, 3), (1, 2))
    return [(points[a], points[b]) for a, b in pairs]


def _key(point):
    return (round(point[0], 10), round(point[1], 10))


def _stitch(segments):
    unique = {}
    for a, b in segments:
        if math.hypot(a[0]-b[0], a[1]-b[1]) <= EPSILON: continue
        ka, kb = _key(a), _key(b)
        unique[tuple(sorted((ka, kb)))] = (ka, kb)
    edges = sorted(unique.values())
    adjacency = {}
    for a, b in edges:
        adjacency.setdefault(a, []).append(b); adjacency.setdefault(b, []).append(a)
    unused = {tuple(sorted(edge)) for edge in edges}; lines = []
    while unused:
        endpoints = sorted(p for p, neighbors in adjacency.items()
                           if sum(tuple(sorted((p, n))) in unused for n in neighbors) == 1)
        start = endpoints[0] if endpoints else min(p for edge in unused for p in edge)
        line = [start]; previous = None; current = start
        while True:
            candidates = sorted(n for n in adjacency[current]
                                if tuple(sorted((current, n))) in unused and n != previous)
            if not candidates: break
            nxt = candidates[0]; unused.remove(tuple(sorted((current, nxt))))
            line.append(nxt); previous, current = current, nxt
            if current == start: break
        if len(line) > 1: lines.append(line)
    return sorted(lines, key=lambda line: (line[0], len(line), line))


def build_equal_time_contours(shadow_duration, settings=None, duration_field=None,
                              maximum_segment_count=None):
    result = _empty(); duration = shadow_duration or {}
    if duration.get("complete") is not True:
        return _block(result, "complete_shadow_duration_required")
    if duration.get("method") != SOURCE_METHOD:
        return _block(result, "unsupported_shadow_duration_method")
    spec = duration.get("grid_spec") or {}; grid = duration.get("duration_grid") or []
    try:
        nx, ny = _positive_grid_count(spec["x_count"]), _positive_grid_count(spec["y_count"])
        ox, oy, resolution = float(spec["origin_x_m"]), float(spec["origin_y_m"]), float(spec["resolution_m"])
        if (not math.isfinite(ox) or not math.isfinite(oy)
                or not math.isfinite(resolution) or resolution <= 0
                or spec.get("ordering") != "row_major_y_then_x"):
            raise ValueError()
        max_x = ox + (nx - 1) * resolution
        max_y = oy + (ny - 1) * resolution
        if not math.isfinite(max_x) or not math.isfinite(max_y):
            raise ValueError()
    except (KeyError, TypeError, ValueError, OverflowError):
        return _block(result, "duration_grid_spec_missing_or_invalid")
    compact = getattr(duration_field, "values", None)
    if compact is None and len(grid) != nx * ny: return _block(result, "duration_grid_size_mismatch")
    if compact is not None and len(compact) != nx * ny: return _block(result, "duration_grid_size_mismatch")
    try:
        values = compact if compact is not None else [float(item["shadow_duration_minutes"]) for item in grid]
        if any(not math.isfinite(value) for value in values): raise ValueError()
        levels = _levels(settings, float(duration.get("maximum_shadow_duration_minutes", 0.0)))
    except OverflowError:
        return _block(result, "max_equal_time_contour_levels_exceeded")
    except (KeyError, TypeError, ValueError):
        return _block(result, "invalid_equal_time_contour_settings")
    result["requested_levels_minutes"] = levels
    effective_segment_cap = _effective_segment_cap(duration, maximum_segment_count)
    result["effective_segment_cap"] = effective_segment_cap
    contours = []
    for level in levels:
        segments = []
        for iy in range(ny - 1):
            for ix in range(nx - 1):
                indices = (iy*nx+ix, iy*nx+ix+1, (iy+1)*nx+ix+1, (iy+1)*nx+ix)
                corners = [(ox + (index % nx)*resolution, oy + (index // nx)*resolution, values[index]) for index in indices]
                segments.extend(_cell_segments(corners, level))
                if len(segments) > effective_segment_cap:
                    return _block(_empty(), "equal_time_contour_segment_budget_exceeded")
        for line in _stitch(segments):
            closed = len(line) > 2 and line[0] == line[-1]
            length = sum(math.hypot(b[0]-a[0], b[1]-a[1]) for a, b in zip(line, line[1:]))
            if (not math.isfinite(length)
                    or any(not math.isfinite(coordinate) for point in line for coordinate in point)):
                return _block(_empty(), "duration_grid_spec_missing_or_invalid")
            contours.append({"level_minutes": level, "contour_index": 0, "closed": closed,
                             "point_count": len(line), "length_m": length,
                             "points_m": [{"x": p[0], "y": p[1]} for p in line]})
    contours.sort(key=lambda c: (c["level_minutes"], c["points_m"][0]["x"], c["points_m"][0]["y"], c["point_count"]))
    per_level = {}
    for contour in contours:
        contour["contour_index"] = per_level.get(contour["level_minutes"], 0)
        per_level[contour["level_minutes"]] = contour["contour_index"] + 1
    result.update({"available": True, "complete": True, "generated_levels_minutes": sorted(per_level),
                   "contour_count": len(contours), "closed_contour_count": sum(c["closed"] for c in contours),
                   "open_contour_count": sum(not c["closed"] for c in contours), "contours": contours})
    result["scalar_copy_materialized"] = compact is None
    return result


_build_equal_time_contours = build_equal_time_contours
