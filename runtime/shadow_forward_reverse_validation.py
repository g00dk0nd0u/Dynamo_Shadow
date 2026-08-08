"""Fixed-input comparison between prismatic Forward-equivalent and Reverse v2."""
import math

from shadow_forward_equivalent_validator import build_prismatic_forward_equivalent_duration, point_in_polygon
from shadow_regulatory_comparison import build_selected_limit_comparison
from shadow_regulatory_presets import resolve_regulatory_shadow_preset
from shadow_reverse_low_rise import (METHOD_V2, METHOD_V3,
    build_low_rise_reverse_shadow_core_v2, build_low_rise_reverse_shadow_core_v3,
    diagnose_general_pattern_fixture_feasibility)
from shadow_settings import _normalize_settings
from shadow_site_masks import build_measurement_masks
from shadow_reverse_state_replay import build_shadow_state_replay


def interpolate_reverse_height(reverse_result, x, y, tolerance=1e-9):
    points = ((reverse_result or {}).get("height_field") or {}).get("grid_points") or []
    triangles = ((reverse_result or {}).get("top_surface_mesh") or {}).get("triangles") or []
    for triangle in triangles:
        vertices = [points[index] for index in triangle["vertex_grid_indices"]]
        ax, ay = vertices[0]["x_m"], vertices[0]["y_m"]
        bx, by = vertices[1]["x_m"], vertices[1]["y_m"]
        cx, cy = vertices[2]["x_m"], vertices[2]["y_m"]
        denominator = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(denominator) <= tolerance:
            continue
        wa = ((by - cy) * (x - cx) + (cx - bx) * (y - cy)) / denominator
        wb = ((cy - ay) * (x - cx) + (ax - cx) * (y - cy)) / denominator
        wc = 1.0 - wa - wb
        if min(wa, wb, wc) >= -tolerance:
            heights = [vertex.get("height_limit_m") for vertex in vertices]
            if any(value is None or not math.isfinite(float(value)) for value in heights):
                return None
            return wa * heights[0] + wb * heights[1] + wc * heights[2]
    return None


def _sample_polygon(polygon, spacing):
    points = set()
    for index, start in enumerate(polygon):
        end = polygon[(index + 1) % len(polygon)]
        count = max(1, int(math.ceil(math.hypot(end[0] - start[0], end[1] - start[1]) / spacing)))
        for step in range(count + 1):
            fraction = float(step) / count
            points.add((round(start[0] + fraction * (end[0] - start[0]), 9),
                        round(start[1] + fraction * (end[1] - start[1]), 9)))
    min_x, max_x = min(p[0] for p in polygon), max(p[0] for p in polygon)
    min_y, max_y = min(p[1] for p in polygon), max(p[1] for p in polygon)
    ix0, ix1 = math.ceil(min_x / spacing), math.floor(max_x / spacing)
    iy0, iy1 = math.ceil(min_y / spacing), math.floor(max_y / spacing)
    for iy in range(iy0, iy1 + 1):
        for ix in range(ix0, ix1 + 1):
            point = (round(ix * spacing, 9), round(iy * spacing, 9))
            if point_in_polygon(point, polygon):
                points.add(point)
    return sorted(points, key=lambda value: (value[1], value[0]))


def evaluate_prism_against_reverse_envelope(footprint, candidate_height_m, reverse_result,
                                             validation_spacing_m=0.5):
    polygon = [(float(p[0]), float(p[1])) for p in footprint]
    samples = _sample_polygon(polygon, validation_spacing_m)
    evaluated = []
    for x, y in samples:
        limit = interpolate_reverse_height(reverse_result, x, y)
        excess = None if limit is None else float(candidate_height_m) - limit
        evaluated.append({"x_m": x, "y_m": y, "height_limit_m": limit, "height_excess_m": excess})
    bounded = [item for item in evaluated if item["height_limit_m"] is not None]
    exceeded = [item for item in bounded if item["height_excess_m"] > 1e-9]
    unbounded = [item for item in evaluated if item["height_limit_m"] is None]
    worst = max(evaluated, key=lambda item: (float("inf") if item["height_excess_m"] is None else item["height_excess_m"],
                                             -item["y_m"], -item["x_m"])) if evaluated else None
    margins = [item["height_limit_m"] - float(candidate_height_m) for item in bounded]
    return {"fully_inside": bool(evaluated) and not exceeded and not unbounded,
            "validation_spacing_m": validation_spacing_m, "validation_point_count": len(evaluated),
            "inside_point_count": len(bounded) - len(exceeded), "exceeded_point_count": len(exceeded),
            "unbounded_point_count": len(unbounded),
            "maximum_height_excess_m": max([item["height_excess_m"] for item in exceeded] or [0.0]),
            "minimum_height_margin_m": min(margins) if margins else None, "worst_point": worst}


def _site_geometry(points):
    polygon = [{"x_m": float(p[0]), "y_m": float(p[1])} for p in points]
    return {"complete": True, "method": "fixed_validation_fixture_polygon",
            "outer_loop": polygon, "bounds_m": {"min_x": min(p["x_m"] for p in polygon),
                                                   "min_y": min(p["y_m"] for p in polygon),
                                                   "max_x": max(p["x_m"] for p in polygon),
                                                   "max_y": max(p["y_m"] for p in polygon)}}


