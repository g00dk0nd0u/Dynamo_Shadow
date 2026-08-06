# Pipeline readiness diagnostics.


def _build_pipeline_readiness(shadow_casters, site_boundary, settings_normalized, shadow_caster_geometry=None, measurement_plane=None, footprint_extraction=None, formal_shadow_polygons=None, solar_calculation=None, unified_shadow_slices=None, shadow_duration=None, equal_time_contours=None, site_boundary_area_extraction=None, site_boundary_geometry=None, measurement_masks=None, resolved_regulatory_preset=None, selected_limit_comparison=None, legal_judgement=None, site_distance_contours=None, site_result_preview=None):
    blockers_equal = []
    blockers_boundary = []
    shadow_ready = (shadow_casters or {}).get("accepted_count", 0) > 0
    settings_ready = ((settings_normalized or {}).get("readiness") or {}).get("ready_for_equal_time_shadow_calculation") is True
    geom_ready = ((shadow_caster_geometry or {}).get("readiness") or {}).get("geometry_diagnostics_ready") is True
    footprint_ready = ((footprint_extraction or {}).get("readiness") or {}).get("ready_for_future_footprint_polygon_generation") is True
    mp_readiness = (measurement_plane or {}).get("readiness") or {}
    measurement_plane_ready = mp_readiness.get("measurement_plane_constructed") is True
    future_projection_context_ready = mp_readiness.get("ready_for_future_shadow_projection_context") is True
    site_boundary_input_ready = (site_boundary_area_extraction or {}).get("complete") is True
    site_boundary_area_ready = site_boundary_input_ready
    site_boundary_geometry_ready = (site_boundary_geometry or {}).get("complete") is True
    measurement_masks_ready = (measurement_masks or {}).get("complete") is True
    site_distance_contours_ready = ((site_distance_contours or {}).get("complete") is True and (site_distance_contours or {}).get("ready_for_revit_preview") is True)
    selected_limit_pair_selected = (resolved_regulatory_preset or {}).get("comparison_ready") is True
    selected_limit_comparison_ready = (selected_limit_pair_selected and measurement_masks_ready and (selected_limit_comparison or {}).get("complete") is True)
    boundary_evaluation_coverage_complete = (shadow_duration or {}).get("boundary_evaluation_coverage_complete") is True
    legal_judgement_masks_ready = False
    site_result_preview_enabled = (site_result_preview or {}).get("enabled") is True
    site_result_preview_attempted = (site_result_preview or {}).get("attempted") is True
    site_result_preview_complete = (site_result_preview or {}).get("complete") is True
    preview_groups = (site_result_preview or {}).get("groups") or []
    site_distance_revit_preview_created = all(any(g.get("output_kind") == "site_distance_contour" and abs(float(g.get("distance_m", -999)) - d) <= 1e-9 and g.get("created") is True for g in preview_groups) for d in (5.0, 10.0))
    available_marker_zones = [z for z in ("near_5_to_10m", "far_over_10m") if any(g.get("output_kind") == "maximum_shadow_duration_marker" and g.get("zone") == z for g in preview_groups)]
    maximum_duration_point_preview_created = bool(available_marker_zones) and all(any(g.get("output_kind") == "maximum_shadow_duration_marker" and g.get("zone") == z and g.get("created") is True for g in preview_groups) for z in available_marker_zones)
    future_projection_ready = footprint_ready and measurement_plane_ready and settings_ready
    blockers_fp = list(((footprint_extraction or {}).get("readiness") or {}).get("blockers_for_future_footprint_polygon_generation") or [])
    blockers_mp = list(mp_readiness.get("blockers_for_measurement_plane") or [])
    blockers_projection = []
    if not footprint_ready:
        blockers_projection.extend(blockers_fp)
    if not measurement_plane_ready:
        blockers_projection.extend(blockers_mp)
    if not settings_ready:
        blockers_projection.append("Settings are not ready for future equal-time shadow calculation.")
    blockers_legal = list(mp_readiness.get("blockers_for_legal_judgement_masks") or [])
    blockers_legal_judgement = []
    for code in ("ordinance_applicability_not_certified", "local_ordinance_reference_missing", "legal_profile_schema_not_implemented"):
        if code not in [item.get("failure_code") for item in blockers_legal_judgement]:
            blockers_legal_judgement.append({"failure_code": code})
    blockers_selected_limit = []
    if not shadow_ready:
        blockers_equal.append("No accepted shadow caster proxy elements are available.")
    if not settings_ready:
        missing = ((settings_normalized or {}).get("readiness") or {}).get("missing_for_equal_time_shadow") or []
        invalid = ((settings_normalized or {}).get("readiness") or {}).get("invalid_for_equal_time_shadow") or []
        blockers_equal.append("Settings are not ready for future equal-time shadow calculation; missing={0}, invalid={1}.".format(missing, invalid))
    if not measurement_plane_ready:
        blockers_equal.extend(blockers_mp)
    equal_ready = shadow_ready and settings_ready and measurement_plane_ready and footprint_ready
    blockers_boundary.extend(list((site_boundary_area_extraction or {}).get("blockers") or []))
    blockers_boundary.extend(list((site_boundary_geometry or {}).get("blockers") or []))
    formal = formal_shadow_polygons or {}
    solar = solar_calculation or {}
    union = unified_shadow_slices or {}
    union_complete = union.get("complete") is True
    duration_ready = (solar.get("formal_solar_calculation_ready") is True
                      and formal.get("complete") is True and union_complete
                      and union.get("ready_for_duration_accumulation") is True
                      and union.get("time_slice_count") == solar.get("slice_count"))
    duration_complete = (shadow_duration or {}).get("complete") is True
    blockers_boundary.extend(list((shadow_duration or {}).get("boundary_evaluation_blockers") or []))
    blockers_boundary.extend(list((measurement_masks or {}).get("blockers") or []))
    contours_complete = (equal_time_contours or {}).get("complete") is True
    next_steps = ([] if contours_complete else (["equal-time contour generation"] if duration_complete else
                  ["shadow duration accumulation", "equal-time contour generation"]))
    if not site_boundary_geometry_ready:
        next_steps.append("site boundary")
    if not measurement_masks_ready:
        next_steps.append("5m / 10m distance masks")
    if not site_distance_contours_ready:
        next_steps.append("5m / 10m geometry preparation")
    if selected_limit_pair_selected and not selected_limit_comparison_ready:
        next_steps.append("selected limit comparison")
    next_steps.extend(["selected-limit exceedance styling", "legal judgement", "report output", "reverse shadow"])
    return {
        "input_diagnostics_ready": True,
        "shadow_caster_ready": shadow_ready,
        "shadow_caster_geometry_ready": geom_ready,
        "footprint_diagnostics_ready": ((footprint_extraction or {}).get("readiness") or {}).get("footprint_diagnostics_ready") is True,
        "footprint_loop_candidates_ready": footprint_ready,
        "future_footprint_polygon_generation_ready": footprint_ready,
        "footprint_extraction_ready": footprint_ready,
        "measurement_plane_ready": measurement_plane_ready,
        "measurement_plane_constructed": measurement_plane_ready,
        "future_projection_context_ready": future_projection_context_ready,
        "future_shadow_projection_ready": future_projection_ready,
        "legal_judgement_masks_ready": legal_judgement_masks_ready,
        "site_boundary_area_ready": site_boundary_area_ready,
        "site_boundary_geometry_ready": site_boundary_geometry_ready,
        "measurement_masks_ready": measurement_masks_ready,
        "site_distance_contours_ready": site_distance_contours_ready,
        "selected_limit_pair_selected": selected_limit_pair_selected,
        "selected_limit_comparison_ready": selected_limit_comparison_ready,
        "site_result_preview_enabled": site_result_preview_enabled,
        "site_result_preview_attempted": site_result_preview_attempted,
        "site_result_preview_complete": site_result_preview_complete,
        "site_distance_revit_preview_created": site_distance_revit_preview_created,
        "maximum_duration_point_preview_created": maximum_duration_point_preview_created,
        "boundary_evaluation_coverage_complete": boundary_evaluation_coverage_complete,
        "settings_ready_for_equal_time_shadow": settings_ready,
        "formal_solar_calculation_ready": solar.get("formal_solar_calculation_ready") is True,
        "regulatory_profile_resolved": solar.get("regulatory_profile_resolved") is True,
        "solar_coordinate_convention_resolved": solar.get("solar_coordinate_convention_resolved") is True,
        "solar_reference_validation_passed": solar.get("solar_reference_validation_passed") is True,
        "permit_ready_certified": False,
        "legal_judgement_ready": False,
        "site_boundary_required_for_equal_time_shadow": False,
        "site_boundary_input_ready": site_boundary_input_ready,
        "site_boundary_ready_for_boundary_dependent_steps": site_boundary_input_ready and site_boundary_geometry_ready,
        "equal_time_shadow_calculation_ready": equal_ready,
        "boundary_dependent_steps_ready": site_boundary_area_ready and site_boundary_geometry_ready and duration_complete and boundary_evaluation_coverage_complete and measurement_masks_ready,
        "formal_shadow_polygon_generation_attempted": formal_shadow_polygons is not None,
        "formal_shadow_polygon_generation_available": formal.get("available") is True,
        "formal_shadow_polygon_generation_complete": formal.get("complete") is True,
        "blockers_for_formal_shadow_polygon_generation": list(formal.get("blockers") or []),
        "formal_shadow_union_attempted": unified_shadow_slices is not None,
        "formal_shadow_union_available": union.get("available") is True,
        "formal_shadow_union_complete": union_complete,
        "blockers_for_formal_shadow_union": list(union.get("blockers") or []),
        "ready_for_duration_accumulation": duration_ready,
        "shadow_duration_accumulation_complete": duration_complete,
        "ready_for_equal_time_contour_generation": (shadow_duration or {}).get("ready_for_equal_time_contour_generation") is True,
        "equal_time_contours_complete": contours_complete,
        "blockers_for_equal_time_shadow": blockers_equal,
        "blockers_for_footprint_extraction": blockers_fp,
        "blockers_for_future_footprint_polygon_generation": blockers_fp,
        "blockers_for_measurement_plane": blockers_mp,
        "blockers_for_future_projection_context": list(mp_readiness.get("blockers_for_future_shadow_projection_context") or []),
        "blockers_for_future_shadow_projection": blockers_projection,
        "blockers_for_site_boundary_area": list((site_boundary_area_extraction or {}).get("blockers") or []),
        "blockers_for_site_boundary_geometry": list((site_boundary_geometry or {}).get("blockers") or []),
        "blockers_for_measurement_masks": list((measurement_masks or {}).get("blockers") or []),
        "blockers_for_site_distance_contours": list((site_distance_contours or {}).get("blockers") or []),
        "blockers_for_site_result_preview": list((site_result_preview or {}).get("blockers") or []),
        "blockers_for_selected_limit_comparison": blockers_selected_limit + list((selected_limit_comparison or {}).get("blockers") or []),
        "blockers_for_legal_judgement": blockers_legal_judgement,
        "blockers_for_legal_judgement_masks": blockers_legal,
        "blockers_for_boundary_dependent_steps": blockers_boundary,
        "info": ["Duration accumulation is a grid/trapezoidal numerical approximation; site_boundary is required only for later legal judgement."],
        "next_implementation_steps": next_steps,
    }
