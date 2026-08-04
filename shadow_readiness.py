# Pipeline readiness diagnostics.


def _build_pipeline_readiness(shadow_casters, site_boundary, settings_normalized, shadow_caster_geometry=None, measurement_plane=None, footprint_extraction=None, formal_shadow_polygons=None, solar_calculation=None, unified_shadow_slices=None, shadow_duration=None):
    blockers_equal = []
    blockers_boundary = []
    shadow_ready = (shadow_casters or {}).get("accepted_count", 0) > 0
    settings_ready = ((settings_normalized or {}).get("readiness") or {}).get("ready_for_equal_time_shadow_calculation") is True
    boundary_ready = (site_boundary or {}).get("boundary_dependent_steps_available") is True
    geom_ready = ((shadow_caster_geometry or {}).get("readiness") or {}).get("geometry_diagnostics_ready") is True
    footprint_ready = ((footprint_extraction or {}).get("readiness") or {}).get("ready_for_future_footprint_polygon_generation") is True
    mp_readiness = (measurement_plane or {}).get("readiness") or {}
    measurement_plane_ready = mp_readiness.get("measurement_plane_constructed") is True
    future_projection_context_ready = mp_readiness.get("ready_for_future_shadow_projection_context") is True
    legal_judgement_masks_ready = False
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
    if not boundary_ready:
        blockers_legal.append("site_boundary is missing or not usable as a closed boundary; future legal judgement masks such as beyond-5m range and own-site exclusion are blocked.")
    if not shadow_ready:
        blockers_equal.append("No accepted shadow caster proxy elements are available.")
    if not settings_ready:
        missing = ((settings_normalized or {}).get("readiness") or {}).get("missing_for_equal_time_shadow") or []
        invalid = ((settings_normalized or {}).get("readiness") or {}).get("invalid_for_equal_time_shadow") or []
        blockers_equal.append("Settings are not ready for future equal-time shadow calculation; missing={0}, invalid={1}.".format(missing, invalid))
    if not measurement_plane_ready:
        blockers_equal.extend(blockers_mp)
    equal_ready = shadow_ready and settings_ready and measurement_plane_ready and footprint_ready
    if not equal_ready:
        blockers_boundary.append("Boundary-dependent steps require shadow caster, settings, and measurement plane readiness first.")
    if not boundary_ready:
        blockers_boundary.append("site_boundary is missing or not usable as a closed boundary; boundary-dependent steps remain skipped.")
    formal = formal_shadow_polygons or {}
    solar = solar_calculation or {}
    union = unified_shadow_slices or {}
    union_complete = union.get("complete") is True
    duration_ready = (solar.get("formal_solar_calculation_ready") is True
                      and formal.get("complete") is True and union_complete
                      and union.get("ready_for_duration_accumulation") is True
                      and union.get("time_slice_count") == solar.get("slice_count"))
    duration_complete = (shadow_duration or {}).get("complete") is True
    next_steps = (["equal-time contour generation"] if duration_complete else
                  ["shadow duration accumulation", "equal-time contour generation"])
    next_steps.extend(["site boundary", "5m / 10m lines", "legal judgement"])
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
        "settings_ready_for_equal_time_shadow": settings_ready,
        "formal_solar_calculation_ready": solar.get("formal_solar_calculation_ready") is True,
        "regulatory_profile_resolved": solar.get("regulatory_profile_resolved") is True,
        "solar_coordinate_convention_resolved": solar.get("solar_coordinate_convention_resolved") is True,
        "solar_reference_validation_passed": solar.get("solar_reference_validation_passed") is True,
        "permit_ready_certified": False,
        "legal_judgement_ready": False,
        "site_boundary_required_for_equal_time_shadow": False,
        "site_boundary_ready_for_boundary_dependent_steps": boundary_ready,
        "equal_time_shadow_calculation_ready": equal_ready,
        "boundary_dependent_steps_ready": equal_ready and boundary_ready,
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
        "blockers_for_equal_time_shadow": blockers_equal,
        "blockers_for_footprint_extraction": blockers_fp,
        "blockers_for_future_footprint_polygon_generation": blockers_fp,
        "blockers_for_measurement_plane": blockers_mp,
        "blockers_for_future_projection_context": list(mp_readiness.get("blockers_for_future_shadow_projection_context") or []),
        "blockers_for_future_shadow_projection": blockers_projection,
        "blockers_for_legal_judgement_masks": blockers_legal,
        "blockers_for_boundary_dependent_steps": blockers_boundary,
        "info": ["Duration accumulation is a grid/trapezoidal numerical approximation; site_boundary is required only for later legal judgement."],
        "next_implementation_steps": next_steps,
    }
