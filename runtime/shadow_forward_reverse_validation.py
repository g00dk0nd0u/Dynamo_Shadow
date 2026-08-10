"""Fixed-input comparison between prismatic Forward-equivalent and Reverse v2."""
from shadow_forward_equivalent_validator import build_prismatic_forward_equivalent_duration
from shadow_reverse_envelope_evaluation import (_sample_polygon,
    evaluate_prism_against_reverse_envelope, interpolate_reverse_height)
from shadow_regulatory_comparison import build_selected_limit_comparison
from shadow_regulatory_presets import resolve_regulatory_shadow_preset
from shadow_reverse_low_rise import (METHOD_V2, METHOD_V3,
    build_low_rise_reverse_shadow_core_v2, build_low_rise_reverse_shadow_core_v3,
    diagnose_general_pattern_fixture_feasibility)
from shadow_settings import _normalize_settings
from shadow_site_masks import build_measurement_masks
from shadow_reverse_state_replay import build_shadow_state_replay
from shadow_reverse_forward_expansion import (build_forward_validated_reverse_expansion,
                                               prism_fits_cell_field)


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
    reverse_expansion_core = build_forward_validated_reverse_expansion(
        site, preset, plane, settings, "standard",
        maximum_height_m=float(fixture.get("maximum_height_m", fixture["building_height_m"])))
    expansion_fit = prism_fits_cell_field(fixture["building_footprint"], fixture["building_height_m"],
        reverse_expansion_core.get("cell_field", {}).get("cells") or [])
    replay_points = []
    for zone in (reverse.get("measurement_points") or {}).values():
        if isinstance(zone, dict):
            replay_points.extend(zone.get("points") or [])
    fit = evaluate_prism_against_reverse_envelope(fixture["building_footprint"], fixture["building_height_m"], reverse)
    fit_v3 = evaluate_prism_against_reverse_envelope(fixture["building_footprint"], fixture["building_height_m"], reverse_v3)
    replay = build_shadow_state_replay(
        fixture, preset, replay_points, site, settings,
        fixture.get("maximum_height_m", 31.0),
        zone_common_v2_or_v3_excess_m=min(fit["maximum_height_excess_m"],
                                           fit_v3["maximum_height_excess_m"]))
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
            "reverse_expansion": {"method": reverse_expansion_core.get("method"),
                "complete": reverse_expansion_core.get("complete"), "selected_source": reverse_expansion_core.get("selected_source"),
                "maximum_height_m": reverse_expansion_core.get("maximum_height_m"),
                "cell_volume_m3": reverse_expansion_core.get("cell_field", {}).get("volume_m3"),
                "envelope_fit": expansion_fit, "full_forward_validation": reverse_expansion_core.get("full_forward_validation"),
                "comparison": reverse_expansion_core.get("comparison"), "expansion": reverse_expansion_core.get("expansion"),
                "constraint_generation": reverse_expansion_core.get("constraint_generation"),
                "blockers": reverse_expansion_core.get("blockers") or []},
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
