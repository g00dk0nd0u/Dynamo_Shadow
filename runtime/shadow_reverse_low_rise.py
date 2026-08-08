"""Lightweight low-rise reverse-shadow calculation core (pure Python)."""
import bisect
import math
from array import array

from shadow_reverse_accuracy import resolve_reverse_shadow_accuracy
from shadow_reverse_measurement import build_reverse_shadow_measurement_points
from shadow_site_distance_contours import build_site_distance_contours_from_site
from shadow_site_masks import _inside
from shadow_sun import build_true_solar_sun_ray_fan

METHOD = "low_rise_optimized_continuous_sunlight_envelope_v2"
MAX_SITE_DISTANCE_GRID_POINTS = 250000
MAX_REVERSE_HEIGHT_GRID_POINTS = 100000
MAX_REVERSE_MEASUREMENT_POINTS = 5000
MAX_REVERSE_CONSTRAINT_CHECKS = 25000000
MAX_REVERSE_TOP_SURFACE_TRIANGLES = 200000
REVERSE_CANDIDATE_CHUNK_SIZE = 8192
_HEIGHT_QUANTIZATION_TOLERANCE = 1e-9


def build_midday_sunlight_interval(start_minutes, end_minutes, allowed_shadow_minutes):
    result = {"complete": False, "blockers": []}
    try:
        start, end, allowed = map(float, (start_minutes, end_minutes, allowed_shadow_minutes))
        if not all(math.isfinite(v) for v in (start, end, allowed)) or end <= start or allowed < 0 or allowed >= end-start:
            raise ValueError()
    except Exception:
        result["blockers"].append({"failure_code": "reverse_shadow_invalid_allowed_shadow_minutes"}); return result
    duration = end-start; required = duration-allowed; midpoint = (start+end)/2.0
    sunlight_start, sunlight_end = midpoint-required/2.0, midpoint+required/2.0
    if sunlight_start < start-1e-9 or sunlight_end > end+1e-9:
        result["blockers"].append({"failure_code": "reverse_shadow_midday_interval_outside_regulation_window"}); return result
    result.update({"complete": True, "regulation_window_start_minutes": start,
                   "regulation_window_end_minutes": end, "regulation_window_duration_minutes": duration,
                   "allowed_shadow_minutes": allowed, "required_sunlight_minutes": required,
                   "sunlight_start_minutes": sunlight_start, "sunlight_end_minutes": sunlight_end})
    return result


def build_sunlight_interval_candidates(start_minutes, end_minutes, allowed_shadow_minutes, step_minutes):
    """Return every stepped placement plus exact endpoints and the centered baseline."""
    baseline = build_midday_sunlight_interval(start_minutes, end_minutes, allowed_shadow_minutes)
    if not baseline["complete"]:
        return dict(baseline, candidates=[])
    try:
        step = float(step_minutes)
        if not math.isfinite(step) or step <= 0:
            raise ValueError()
    except Exception:
        return {"complete": False, "blockers": [{"failure_code": "reverse_shadow_invalid_sun_time_step_minutes"}],
                "candidates": []}
    first = baseline["regulation_window_start_minutes"]
    last = baseline["regulation_window_end_minutes"] - baseline["required_sunlight_minutes"]
    starts = [first, last, baseline["sunlight_start_minutes"]]
    value = first
    while value <= last + 1e-9:
        starts.append(min(value, last))
        value += step
    starts = sorted(set(round(value, 9) for value in starts))
    candidates = [{"sunlight_start_minutes": value,
                   "sunlight_end_minutes": value + baseline["required_sunlight_minutes"]}
                  for value in starts]
    return dict(baseline, candidates=candidates, candidate_count=len(candidates))


def evaluate_adjacent_ray_facet(measurement_point, site_point, ray0, ray1, tolerance=1e-10):
    """Evaluate one planar cone facet, including its conservative endpoint clamp."""
    dx = site_point[0]-measurement_point[0]; dy = site_point[1]-measurement_point[1]
    det = ray0["x"]*ray1["y"]-ray0["y"]*ray1["x"]
    if abs(det) <= tolerance: return None
    a = (dx*ray1["y"]-dy*ray1["x"])/det
    b = (ray0["x"]*dy-ray0["y"]*dx)/det
    if a < -tolerance or b < -tolerance: return None
    planar = a*ray0["z"]+b*ray1["z"]
    endpoint = math.hypot(dx, dy)*min(ray0["z"]/math.hypot(ray0["x"], ray0["y"]),
                                      ray1["z"]/math.hypot(ray1["x"], ray1["y"]))
    return {"a": a, "b": b, "planar_delta_z_m": planar,
            "endpoint_conservative_delta_z_m": endpoint, "delta_z_m": min(planar, endpoint),
            "conservative_endpoint_altitude_clamp_applied": True}


