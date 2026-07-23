# Policy constants for Dynamo_Shadow diagnostics.

TOOL_NAME = "Dynamo_Shadow"
STAGE_NAME = "v1_formal_footprint_stabilization"

LEGAL_CONSTANTS = {
    "date_basis": "winter_solstice",
    "standard_start_time": "08:00",
    "standard_end_time": "16:00",
    "time_step_minutes": 30,
    "measurement_line_near_m": 5.0,
    "measurement_line_far_m": 10.0,
    "standard_profile_note": "Standard Building Standard Law shadow period. Regional exceptions such as Hokkaido should be handled by future profiles.",
    "regional_exception_examples": {
        "hokkaido_start_time": "09:00",
        "hokkaido_end_time": "15:00",
    },
}

PLANNED_PIPELINE = [
    "input diagnostics",
    "shadow caster proxy validation",
    "shadow caster geometry access check",
    "shadow caster geometry extraction diagnostics",
    "solid / face / edge summary",
    "Revit internal unit conversion diagnostics",
    "footprint candidate diagnostics",
    "footprint edge loop diagnostics",
    "footprint extraction readiness diagnostics",
    "optional site boundary source validation",
    "property line / site property diagnostics when provided",
    "model lines fallback closed-loop diagnostics when provided",
    "settings coercion and normalization",
    "law56_2 awareness context diagnostics",
    "measurement plane readiness check",
    "measurement plane construction diagnostics",
    "pipeline readiness diagnostics",
    "formal footprint polygon generation",
    "optional site boundary loop extraction",
    "legal judgement mask preparation",
    "optional 5m / 10m measurement line generation when site_boundary is available",
    "true solar time diagnostics",
    "sun vector calculation",
    "time-slice shadow projection per caster",
    "logical union of shadows per time slice",
    "shadow duration accumulation without double counting",
    "equal-time contour generation",
    "legal judgement report",
]

INPUT_KEYS = [
    "building_elements",
    "site_boundary",
    "level",
    "settings",
]

SUPPORTED_CATEGORY_NAMES = set([
    "mass",
    "masses",
    "generic model",
    "generic models",
    "一般モデル",
    "マス",
])

ACCEPTED_BUILT_IN_CATEGORY_NAMES = set([
    "OST_GenericModel",
    "OST_Mass",
])

SITE_BOUNDARY_PRIMARY_CATEGORY_NAMES = set([
    "OST_SiteProperty",
    "OST_SitePropertyLineSegment",
])

SITE_BOUNDARY_RELATED_CATEGORY_NAMES = set([
    "OST_SitePointBoundary",
    "OST_SitePropertyTags",
    "OST_Site",
    "OST_Property",
])

SITE_BOUNDARY_FALLBACK_LINE_CATEGORY_NAMES = set([
    "OST_Lines",
    "OST_SketchLines",
    "OST_Curves",
    "OST_GenericLines",
])

SITE_BOUNDARY_TOPO_CATEGORY_NAMES = set([
    "OST_Toposolid",
    "OST_SiteSurface",
    "OST_Topography",
    "OST_TopographySurface",
])

SETTINGS_SCHEMA_VERSION = "v1"

SETTINGS_REQUIRED_FOR_EQUAL_TIME_SHADOW = [
    "average_ground_level_elevation_m",
    "measurement_height_m",
    "latitude",
    "longitude",
    "true_north_deg",
]

SETTINGS_DIAGNOSTIC_DEFAULTS = {
    "profile": "standard_8_16",
    "debug_log_enabled": False,
    "debug_log_dir": "debug_logs",
    "debug_log_filename": "latest_debug.json",
    "grid_resolution_m": 1.0,
    "analysis_margin_m": 20.0,
    "closure_tolerance_m": 0.01,
    "max_diagnostic_source_points_per_caster": 1000,
    "max_projected_points_output_per_slice": 300,
}


UNIT_CONVERSION_POLICY = {
    "purpose": "revit_internal_units_to_legal_si_meters_diagnostics",
    "diagnostic_only": True,
    "revit_internal_length_unit": "foot",
    "legal_length_unit": "meter",
    "preferred_api": "Revit DB UnitUtils",
    "fallback_length_factor": "1 ft = 0.3048 m",
    "fallback_area_factor": "1 ft2 = 0.09290304 m2",
    "fallback_volume_factor": "1 ft3 = 0.028316846592 m3",
    "reverse_length_factor": "1 m = 3.280839895013123 ft",
    "formal_geometry_projection_enabled": False,
    "legal_judgement_generated": False,
    "create_revit_elements": False,
    "raw_fields_preserved": True,
    "converted_fields_suffix": "_m / _m2 / _m3",
    "not_implemented_in_this_pr": [
        "formal footprint polygon",
        "CurveLoop",
        "shadow projection",
        "equal-time contour",
        "legal judgement",
    ],
}


