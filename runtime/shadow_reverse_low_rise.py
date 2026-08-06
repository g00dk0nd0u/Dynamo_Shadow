"""Lightweight low-rise reverse-shadow calculation core (pure Python)."""
import bisect
import math

from shadow_reverse_accuracy import resolve_reverse_shadow_accuracy
from shadow_reverse_measurement import build_reverse_shadow_measurement_points
from shadow_site_distance_contours import build_site_distance_contours_from_site
from shadow_site_masks import _inside
from shadow_sun import build_true_solar_sun_ray_fan

METHOD = "low_rise_midday_continuous_sunlight_envelope_v1"
MAX_SITE_DISTANCE_GRID_POINTS = 250000
MAX_REVERSE_HEIGHT_GRID_POINTS = 100000
MAX_REVERSE_MEASUREMENT_POINTS = 5000
MAX_REVERSE_CONSTRAINT_CHECKS = 25000000
MAX_REVERSE_TOP_SURFACE_TRIANGLES = 200000


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
            "regulation_interpretation": {"sunlight_allocation": "continuous_interval_centered_on_selected_regulation_window_midpoint",
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
                  "start": samples[facet]["true_solar_minutes"], "end": samples[facet+1]["true_solar_minutes"]})
    return value


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
        result["blockers"].append({"failure_code": "reverse_shadow_complexity_limit_exceeded",
                                   "requested_preset": requested, "recommended_preset": _recommend(requested),
                                   "measurement_point_count": measurements["total_point_count"],
                                   "maximum_measurement_points": MAX_REVERSE_MEASUREMENT_POINTS}); return result
    try: window_start, window_end = _minutes(preset["true_solar_start_time"]), _minutes(preset["true_solar_end_time"])
    except Exception: result["blockers"].append({"failure_code": "reverse_shadow_selected_limit_pair_required"}); return result
    zones = {}
    for name, distance, limit in (("near", 5.0, preset["near_limit_minutes"]), ("far", 10.0, preset["far_limit_minutes"])):
        interval = build_midday_sunlight_interval(window_start, window_end, limit)
        if not interval["complete"]: result["blockers"] += interval["blockers"]; return result
        fan = build_true_solar_sun_ray_fan(settings_normalized, interval["sunlight_start_minutes"],
                                           interval["sunlight_end_minutes"], accuracy["sun_time_step_minutes"])
        if not fan["complete"]: result["blockers"] += fan["blockers"]; return result
        zones[name] = dict(interval, distance_m=distance, sun_time_step_minutes=accuracy["sun_time_step_minutes"],
                           sun_ray_sample_count=fan["sample_count"], sun_facet_count=fan["facet_count"], sun_ray_fan=fan)
    result["zones"] = zones
    polygon = [(float(p["x_m"]), float(p["y_m"])) for p in site_boundary_geometry["outer_loop"]]
    resolution = accuracy["height_field_grid_resolution_m"]
    ox = math.floor(min(p[0] for p in polygon)/resolution)*resolution
    oy = math.floor(min(p[1] for p in polygon)/resolution)*resolution
    nx = int(round((math.ceil(max(p[0] for p in polygon)/resolution)*resolution-ox)/resolution))+1
    ny = int(round((math.ceil(max(p[1] for p in polygon)/resolution)*resolution-oy)/resolution))+1
    count = nx*ny
    if count > MAX_REVERSE_HEIGHT_GRID_POINTS:
        result["blockers"].append({"failure_code": "reverse_shadow_complexity_limit_exceeded", "requested_preset": requested,
                                   "recommended_preset": _recommend(requested), "height_field_grid_point_count": count,
                                   "maximum_height_grid_points": MAX_REVERSE_HEIGHT_GRID_POINTS}); return result
    classifications = [_inside((ox+(i%nx)*resolution, oy+(i//nx)*resolution), polygon, 1e-8) for i in range(count)]
    inside_count = sum(v is not False for v in classifications)
    checks = inside_count*measurements["total_point_count"]
    estimated_triangles = 2*(nx-1)*(ny-1)
    if checks > MAX_REVERSE_CONSTRAINT_CHECKS or estimated_triangles > MAX_REVERSE_TOP_SURFACE_TRIANGLES:
        result["blockers"].append({"failure_code": "reverse_shadow_complexity_limit_exceeded", "requested_preset": requested,
                                   "recommended_preset": _recommend(requested), "estimated_constraint_checks": checks,
                                   "maximum_constraint_checks": MAX_REVERSE_CONSTRAINT_CHECKS}); return result
    try: measurement_height = float(measurement_plane["measurement_height_m"])
    except Exception:
        try: measurement_height = float(measurement_plane["elevation_m"])-float(measurement_plane["average_ground_level_elevation_m"])
        except Exception: result["blockers"].append({"failure_code": "reverse_shadow_measurement_plane_required"}); return result
    grid = []
    for index, inside in enumerate(classifications):
        x, y = ox+(index%nx)*resolution, oy+(index//nx)*resolution
        item = {"grid_index": index, "ix": index%nx, "iy": index//nx, "x_m": x, "y_m": y,
                "inside_site": inside is not False, "on_site_boundary": inside is None, "bounded": False,
                "height_limit_m": None, "governing_zone": None, "governing_measurement_point_index": None,
                "governing_facet_index": None, "governing_true_solar_start_minutes": None,
                "governing_true_solar_end_minutes": None, "governing_distance_m": None}
        best = None
        if inside is not False:
            for zone_name in ("near", "far"):
                for mp in measurements[zone_name]["points"]:
                    value = _constraint((x, y), mp, zones[zone_name]["sun_ray_fan"], measurement_height)
                    if value is not None and (best is None or value["height"] < best[0]["height"]): best = (value, zone_name, mp)
        if best:
            value, zone_name, mp = best; item.update({"bounded": True, "height_limit_m": value["height"],
                "governing_zone": zone_name, "governing_measurement_point_index": mp["measurement_point_index"],
                "governing_facet_index": value["facet"], "governing_true_solar_start_minutes": value["start"],
                "governing_true_solar_end_minutes": value["end"], "governing_distance_m": zones[zone_name]["distance_m"]})
        grid.append(item)
    triangles, edge_counts, omitted_boundary, omitted_unbounded, area, volume = [], {}, 0, 0, 0.0, 0.0
    for iy in range(ny-1):
        for ix in range(nx-1):
            ids = [iy*nx+ix, iy*nx+ix+1, (iy+1)*nx+ix+1, (iy+1)*nx+ix]
            pts = [grid[i] for i in ids]
            center_inside = _inside((ox+(ix+.5)*resolution, oy+(iy+.5)*resolution), polygon, 1e-8) is not False
            if not all(p["inside_site"] for p in pts) or not center_inside: omitted_boundary += 1; continue
            if not all(p["bounded"] and math.isfinite(p["height_limit_m"]) for p in pts): omitted_unbounded += 1; continue
            for vertices in ((ids[0], ids[1], ids[2]), (ids[0], ids[2], ids[3])):
                triangles.append({"triangle_index": len(triangles), "cell_ix": ix, "cell_iy": iy,
                                  "vertex_grid_indices": list(vertices)})
                area += resolution*resolution/2.0
                volume += resolution*resolution/2.0*sum(grid[v]["height_limit_m"] for v in vertices)/3.0
                for a, b in zip(vertices, (vertices[1], vertices[2], vertices[0])):
                    edge = tuple(sorted((a, b))); edge_counts[edge] = edge_counts.get(edge, 0)+1
    edges = [{"start_grid_index": a, "end_grid_index": b} for (a,b), uses in sorted(edge_counts.items()) if uses == 1]
    bounded = [p["height_limit_m"] for p in grid if p["bounded"]]
    result["complexity"] = {"site_distance_grid_point_count": contours["grid_spec"]["point_count"],
        "height_field_grid_point_count": count, "inside_site_height_grid_point_count": inside_count,
        "measurement_point_count": measurements["total_point_count"], "estimated_constraint_check_count": checks,
        "top_surface_triangle_count": len(triangles), "automatic_accuracy_fallback_used": False}
    result["height_field"] = {"grid_spec": {"x_count": nx, "y_count": ny, "origin_x_m": ox, "origin_y_m": oy,
        "resolution_m": resolution, "ordering": "row_major_y_then_x"}, "grid_points": grid,
        "bounded_grid_point_count": len(bounded), "unbounded_grid_point_count": inside_count-len(bounded),
        "minimum_bounded_height_m": min(bounded) if bounded else None, "maximum_bounded_height_m": max(bounded) if bounded else None}
    result["top_surface_mesh"] = {"vertices_source": "height_field.grid_points", "triangles": triangles, "boundary_edges": edges,
        "top_surface_triangle_count": len(triangles), "top_surface_vertex_count": len(set(v for t in triangles for v in t["vertex_grid_indices"])),
        "top_surface_boundary_edge_count": len(edges), "omitted_boundary_cell_count": omitted_boundary,
        "omitted_unbounded_cell_count": omitted_unbounded, "bounded_candidate_plan_area_m2": area,
        "bounded_candidate_volume_m3": volume}
    result["approximation"] = {"measurement_lines_grid_based": True, "site_distance_resolution_m": accuracy["site_distance_resolution_m"],
        "measurement_point_spacing_m": accuracy["measurement_point_spacing_m"], "height_field_grid_resolution_m": resolution,
        "sun_time_step_minutes": accuracy["sun_time_step_minutes"], "sun_cone_facets": "adjacent_ray_planar_facets",
        "conservative_endpoint_altitude_clamp": True, "partial_boundary_cells_omitted": True,
        "unbounded_cells_omitted": True, "exact_statutory_offset_used": False}
    result.update({"available": True, "complete": True})
    return result