def _minutes(text):
    if isinstance(text, (int, float)): return float(text)
    h, m = str(text).split(":")[:2]
    return int(h)*60+int(m)


def _empty():
    return {"available": False, "complete": False, "method": METHOD, "calculation_type": "low_rise",
            "intended_use": "coarse_initial_massing_guidance", "final_forward_equal_time_validation_required": True,
            "status_disclaimers": ["coarse planning envelope", "not a unique maximum volume",
                                   "not permit certified", "final forward equal-time shadow validation required",
                                   "time discretization applied", "spatial discretization applied",
                                   "high-rise reverse shadow not implemented", "ordinance applicability not confirmed"],
            "regulation_interpretation": {"sunlight_allocation": "deterministically_selected_continuous_interval",
                                          "unique_maximum_volume": False, "ordinance_applicability_confirmed": False},
            "blockers": [], "warnings": ["Reverse-shadow v1 is a coarse initial massing aid.",
            "The result is not a unique or maximum legally buildable volume.",
            "The selected regulation preset applicability is not certified.",
            "Final forward equal-time shadow validation is required.",
            "Time discretization and spatial discretization are applied.",
            "High-rise reverse shadow is not implemented."],
            "legal_judgement_generated": False, "ordinance_selection_certified": False,
            "permit_ready_certified": False}


def _recommend(preset): return {"high": "standard", "standard": "rough", "rough": None}.get(preset)


def _cell_crossed_by_boundary(min_x, min_y, max_x, max_y, polygon, tolerance=1e-9):
    """Conservatively detect a site segment passing through the open cell interior."""
    for index, start in enumerate(polygon):
        end = polygon[(index + 1) % len(polygon)]
        dx, dy = end[0] - start[0], end[1] - start[1]
        lower, upper = 0.0, 1.0
        for p, q in ((-dx, start[0]-min_x), (dx, max_x-start[0]),
                     (-dy, start[1]-min_y), (dy, max_y-start[1])):
            if abs(p) <= tolerance:
                if q < -tolerance: lower, upper = 1.0, 0.0; break
                continue
            ratio = q / p
            if p < 0: lower = max(lower, ratio)
            else: upper = min(upper, ratio)
            if lower > upper + tolerance: break
        if lower <= upper + tolerance:
            midpoint = (lower + upper) / 2.0
            x, y = start[0] + midpoint*dx, start[1] + midpoint*dy
            if min_x+tolerance < x < max_x-tolerance and min_y+tolerance < y < max_y-tolerance:
                return True
    return False


def _boundary_loops(directed_edges, grid):
    """Stitch oriented triangle boundary edges into deterministic closed loops."""
    outgoing = {}
    for start, end in directed_edges:
        outgoing.setdefault(start, []).append(end)
    if any(len(values) != 1 for values in outgoing.values()):
        return None
    unused = set(directed_edges); loops = []
    while unused:
        first = min(unused, key=lambda edge: (grid[edge[0]]["x_m"], grid[edge[0]]["y_m"], edge))
        vertices = [first[0]]; current = first[0]
        for _ in range(len(directed_edges) + 1):
            nxt = outgoing.get(current, [None])[0]
            edge = (current, nxt)
            if nxt is None or edge not in unused: return None
            unused.remove(edge); vertices.append(nxt); current = nxt
            if current == vertices[0]: break
        if vertices[-1] != vertices[0]: return None
        area = 0.5 * sum(grid[a]["x_m"]*grid[b]["y_m"] - grid[b]["x_m"]*grid[a]["y_m"]
                         for a, b in zip(vertices, vertices[1:]))
        loops.append({"loop_index": 0, "closed": True, "vertex_grid_indices": vertices,
                      "signed_plan_area_m2": area,
                      "orientation": "counter_clockwise" if area > 0 else "clockwise"})
    loops.sort(key=lambda loop: (-abs(loop["signed_plan_area_m2"]),
                                grid[loop["vertex_grid_indices"][0]]["x_m"],
                                grid[loop["vertex_grid_indices"][0]]["y_m"]))
    for index, loop in enumerate(loops): loop["loop_index"] = index
    return loops