SUN_POSITION_POLICY = {
    "purpose": "diagnostic_solar_time_conversion_and_sun_position_table",
    "diagnostic_only": True,
    "supported_time_basis": ["true_solar_time", "japan_standard_time"],
    "requires_explicit_settings": ["time_basis", "analysis_start_time", "analysis_end_time", "sun_time_step_minutes", "site_latitude_deg", "solar_declination_deg", "true_north_deg"],
    "jst_conversion_requires": ["site_longitude_deg", "standard_meridian_deg", "equation_of_time_minutes"],
    "formula": {
        "longitude_correction_minutes": "4.0 * (site_longitude_deg - standard_meridian_deg)",
        "true_solar_time_minutes": "japan_standard_time_minutes + longitude_correction_minutes + equation_of_time_minutes",
        "hour_angle_deg": "15 * (true_solar_hour - 12)",
        "solar_altitude": "asin(sin(latitude) * sin(declination) + cos(latitude) * cos(declination) * cos(hour_angle))",
        "solar_azimuth": "atan2(sin(hour_angle), cos(hour_angle) * sin(latitude) - tan(declination) * cos(latitude)) + 180deg",
        "model_azimuth_deg": "(true_north_azimuth_deg + true_north_deg) % 360",
        "shadow_length_factor": "1 / tan(solar_altitude) when altitude is above horizon"
    },
    "azimuth_convention": "degrees clockwise from true north: 0=N, 90=E, 180=S, 270=W",
    "true_north_convention": "true_north_deg is measured clockwise from model +Y to true north; 0 means model +Y is true north, 90 means model +X is true north, -90 means model -X is true north.",
    "atmospheric_refraction_applied": False,
    "date_based_declination_calculated": False,
    "date_based_equation_of_time_calculated": False,
    "permit_ready_certified": False,
    "not_implemented_in_this_pr": [
        "date-based winter solstice selection",
        "date-based solar declination calculation",
        "date-based equation-of-time calculation",
        "Revit ProjectLocation true-north extraction",
        "formal shadow polygons",
        "Boolean union",
        "time accumulation",
        "equal-time contours",
        "5m / 10m legal masks",
        "legal OK/NG judgement",
        "Revit element creation"
    ],
}

SHADOW_PROJECTION_POLICY = {
    "purpose": "diagnostic_shadow_projection_point_cloud",
    "diagnostic_only": True,
    "source_geometry": "meter_based_geometry_diagnostic_points",
    "measurement_plane_source": "measurement_plane.elevation_m",
    "sun_table_source": "sun_time_slices shadow_direction_vector and shadow_length_factor",
    "convex_shadow_envelope_v0": {
        "purpose": "diagnostic convex hull envelope around projected shadow point cloud",
        "diagnostic_only": True,
        "convex_hull_only": True,
        "point_source": "projected_point_cloud",
        "algorithm": "2d_monotonic_chain_convex_hull",
        "over_approximation": True,
        "true_volume_silhouette_generated": False,
        "formal_shadow_polygon_generated": False,
        "equal_time_contours_generated": False,
        "legal_masks_generated": False,
        "site_boundary_clipping_performed": False,
        "legal_judgement_generated": False,
        "revit_elements_created": False,
    },
    "formal_shadow_polygons_generated": False,
    "equal_time_contours_generated": False,
    "legal_masks_generated": False,
    "site_boundary_clipping_performed": False,
    "legal_judgement_generated": False,
    "revit_elements_created": False,
    "jst_conversion_performed": False,
    "equation_of_time_correction_performed": False,
    "uses_bounding_box_as_shadow_geometry": False,
}

DEBUG_LOG_POLICY = {
    "purpose": "development_review_debug_log",
    "enabled_by_default": False,
    "enabled_by_settings_key": "settings.debug_log_enabled",
    "default_directory": "debug_logs",
    "default_filename": "latest_debug.json",
    "committed_review_artifacts_allowed": True,
    "fixed_filename_overwrite": True,
    "timestamped_log_files_allowed": False,
    "raw_revit_object_dump_allowed": False,
    "personal_paths_allowed": False,
    "fixed_absolute_paths_allowed": False,
    "sanitized": True,
    "non_fatal_on_write_failure": True,
}

SETTINGS_POLICY = {
    "optional": True,
    "missing_settings_is_fatal": False,
    "units": {
        "length": "meter",
        "angle": "degree",
        "latitude_longitude": "decimal_degree",
    },
    "level_used_as_average_ground_level": False,
    "level_used_as_measurement_plane": False,
    "required_for_equal_time_shadow": SETTINGS_REQUIRED_FOR_EQUAL_TIME_SHADOW,
    "diagnostic_defaults": SETTINGS_DIAGNOSTIC_DEFAULTS,
    "no_legal_assumption_defaults": SETTINGS_REQUIRED_FOR_EQUAL_TIME_SHADOW,
    "formal_permit_check": "external_tool_such_as_ADS",
    "debug_log_policy": DEBUG_LOG_POLICY,
}