def build_forward_reverse_validation(fixture):
    preset = resolve_regulatory_shadow_preset(fixture["preset_id"])
    site = _site_geometry(fixture["site_boundary"])
    settings = _normalize_settings({"profile": preset["profile"], "time_basis": "true_solar_time",
        "solar_parameter_mode": "regulatory_winter_solstice_v1", "site_latitude_deg": fixture["site_latitude_deg"],
        "site_longitude_deg": fixture["site_longitude_deg"], "true_north_deg": fixture["true_north_deg"],
        "average_ground_level_elevation_m": fixture["average_ground_level_elevation_m"],
        "measurement_height_m": fixture["measurement_height_m"], "sun_time_step_minutes": 15})
    duration = build_prismatic_forward_equivalent_duration(fixture, preset)
    masks = build_measurement_masks(duration, site)
    comparison = build_selected_limit_comparison(preset, masks, duration, settings)
    plane = {"elevation_m": float(fixture["average_ground_level_elevation_m"]) + float(fixture["measurement_height_m"]),
             "average_ground_level_elevation_m": fixture["average_ground_level_elevation_m"],
             "measurement_height_m": fixture["measurement_height_m"]}
    reverse = build_low_rise_reverse_shadow_core_v2(site, preset, plane, settings, "standard")
    reverse_v3 = build_low_rise_reverse_shadow_core_v3(site, preset, plane, settings, "standard")
    replay_points = []
    for zone in (reverse.get("measurement_points") or {}).values():
        if isinstance(zone, dict):
            replay_points.extend(zone.get("points") or [])
    replay = build_shadow_state_replay(fixture, preset, replay_points,
                                       fixture.get("maximum_height_m", 31.0))
    fit = evaluate_prism_against_reverse_envelope(fixture["building_footprint"], fixture["building_height_m"], reverse)
    fit_v3 = evaluate_prism_against_reverse_envelope(fixture["building_footprint"], fixture["building_height_m"], reverse_v3)
    feasibility = None
    if fixture.get("fixture_id") == "centered_mismatch":
        validation_points = _sample_polygon(
            [(float(point[0]), float(point[1])) for point in fixture["building_footprint"]], 0.5)
        feasibility = diagnose_general_pattern_fixture_feasibility(
            site, preset, plane, settings, "standard", validation_points, fixture["building_height_m"])
    forward_within = comparison.get("status") == "within_selected_limits"
    reverse_inside = fit["fully_inside"]
    classification = (("forward_within" if forward_within else "forward_exceeds") +
                      ("_reverse_inside" if reverse_inside else "_reverse_outside"))
    if not comparison.get("complete") or not reverse.get("complete"):
        classification = "undetermined"
    selected = reverse.get("reverse_shadow_interval_optimization", {}).get("selected", {})
    return {"fixture_id": fixture["fixture_id"], "preset_id": fixture["preset_id"],
            "forward_equivalent": {"method": duration["method"], "spatial_resolution_m": 0.5,
                "temporal_step_minutes": 15, "near_max_minutes": masks.get("near", {}).get("maximum_shadow_duration_minutes"),
                "far_max_minutes": masks.get("far", {}).get("maximum_shadow_duration_minutes"),
                "near_limit_minutes": preset["near_limit_minutes"], "far_limit_minutes": preset["far_limit_minutes"],
                "near_status": comparison.get("near", {}).get("status"), "far_status": comparison.get("far", {}).get("status"),
                "overall_status": comparison.get("status")},
            "reverse_v2": {"method": METHOD_V2,
                "selected_near_interval": [selected.get("near_start_minutes"), selected.get("near_end_minutes")],
                "selected_far_interval": [selected.get("far_start_minutes"), selected.get("far_end_minutes")],
                "bounded_candidate_volume_m3": reverse.get("top_surface_mesh", {}).get("bounded_candidate_volume_m3"),
                "vertical_height_step_m": 0.5, "envelope_fit": fit},
            "reverse_v3": {"method": METHOD_V3,
                "complete": reverse_v3.get("complete"), "blockers": reverse_v3.get("blockers") or [],
                "bounded_candidate_volume_m3": reverse_v3.get("top_surface_mesh", {}).get("bounded_candidate_volume_m3"),
                "vertical_height_step_m": 0.5, "envelope_fit": fit_v3,
                "pattern_optimization": reverse_v3.get("reverse_shadow_pattern_optimization")},
            "v2_to_v3_delta": {
                "v2_maximum_height_excess_m": fit["maximum_height_excess_m"],
                "v3_maximum_height_excess_m": fit_v3["maximum_height_excess_m"],
                "height_excess_improvement_m": (fit["maximum_height_excess_m"]-fit_v3["maximum_height_excess_m"]),
                "v2_bounded_volume_m3": reverse.get("top_surface_mesh", {}).get("bounded_candidate_volume_m3"),
                "v3_bounded_volume_m3": reverse_v3.get("top_surface_mesh", {}).get("bounded_candidate_volume_m3")},
            "general_pattern_fixture_feasibility": feasibility,
            "replay": replay,
            "delta_summary": {"forward_within_selected_limits": forward_within,
                "candidate_fully_inside_reverse_envelope": reverse_inside, "mismatch_classification": classification,
                "maximum_height_excess_m": fit["maximum_height_excess_m"]},
            "legal_judgement_generated": False, "ordinance_selection_certified": False,
            "permit_ready_certified": False}