def _constraint(point, measurement, fan, measurement_height):
    dx, dy = point[0]-measurement["x_m"], point[1]-measurement["y_m"]
    az = math.degrees(math.atan2(dx, dy)) % 360.0
    samples = fan["samples"]
    angles = [s["sun_azimuth_model_unwrapped_deg"] for s in samples]
    ascending = angles[-1] >= angles[0]
    if not ascending: angles = [-a for a in angles]; az = -az
    while az < angles[0]: az += 360.0
    while az > angles[-1]: az -= 360.0
    if az < angles[0]-1e-9 or az > angles[-1]+1e-9: return None
    facet = max(0, min(len(samples)-2, bisect.bisect_right(angles, az)-1))
    r0, r1 = samples[facet]["ray_vector_model"], samples[facet+1]["ray_vector_model"]
    value = evaluate_adjacent_ray_facet((measurement["x_m"], measurement["y_m"]), point, r0, r1)
    if value is None: return None
    value.update({"height": max(0.0, measurement_height+value["delta_z_m"]), "facet": facet,
                  "start": samples[facet]["true_solar_minutes"], "end": samples[facet+1]["true_solar_minutes"],
                  "horizontal_distance_m": math.hypot(dx, dy)})
    return value


def _quantize_height(raw_height_m, vertical_step_m, tolerance=_HEIGHT_QUANTIZATION_TOLERANCE):
    """Floor a non-negative analytical height to the conservative vertical step."""
    raw = max(0.0, float(raw_height_m))
    step = float(vertical_step_m)
    return max(0.0, math.floor((raw + tolerance) / step) * step)


def _candidate_height(point, measurement_points, candidate, measurement_height, vertical_step, metadata=False):
    """Shared Pass 1/Pass 2 constraint evaluation with identical quantization."""
    best = None
    for measurement in measurement_points:
        value = _constraint(point, measurement, candidate["sun_ray_fan"], measurement_height)
        if value is None:
            continue
        quantized = _quantize_height(value["height"], vertical_step)
        key = (quantized, value["height"], measurement["measurement_point_index"])
        if best is None or key < best[0]:
            best = (key, value, measurement)
    if best is None:
        return None
    if not metadata:
        return best[0][0]
    _, value, measurement = best
    value = dict(value)
    value["raw_height"] = value["height"]
    value["height"] = best[0][0]
    return value, measurement