SITE_BOUNDARY_POLICY = {
    "optional": True,
    "required_for_equal_time_shadow": False,
    "required_for_boundary_dependent_steps": True,
    "missing_site_boundary_is_fatal": False,
    "equal_time_shadow_available_without_site_boundary": True,
    "missing_site_boundary_behavior": "skip_boundary_dependent_steps_only",
    "boundary_dependent_steps": [
        "property_line_or_site_boundary_based_offset",
        "5m_10m_measurement_line_generation",
        "boundary_based_regulation_reference_check",
    ],
    "non_boundary_dependent_steps_continue": [
        "shadow_caster_geometry_reading",
        "time_slice_shadow_projection",
        "logical_union_of_shadows_per_time_slice",
        "shadow_duration_accumulation",
        "equal_time_shadow_output",
    ],
    "primary_source": "revit_property_line_or_site_property",
    "primary_built_in_categories": [
        "BuiltInCategory.OST_SiteProperty",
        "BuiltInCategory.OST_SitePropertyLineSegment",
    ],
    "related_site_categories_diagnostic_only": [
        "BuiltInCategory.OST_SitePointBoundary",
        "BuiltInCategory.OST_Site",
        "BuiltInCategory.OST_Property",
    ],
    "fallback_source": "model_lines_closed_loop",
    "fallback_line_categories": [
        "BuiltInCategory.OST_Lines",
        "BuiltInCategory.OST_SketchLines",
        "BuiltInCategory.OST_Curves",
        "BuiltInCategory.OST_GenericLines",
    ],
    "detail_lines_allowed": False,
    "cad_import_auto_boundary": False,
    "toposolid_auto_boundary": False,
    "temporary_revit_boundary_model": False,
    "measurement_lines_generated": False,
    "formal_permit_check": "external_tool_such_as_ADS",
}

SHADOW_CASTER_POLICY = {
    "purpose": "conceptual_design_shadow_study",
    "formal_permit_check": "external_tool_such_as_ADS",
    "source_geometry": "user_defined_mass_or_generic_model_proxy",
    "multiple_shadow_casters_supported": True,
    "temporary_unified_revit_model": False,
    "per_caster_geometry_reading": True,
    "bounding_box_for_shadow_geometry": False,
    "bounding_box_for_shadow_judgement": False,
    "existing_model_auto_extraction": False,
    "allowed_initial_categories": ["BuiltInCategory.OST_Mass", "BuiltInCategory.OST_GenericModel"],
    "category_detection_priority": "built_in_category_then_localized_category_name",
    "localized_category_names_are_fallback_only": True,
    "shadow_role_overrides_category": False,
    "future_time_slice_union_policy": "logical_union",
    "double_count_overlapping_shadows": False,
}

GEOMETRY_EXTRACTION_POLICY = {
    "purpose": "shadow_caster_geometry_extraction_diagnostics",
    "read_only": True,
    "create_revit_elements": False,
    "accepted_shadow_caster_sources": ["user_selected_mass", "user_selected_generic_model"],
    "auto_extract_existing_building_model": False,
    "use_bounding_box_for_shadow_geometry": False,
    "use_bounding_box_for_shadow_judgement": False,
    "bounding_box_allowed_for": ["diagnostic_summary", "future_analysis_extent_estimation"],
    "geometry_units": "revit_raw_internal_units",
    "official_unit_conversion": "diagnostic_meter_fields_added",
    "footprint_polygon_generated": True,
    "shadow_projection_generated": "diagnostic_point_cloud_only",
    "equal_time_contours_generated": False,
}

FOOTPRINT_EXTRACTION_POLICY = {
    "purpose": "footprint_extraction_diagnostics_from_user_selected_shadow_caster_proxy",
    "diagnostic_only": True,
    "read_only": True,
    "create_revit_elements": False,
    "accepted_sources": ["bottom_face_candidate", "planar_face_edge_loops", "edge_loop_candidates"],
    "accepted_shadow_caster_sources": ["user_selected_mass", "user_selected_generic_model"],
    "auto_extract_existing_building_model": False,
    "auto_extract_walls_floors_roofs_equipment": False,
    "per_caster_extraction": True,
    "merge_casters": False,
    "temporary_unified_revit_model": False,
    "formal_footprint_polygon_generated": True,
    "curve_loop_generated": False,
    "offset_generated": False,
    "self_intersection_checked": True,
    "polygon_boolean_generated": False,
    "formal_unit_conversion": "diagnostic_meter_fields_added",
    "geometry_units": "revit_raw_internal_units",
    "measurement_plane_units": "meter",
    "bounding_box_used_for_footprint": False,
    "bounding_box_used_for_shadow_geometry": False,
    "bounding_box_used_for_legal_judgement": False,
    "same_site_multiple_buildings_awareness": "buildings_on_same_site_are_treated_as_one_building_in_future_duration_accumulation",
    "implemented_in_this_stage": [
        "formal diagnostic footprint polygon generation from eligible Line edge loops",
        "segment loop stitching",
        "outer / inner classification within each source face",
        "self-intersection check",
    ],
    "not_implemented_in_this_pr": [
        "CurveLoop creation", "boolean union across casters", "site boundary clipping",
        "own-site exclusion", "beyond-5m legal range", "formal shadow polygon generation",
        "equal-time contour generation", "legal OK/NG judgement",
    ],
}

FOOTPRINT_READINESS_REQUIRED_FOR_FUTURE_SHADOW = [
    "at least one accepted shadow caster",
    "at least one bottom face candidate",
    "at least one edge loop candidate",
    "at least one closed loop candidate",
    "measurement plane constructed for future projection context",
    "settings ready for future shadow calculation",
]

LAW56_2_AWARENESS_POLICY = {
    "purpose": "building_standard_law_article_56_2_shadow_restriction_awareness",
    "formal_permit_check": "external_tool_such_as_ADS",
    "implemented_as_legal_judgement": False,
    "legal_judgement_generated": False,
    "date_basis": "winter_solstice",
    "time_basis": "true_solar_time",
    "standard_time_window": {"start": "08:00", "end": "16:00"},
    "hokkaido_time_window": {"start": "09:00", "end": "15:00"},
    "measurement_plane_basis": "average_ground_level_plus_designated_measurement_height",
    "measurement_plane_formula": "measurement_plane_elevation_m = average_ground_level_elevation_m + measurement_height_m",
    "boundary_distance_rule_awareness": "beyond_5m_from_site_boundary",
    "exclusion_awareness": ["outside_target_area", "high_rise_residential_inducement_district", "urban_renaissance_special_district", "own_site_area"],
    "multiple_buildings_policy_awareness": "buildings_on_same_site_are_treated_as_one_building",
    "relaxation_awareness": ["road", "river", "sea", "significant_elevation_difference", "other_special_conditions_by_enforcement_order"],
    "outside_target_area_building_awareness": "building_over_10m_outside_target_area_casting_shadow_into_target_area_may_be_treated_as_in_target_area",
    "different_restriction_zones_awareness": "ordinance_and_enforcement_order_required",
    "ordinance_dependent_values": ["target_area", "applicable_building_threshold", "measurement_height_m", "allowed_shadow_duration", "selected_table_row"],
    "not_implemented_in_this_pr": ["ordinance lookup", "target area mask", "own site exclusion", "beyond 5m judgement range", "5m/10m measurement lines", "relaxation handling", "legal OK/NG judgement", "true solar time calculation", "sun vector calculation", "shadow projection", "equal-time contour generation"],
}

MEASUREMENT_PLANE_POLICY = {
    "purpose": "article_56_2_measurement_plane_construction_diagnostics",
    "create_revit_element": False,
    "internal_data_only": True,
    "plane_type": "horizontal_plane",
    "normal": "+Z",
    "coordinate_system": "legal_si_meters",
    "formula": "measurement_plane_elevation_m = average_ground_level_elevation_m + measurement_height_m",
    "average_ground_level_source": "settings.average_ground_level_elevation_m",
    "measurement_height_source": "settings.measurement_height_m",
    "revit_level_used_as_average_ground_level": False,
    "revit_level_used_as_measurement_plane": False,
    "revit_internal_unit_conversion": "diagnostic_meter_fields_added",
    "geometry_relation": "diagnostic_only",
    "formal_intersection_with_revit_geometry": "not_implemented_in_this_pr",
    "site_boundary_required_for_plane_construction": False,
    "site_boundary_required_for_legal_judgement_masks": True,
    "legal_judgement_generated": False,
}

LAW56_2_FUTURE_REQUIRED_INPUTS = [
    "ordinance_profile", "target_area_status", "applicable_building_threshold",
    "measurement_height_m", "allowed_shadow_duration_profile", "site_boundary",
    "own_site_boundary", "target_area_mask", "exclusion_area_masks",
    "road_water_relaxation_profile", "elevation_difference_relaxation_profile",
    "true_solar_time_profile", "same_site_building_group",
]

GEOMETRY_READINESS_REQUIRED_FOR_FUTURE_SHADOW = [
    "at least one accepted shadow caster",
    "at least one readable solid or mesh",
    "at least one footprint candidate or bottom face candidate",
    "measurement plane readiness from settings is recommended, but geometry diagnostics can run without it",
]