def build_low_rise_reverse_shadow_core(site_boundary_geometry, resolved_regulatory_preset,
                                       measurement_plane, settings_normalized, calculation_accuracy_preset):
    result = _empty()
    requested = calculation_accuracy_preset.get("preset_id") if isinstance(calculation_accuracy_preset, dict) else calculation_accuracy_preset
    accuracy = resolve_reverse_shadow_accuracy(requested)
    result["reverse_shadow_accuracy"] = accuracy
    if not accuracy["valid"]: result["blockers"] += accuracy["blockers"]; return result
    preset = resolved_regulatory_preset or {}
    if not preset.get("valid") or not preset.get("comparison_ready") or preset.get("near_limit_minutes") is None or preset.get("far_limit_minutes") is None:
        result["blockers"].append({"failure_code": "reverse_shadow_selected_limit_pair_required"}); return result
    contours = build_site_distance_contours_from_site(site_boundary_geometry, accuracy["site_distance_resolution_m"], MAX_SITE_DISTANCE_GRID_POINTS)
    result["site_distance_contours"] = contours
    if not contours.get("complete"): result["blockers"] += contours.get("blockers", []); return result
    measurements = build_reverse_shadow_measurement_points(contours, accuracy["measurement_point_spacing_m"])
    result["measurement_points"] = measurements
    if not measurements.get("complete"): result["blockers"] += measurements.get("blockers", []); return result
    if measurements["total_point_count"] > MAX_REVERSE_MEASUREMENT_POINTS:
        result["blockers"].append({"failure_code": "reverse_shadow_complexity_limit_exceeded", "requested_preset": requested,
            "recommended_preset": _recommend(requested), "measurement_point_count": measurements["total_point_count"],
            "maximum_measurement_points": MAX_REVERSE_MEASUREMENT_POINTS}); return result
    try:
        window_start, window_end = _minutes(preset["true_solar_start_time"]), _minutes(preset["true_solar_end_time"])
        measurement_height = float(measurement_plane["measurement_height_m"])
    except Exception:
        result["blockers"].append({"failure_code": "reverse_shadow_measurement_plane_or_limit_pair_required"}); return result

    zone_candidates = {}; zones = {}
    for name, distance, limit in (("near", 5.0, preset["near_limit_minutes"]), ("far", 10.0, preset["far_limit_minutes"])):
        generated = build_sunlight_interval_candidates(window_start, window_end, limit, accuracy["sun_time_step_minutes"])
        if not generated["complete"]: result["blockers"] += generated["blockers"]; return result
        candidates = []
        for interval in generated["candidates"]:
            fan = build_true_solar_sun_ray_fan(settings_normalized, interval["sunlight_start_minutes"],
                interval["sunlight_end_minutes"], accuracy["sun_time_step_minutes"])
            if not fan["complete"]: result["blockers"] += fan["blockers"]; return result
            candidates.append(dict(interval, sun_ray_fan=fan, sun_ray_sample_count=fan["sample_count"],
                                   sun_facet_count=fan["facet_count"]))
        zone_candidates[name] = candidates
        centered = min(candidates, key=lambda item: abs(item["sunlight_start_minutes"]-generated["sunlight_start_minutes"]))
        zones[name] = dict(generated, distance_m=distance, sun_time_step_minutes=accuracy["sun_time_step_minutes"],
                           sun_ray_sample_count=centered["sun_ray_sample_count"], sun_facet_count=centered["sun_facet_count"],
                           sun_ray_fan=centered["sun_ray_fan"])
    result["zones"] = zones
    polygon = [(float(p["x_m"]), float(p["y_m"])) for p in site_boundary_geometry["outer_loop"]]
    resolution = accuracy["height_field_grid_resolution_m"]
    ox = math.floor(min(p[0] for p in polygon)/resolution)*resolution
    oy = math.floor(min(p[1] for p in polygon)/resolution)*resolution
    nx = int(round((math.ceil(max(p[0] for p in polygon)/resolution)*resolution-ox)/resolution))+1
    ny = int(round((math.ceil(max(p[1] for p in polygon)/resolution)*resolution-oy)/resolution))+1
    count = nx*ny
    if count > MAX_REVERSE_HEIGHT_GRID_POINTS:
        result["blockers"].append({"failure_code": "reverse_shadow_complexity_limit_exceeded", "height_field_grid_point_count": count}); return result
    points = [(ox+(i%nx)*resolution, oy+(i//nx)*resolution) for i in range(count)]
    classifications = [_inside(point, polygon, 1e-8) for point in points]
    inside_count = sum(value is not False for value in classifications)
    candidate_evaluations = inside_count * sum(len(zone_candidates[z])*len(measurements[z]["points"]) for z in ("near", "far"))
    estimated_triangles = 2*(nx-1)*(ny-1)
    if candidate_evaluations > MAX_REVERSE_CONSTRAINT_CHECKS:
        result["blockers"].append({"failure_code": "reverse_shadow_complexity_limit_exceeded", "limit_type": "constraint_checks",
            "requested_preset": requested, "recommended_preset": _recommend(requested),
            "estimated_constraint_checks": candidate_evaluations, "maximum_constraint_checks": MAX_REVERSE_CONSTRAINT_CHECKS})
    if estimated_triangles > MAX_REVERSE_TOP_SURFACE_TRIANGLES:
        result["blockers"].append({"failure_code": "reverse_shadow_complexity_limit_exceeded", "limit_type": "top_surface_triangles",
            "requested_preset": requested, "recommended_preset": _recommend(requested),
            "estimated_top_surface_triangle_count": estimated_triangles, "maximum_top_surface_triangles": MAX_REVERSE_TOP_SURFACE_TRIANGLES})
    if result["blockers"]: return result

    eligible_cells = []; omitted_boundary = 0
    for iy in range(ny-1):
        for ix in range(nx-1):
            ids = (iy*nx+ix, iy*nx+ix+1, (iy+1)*nx+ix+1, (iy+1)*nx+ix)
            center_inside = _inside((ox+(ix+.5)*resolution, oy+(iy+.5)*resolution), polygon, 1e-8) is not False
            if (not all(classifications[i] is not False for i in ids) or not center_inside or
                    _cell_crossed_by_boundary(points[ids[0]][0], points[ids[0]][1],
                                              points[ids[2]][0], points[ids[2]][1], polygon)):
                omitted_boundary += 1
            else:
                eligible_cells.append((ix, iy, ids))

    # Pass 1 holds only chunk-local compact candidate buffers. Rows overlap by one
    # so each eligible cell is scored exactly once without retaining full fields.
    nan = float("nan")
    pair_metrics = [[{"bounded_candidate_plan_area_m2": 0.0, "bounded_candidate_volume_m3": 0.0,
                      "omitted_unbounded_cell_count": 0}
                     for _ in zone_candidates["far"]] for _ in zone_candidates["near"]]
    chunk_size = max(2, int(REVERSE_CANDIDATE_CHUNK_SIZE))
    cell_rows_per_chunk = max(1, chunk_size // nx - 1)
    vertical_step = accuracy["vertical_height_step_m"]

    for first_row in range(0, ny - 1, cell_rows_per_chunk):
        last_cell_row = min(ny - 2, first_row + cell_rows_per_chunk - 1)
        first_index = first_row * nx
        stop_index = (last_cell_row + 2) * nx
        local_count = stop_index - first_index
        fields = {"near": [], "far": []}
        for zone_name in ("near", "far"):
            for candidate in zone_candidates[zone_name]:
                heights = array("d", [nan]) * local_count
                for local_index, global_index in enumerate(range(first_index, stop_index)):
                    if classifications[global_index] is False:
                        continue
                    value = _candidate_height(points[global_index], measurements[zone_name]["points"],
                                              candidate, measurement_height, vertical_step)
                    if value is not None:
                        heights[local_index] = value
                fields[zone_name].append(heights)
        for ix, iy, ids in eligible_cells:
            if iy < first_row or iy > last_cell_row:
                continue
            local_ids = tuple(index - first_index for index in ids)
            for ni, near in enumerate(fields["near"]):
                for fi, far in enumerate(fields["far"]):
                    values = []
                    for index in local_ids:
                        a, b = near[index], far[index]
                        values.append(b if math.isnan(a) else a if math.isnan(b) else min(a, b))
                    metrics = pair_metrics[ni][fi]
                    if any(math.isnan(value) or not math.isfinite(value) for value in values):
                        metrics["omitted_unbounded_cell_count"] += 1
                        continue
                    metrics["bounded_candidate_plan_area_m2"] += resolution * resolution
                    metrics["bounded_candidate_volume_m3"] += (resolution * resolution *
                        (2.0*values[0] + values[1] + 2.0*values[2] + values[3]) / 6.0)

    centered_indices = {}
    for zone_name in ("near", "far"):
        centered_start = zones[zone_name]["sunlight_start_minutes"]
        centered_indices[zone_name] = min(range(len(zone_candidates[zone_name])),
            key=lambda i: abs(zone_candidates[zone_name][i]["sunlight_start_minutes"]-centered_start))
    baseline_score = pair_metrics[centered_indices["near"]][centered_indices["far"]]
    best = None
    for ni, near in enumerate(zone_candidates["near"]):
        for fi, far in enumerate(zone_candidates["far"]):
            metrics = pair_metrics[ni][fi]
            shift = abs(near["sunlight_start_minutes"]-zones["near"]["sunlight_start_minutes"]) + abs(far["sunlight_start_minutes"]-zones["far"]["sunlight_start_minutes"])
            key = (metrics["bounded_candidate_volume_m3"], metrics["bounded_candidate_plan_area_m2"],
                   -metrics["omitted_unbounded_cell_count"], -shift, -near["sunlight_start_minutes"], -far["sunlight_start_minutes"])
            if best is None or key > best[0]: best = (key, ni, fi, metrics)
    _, selected_near, selected_far, selected_score = best
    selected_candidates = {"near": zone_candidates["near"][selected_near], "far": zone_candidates["far"][selected_far]}
    for zone_name in ("near", "far"):
        selected = selected_candidates[zone_name]
        zones[zone_name].update({
            "sunlight_start_minutes": selected["sunlight_start_minutes"],
            "sunlight_end_minutes": selected["sunlight_end_minutes"],
            "sun_ray_fan": selected["sun_ray_fan"],
            "sun_ray_sample_count": selected["sun_ray_sample_count"],
            "sun_facet_count": selected["sun_facet_count"],
        })

    # Build rich metadata only for the selected pair and retain the production endpoint clamp.
    grid = []; clamp_count = governing_count = 0; maximum_reduction = 0.0
    for index, inside in enumerate(classifications):
        x, y = points[index]
        item = {"grid_index": index, "ix": index%nx, "iy": index//nx, "x_m": x, "y_m": y,
                "inside_site": inside is not False, "on_site_boundary": inside is None, "bounded": False,
                "raw_height_limit_m": None, "height_limit_m": None, "governing_zone": None, "governing_measurement_point_index": None,
                "governing_facet_index": None, "governing_true_solar_start_minutes": None,
                "governing_true_solar_end_minutes": None, "governing_distance_m": None,
                "governing_horizontal_distance_m": None, "governing_measurement_line_distance_m": None}
        best_value = None
        if inside is not False:
            for zone_name in ("near", "far"):
                evaluated = _candidate_height((x, y), measurements[zone_name]["points"],
                    selected_candidates[zone_name], measurement_height, vertical_step, metadata=True)
                if evaluated is not None:
                    value, mp = evaluated
                    key = (value["height"], value["raw_height"], 0 if zone_name == "near" else 1, mp["measurement_point_index"])
                    if best_value is None or key < best_value[0]: best_value=(key, value, zone_name, mp)
        if best_value:
            _, value, zone_name, mp = best_value; governing_count += 1
            reduction = max(0.0, value["planar_delta_z_m"]-value["endpoint_conservative_delta_z_m"])
            if reduction > 1e-12: clamp_count += 1; maximum_reduction=max(maximum_reduction, reduction)
            item.update({"bounded": True, "raw_height_limit_m": value["raw_height"], "height_limit_m": value["height"], "governing_zone": zone_name,
                "governing_measurement_point_index": mp["measurement_point_index"], "governing_facet_index": value["facet"],
                "governing_true_solar_start_minutes": value["start"], "governing_true_solar_end_minutes": value["end"],
                "governing_horizontal_distance_m": value["horizontal_distance_m"], "governing_distance_m": value["horizontal_distance_m"],
                "governing_measurement_line_distance_m": zones[zone_name]["distance_m"]})
        grid.append(item)

    triangles=[]; edge_counts={}; directed_counts={}; area=volume=0.0; omitted_unbounded=0
    for ix, iy, ids in eligible_cells:
        if not all(grid[i]["bounded"] and math.isfinite(grid[i]["height_limit_m"]) for i in ids): omitted_unbounded += 1; continue
        for vertices in ((ids[0], ids[1], ids[2]), (ids[0], ids[2], ids[3])):
            triangles.append({"triangle_index": len(triangles), "cell_ix": ix, "cell_iy": iy, "vertex_grid_indices": list(vertices)})
            area += resolution*resolution/2.0
            volume += resolution*resolution/2.0*sum(grid[v]["height_limit_m"] for v in vertices)/3.0
            for a,b in zip(vertices,(vertices[1],vertices[2],vertices[0])):
                edge=tuple(sorted((a,b))); edge_counts[edge]=edge_counts.get(edge,0)+1; directed_counts[(a,b)]=directed_counts.get((a,b),0)+1
    edges=[{"start_grid_index":a,"end_grid_index":b} for (a,b),uses in sorted(edge_counts.items()) if uses==1]
    directed_boundary=[(a,b) for (a,b),uses in directed_counts.items() if uses>directed_counts.get((b,a),0)]
    boundary_loops=_boundary_loops(directed_boundary,grid) if directed_boundary else []
    bounded=[p["height_limit_m"] for p in grid if p["bounded"]]
    result["complexity"]={"site_distance_grid_point_count":contours["grid_spec"]["point_count"],"height_field_grid_point_count":count,
        "inside_site_height_grid_point_count":inside_count,"measurement_point_count":measurements["total_point_count"],
        "estimated_constraint_check_count":candidate_evaluations,"selected_metadata_constraint_check_count":inside_count*measurements["total_point_count"],
        "top_surface_triangle_count":len(triangles),"automatic_accuracy_fallback_used":False,
        "chunk_size":chunk_size,"pass_count":2,"compact_buffer_type":"array('d')",
        "candidate_field_full_materialization":False,"single_process":True}
    result["height_field"]={"grid_spec":{"x_count":nx,"y_count":ny,"origin_x_m":ox,"origin_y_m":oy,"resolution_m":resolution,"ordering":"row_major_y_then_x"},
        "grid_points":grid,"bounded_grid_point_count":len(bounded),"unbounded_grid_point_count":inside_count-len(bounded),
        "minimum_bounded_height_m":min(bounded) if bounded else None,"maximum_bounded_height_m":max(bounded) if bounded else None}
    result["top_surface_mesh"]={"vertices_source":"height_field.grid_points","triangles":triangles,"boundary_edges":edges,
        "top_surface_boundary_loops":boundary_loops or [],"top_surface_triangle_count":len(triangles),
        "top_surface_vertex_count":len(set(v for t in triangles for v in t["vertex_grid_indices"])),"top_surface_boundary_edge_count":len(edges),
        "omitted_boundary_cell_count":omitted_boundary,"omitted_unbounded_cell_count":omitted_unbounded,
        "bounded_candidate_plan_area_m2":area,"bounded_candidate_volume_m3":volume}
    def interval_data(zone_name, index):
        value=zone_candidates[zone_name][index]
        return value["sunlight_start_minutes"], value["sunlight_end_minutes"]
    bn,be=interval_data("near",centered_indices["near"]); bf,bfe=interval_data("far",centered_indices["far"])
    sn,se=interval_data("near",selected_near); sf,sfe=interval_data("far",selected_far)
    gain=selected_score["bounded_candidate_volume_m3"]-baseline_score["bounded_candidate_volume_m3"]
    result["reverse_shadow_interval_optimization"]={"enabled":True,"objective":"coarse_bounded_candidate_volume_then_plan_area",
        "near_candidate_count":len(zone_candidates["near"]),"far_candidate_count":len(zone_candidates["far"]),
        "candidate_pair_count":len(zone_candidates["near"])*len(zone_candidates["far"]),
        "centered_baseline":dict(baseline_score,near_start_minutes=bn,near_end_minutes=be,far_start_minutes=bf,far_end_minutes=bfe),
        "selected":dict(selected_score,near_start_minutes=sn,near_end_minutes=se,far_start_minutes=sf,far_end_minutes=sfe,
            near_shift_from_centered_minutes=sn-bn,far_shift_from_centered_minutes=sf-bf),
        "gain_vs_centered":{"volume_m3":gain,"volume_percent":(100.0*gain/baseline_score["bounded_candidate_volume_m3"] if baseline_score["bounded_candidate_volume_m3"] else None),
            "plan_area_m2":selected_score["bounded_candidate_plan_area_m2"]-baseline_score["bounded_candidate_plan_area_m2"]},
        "clamp_diagnostics":{"governing_constraint_count":governing_count,"endpoint_clamp_governing_count":clamp_count,
            "maximum_governing_clamp_reduction_m":maximum_reduction}}
    result["approximation"]={"measurement_lines_grid_based":True,"site_distance_resolution_m":accuracy["site_distance_resolution_m"],
        "measurement_point_spacing_m":accuracy["measurement_point_spacing_m"],"height_field_grid_resolution_m":resolution,
        "sun_time_step_minutes":accuracy["sun_time_step_minutes"],"vertical_height_step_m":vertical_step,
        "vertical_height_quantization":"floor_conservative","sun_cone_facets":"adjacent_ray_planar_facets",
        "conservative_endpoint_altitude_clamp":True,"partial_boundary_cells_omitted":True,"unbounded_cells_omitted":True,"exact_statutory_offset_used":False}
    if not bounded: result["blockers"].append({"failure_code":"reverse_shadow_no_bounded_height_points"})
    if not triangles or area<=0: result["blockers"].append({"failure_code":"reverse_shadow_top_surface_mesh_empty"})
    if triangles and boundary_loops is None: result["blockers"].append({"failure_code":"reverse_shadow_boundary_loop_construction_failed"})
    if not all(math.isfinite(v) for v in [area,volume]+bounded) or volume<=0: result["blockers"].append({"failure_code":"reverse_shadow_candidate_volume_invalid"})
    if result["blockers"]: return result
    result.update({"available":True,"complete":True})
    return result
