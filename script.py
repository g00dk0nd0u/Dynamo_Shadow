# script.py
# Dynamo_Shadow v1 input diagnostics orchestration.
#
# This script intentionally does not perform shadow, sun-position, shadow
# polygon, grid accumulation, or equal-time contour calculations yet. It only
# orchestrates diagnostics implemented in shadow_*.py modules and constructs OUT.

import os
import sys
import traceback


def _ensure_local_module_path():
    """Add the script/workspace directory for Dynamo Python imports."""
    directory = None
    try:
        file_path = globals().get("__file__")
        if file_path:
            directory = os.path.dirname(os.path.abspath(file_path))
    except Exception:
        directory = None
    if not directory:
        try:
            workspace_dir = globals().get("WORKSPACE_DIR")
            if workspace_dir:
                directory = os.path.abspath(workspace_dir)
        except Exception:
            directory = None
    if directory and directory not in sys.path:
        sys.path.insert(0, directory)
    return directory


_ensure_local_module_path()

try:
    import shadow_utils as _shadow_utils
    from shadow_policies import (
        TOOL_NAME,
        STAGE_NAME,
        LEGAL_CONSTANTS,
        PLANNED_PIPELINE,
        INPUT_KEYS,
        SETTINGS_POLICY,
        SITE_BOUNDARY_POLICY,
        SHADOW_CASTER_POLICY,
        GEOMETRY_EXTRACTION_POLICY,
        FOOTPRINT_EXTRACTION_POLICY,
        MEASUREMENT_PLANE_POLICY,
        DEBUG_LOG_POLICY,
        UNIT_CONVERSION_POLICY,
        SUN_POSITION_POLICY,
        SHADOW_PROJECTION_POLICY,
    )
    from shadow_inputs import _read_inputs, _summarize_input, _diagnose_shadow_casters, _diagnose_site_boundary
    from shadow_settings import _normalize_settings
    from shadow_measurement_plane import _build_law56_2_awareness_context, _construct_measurement_plane
    from shadow_geometry import _diagnose_shadow_caster_geometry
    from shadow_footprint import _build_footprint_extraction_summary
    from shadow_readiness import _build_pipeline_readiness
    from shadow_debug import _write_debug_log_if_enabled, _build_debug_log_status
    from shadow_units import _build_unit_conversion_diagnostics
    from shadow_sun import _build_sun_position_diagnostics
    from shadow_projection import _build_shadow_projection_diagnostics
except Exception:
    _IMPORT_ERROR_TEXT = traceback.format_exc()
else:
    _IMPORT_ERROR_TEXT = None


def _sync_dynamo_runtime_globals():
    """Expose Dynamo-provided globals to helper modules without importing Dynamo."""
    if _IMPORT_ERROR_TEXT is not None:
        return
    for name in ("IN", "INPUTS", "UnwrapElement"):
        if name in globals():
            try:
                setattr(_shadow_utils, name, globals().get(name))
            except Exception:
                pass


def _minimal_import_failure(error_text):
    unit_conversion_diagnostics = None
    unit_conversion_policy = None
    unit_conversion_warnings = []
    try:
        if "_build_unit_conversion_diagnostics" in globals():
            unit_conversion_diagnostics = _build_unit_conversion_diagnostics()
        if "UNIT_CONVERSION_POLICY" in globals():
            unit_conversion_policy = UNIT_CONVERSION_POLICY
        if isinstance(unit_conversion_diagnostics, dict):
            unit_conversion_warnings = list(unit_conversion_diagnostics.get("warnings", []))
    except Exception:
        unit_conversion_diagnostics = None
        unit_conversion_policy = None
        unit_conversion_warnings = []

    return {
        "success": False,
        "tool": "Dynamo_Shadow",
        "stage": "v1_footprint_extraction_diagnostics",
        "message": "script.py failed while importing diagnostic modules.",
        "warnings": unit_conversion_warnings,
        "error": error_text,
        "debug_log": {
            "enabled": False,
            "attempted": False,
            "written": False,
            "path": None,
            "relative_path": None,
            "warnings": [],
            "error": None,
        },
        "unit_conversion_diagnostics": unit_conversion_diagnostics,
        "unit_conversion_policy": unit_conversion_policy,
        "shadow_projection_diagnostics": None,
        "shadow_projection_policy": globals().get("SHADOW_PROJECTION_POLICY"),
        "debug_log_policy": {
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
        },
    }


def _build_success():
    _sync_dynamo_runtime_globals()
    raw_inputs, input_source = _read_inputs()
    warnings = []
    unit_conversion_diagnostics = _build_unit_conversion_diagnostics()

    for key in INPUT_KEYS:
        if key in ("site_boundary", "settings"):
            continue
        if raw_inputs.get(key) is None:
            warnings.append("{0} input is empty.".format(key))

    shadow_casters = _diagnose_shadow_casters(raw_inputs.get("building_elements"))
    site_boundary = _diagnose_site_boundary(raw_inputs.get("site_boundary"))
    settings_normalized = _normalize_settings(raw_inputs.get("settings"), raw_inputs.get("level"))
    law56_2_awareness = _build_law56_2_awareness_context(settings_normalized, site_boundary)
    measurement_plane = _construct_measurement_plane(settings_normalized, raw_inputs.get("level"))
    shadow_caster_geometry = _diagnose_shadow_caster_geometry(raw_inputs.get("building_elements"), shadow_casters, settings_normalized, measurement_plane)
    footprint_extraction = _build_footprint_extraction_summary(shadow_caster_geometry, measurement_plane, settings_normalized, site_boundary)
    sun_time_slices, sun_position_diagnostics, sun_position_policy, solar_calculation_v1 = _build_sun_position_diagnostics(settings_normalized)
    shadow_projection_diagnostics, shadow_projection_policy = _build_shadow_projection_diagnostics(shadow_caster_geometry, measurement_plane, sun_time_slices)
    pipeline_readiness = _build_pipeline_readiness(shadow_casters, site_boundary, settings_normalized, shadow_caster_geometry, measurement_plane, footprint_extraction)
    warnings.extend(shadow_casters.get("warnings", []))
    warnings.extend(site_boundary.get("warnings", []))
    warnings.extend(settings_normalized.get("warnings", []))
    warnings.extend(law56_2_awareness.get("warnings", []))
    warnings.extend(measurement_plane.get("warnings", []))
    warnings.extend(shadow_caster_geometry.get("warnings", []))
    warnings.extend(footprint_extraction.get("warnings", []))
    warnings.extend(sun_position_diagnostics.get("warnings", []))
    warnings.extend(shadow_projection_diagnostics.get("warnings", []))
    warnings.extend(pipeline_readiness.get("blockers_for_equal_time_shadow", []))
    warnings.extend(pipeline_readiness.get("blockers_for_footprint_extraction", []))
    warnings.extend(pipeline_readiness.get("blockers_for_measurement_plane", []))
    warnings.extend(pipeline_readiness.get("blockers_for_future_projection_context", []))
    warnings.extend(pipeline_readiness.get("blockers_for_future_shadow_projection", []))
    warnings.extend(pipeline_readiness.get("blockers_for_legal_judgement_masks", []))
    warnings.extend(unit_conversion_diagnostics.get("warnings", []))
    if not pipeline_readiness.get("boundary_dependent_steps_ready"):
        warnings.extend(pipeline_readiness.get("blockers_for_boundary_dependent_steps", []))

    out_payload = {
        "success": True,
        "tool": TOOL_NAME,
        "stage": STAGE_NAME,
        "message": "Dynamo_Shadow v1 diagnostics; formal diagnostic footprint polygons are generated from eligible bottom-face Line edge loops. No formal shadow polygon generation, Revit element creation, date-based declination/equation-of-time calculation, legal judgement, 5m/10m measurement line generation, Boolean union, or equal-time contours are implemented. Diagnostic-only true-solar-time sun position and shadow projection point-cloud outputs are included when explicit site_latitude_deg and solar_declination_deg are provided.",
        "legal_constants": LEGAL_CONSTANTS,
        "unit_conversion_diagnostics": unit_conversion_diagnostics,
        "unit_conversion_policy": UNIT_CONVERSION_POLICY,
        "inputs": {
            "source": input_source,
            "building_elements": _summarize_input(raw_inputs.get("building_elements")),
            "site_boundary": _summarize_input(raw_inputs.get("site_boundary")),
            "level": _summarize_input(raw_inputs.get("level")),
            "settings": _summarize_input(raw_inputs.get("settings")),
        },
        "shadow_casters": shadow_casters,
        "shadow_caster_policy": SHADOW_CASTER_POLICY,
        "shadow_caster_geometry": shadow_caster_geometry,
        "footprint_extraction": footprint_extraction,
        "footprint_extraction_policy": FOOTPRINT_EXTRACTION_POLICY,
        "sun_time_slices": sun_time_slices,
        "sun_position_diagnostics": sun_position_diagnostics,
        "solar_calculation_v1": solar_calculation_v1,
        "sun_position_policy": sun_position_policy,
        "shadow_projection_diagnostics": shadow_projection_diagnostics,
        "shadow_projection_policy": shadow_projection_policy,
        "law56_2_awareness": law56_2_awareness,
        "measurement_plane": measurement_plane,
        "measurement_plane_policy": MEASUREMENT_PLANE_POLICY,
        "geometry_extraction_policy": GEOMETRY_EXTRACTION_POLICY,
        "site_boundary": site_boundary,
        "site_boundary_policy": SITE_BOUNDARY_POLICY,
        "settings_normalized": settings_normalized,
        "settings_policy": SETTINGS_POLICY,
        "pipeline_readiness": pipeline_readiness,
        "planned_pipeline": PLANNED_PIPELINE,
        "warnings": warnings,
        "debug_log": _build_debug_log_status(False, False),
        "debug_log_policy": DEBUG_LOG_POLICY,
    }
    debug_log_status = _write_debug_log_if_enabled(out_payload, settings_normalized)
    out_payload["debug_log"] = debug_log_status
    if debug_log_status.get("warnings"):
        out_payload["warnings"].extend(debug_log_status.get("warnings"))
    return out_payload


def _build_failure(error_text):
    _sync_dynamo_runtime_globals()
    raw_inputs, input_source = _read_inputs()
    shadow_casters = None
    site_boundary = None
    settings_normalized = None
    pipeline_readiness = None
    shadow_caster_geometry = None
    law56_2_awareness = None
    measurement_plane = None
    footprint_extraction = None
    sun_time_slices = []
    sun_position_diagnostics = None
    sun_position_policy = SUN_POSITION_POLICY
    shadow_projection_diagnostics = None
    shadow_projection_policy = SHADOW_PROJECTION_POLICY
    try:
        unit_conversion_diagnostics = _build_unit_conversion_diagnostics()
    except Exception:
        unit_conversion_diagnostics = {"available": False, "diagnostic_only": True, "warnings": ["unit conversion diagnostics could not be built during failure handling"]}
    try:
        shadow_casters = _diagnose_shadow_casters(raw_inputs.get("building_elements"))
    except Exception:
        shadow_casters = None
    try:
        site_boundary = _diagnose_site_boundary(raw_inputs.get("site_boundary"))
    except Exception:
        site_boundary = None
    try:
        settings_normalized = _normalize_settings(raw_inputs.get("settings"), raw_inputs.get("level"))
    except Exception:
        settings_normalized = None
    try:
        law56_2_awareness = _build_law56_2_awareness_context(settings_normalized or {}, site_boundary or {})
    except Exception:
        law56_2_awareness = None
    try:
        measurement_plane = _construct_measurement_plane(settings_normalized or {}, raw_inputs.get("level"))
    except Exception:
        measurement_plane = None
    try:
        shadow_caster_geometry = _diagnose_shadow_caster_geometry(raw_inputs.get("building_elements"), shadow_casters or {}, settings_normalized or {}, measurement_plane)
        footprint_extraction = _build_footprint_extraction_summary(shadow_caster_geometry, measurement_plane, settings_normalized or {}, site_boundary or {})
        sun_time_slices, sun_position_diagnostics, sun_position_policy = _build_sun_position_diagnostics(settings_normalized or {})
        shadow_projection_diagnostics, shadow_projection_policy = _build_shadow_projection_diagnostics(shadow_caster_geometry, measurement_plane, sun_time_slices)
        pipeline_readiness = _build_pipeline_readiness(shadow_casters or {}, site_boundary or {}, settings_normalized or {}, shadow_caster_geometry, measurement_plane, footprint_extraction)
    except Exception:
        pipeline_readiness = None

    out_payload = {
        "success": False,
        "tool": TOOL_NAME,
        "stage": STAGE_NAME,
        "message": "script.py failed while building v1 footprint extraction diagnostics.",
        "legal_constants": LEGAL_CONSTANTS,
        "unit_conversion_diagnostics": unit_conversion_diagnostics,
        "unit_conversion_policy": UNIT_CONVERSION_POLICY,
        "inputs": {
            "source": input_source,
            "building_elements": _summarize_input(raw_inputs.get("building_elements")),
            "site_boundary": _summarize_input(raw_inputs.get("site_boundary")),
            "level": _summarize_input(raw_inputs.get("level")),
            "settings": _summarize_input(raw_inputs.get("settings")),
        },
        "shadow_casters": shadow_casters,
        "shadow_caster_policy": SHADOW_CASTER_POLICY,
        "shadow_caster_geometry": shadow_caster_geometry,
        "footprint_extraction": footprint_extraction,
        "footprint_extraction_policy": FOOTPRINT_EXTRACTION_POLICY,
        "sun_time_slices": sun_time_slices,
        "sun_position_diagnostics": sun_position_diagnostics,
        "solar_calculation_v1": solar_calculation_v1,
        "sun_position_policy": sun_position_policy,
        "shadow_projection_diagnostics": shadow_projection_diagnostics,
        "shadow_projection_policy": shadow_projection_policy,
        "law56_2_awareness": law56_2_awareness,
        "measurement_plane": measurement_plane,
        "measurement_plane_policy": MEASUREMENT_PLANE_POLICY,
        "geometry_extraction_policy": GEOMETRY_EXTRACTION_POLICY,
        "site_boundary": site_boundary,
        "site_boundary_policy": SITE_BOUNDARY_POLICY,
        "settings_normalized": settings_normalized,
        "settings_policy": SETTINGS_POLICY,
        "pipeline_readiness": pipeline_readiness,
        "planned_pipeline": PLANNED_PIPELINE,
        "warnings": list(unit_conversion_diagnostics.get("warnings", [])),
        "error": error_text,
        "debug_log": _build_debug_log_status(False, False),
        "debug_log_policy": DEBUG_LOG_POLICY,
    }
    debug_log_status = _write_debug_log_if_enabled(out_payload, settings_normalized)
    out_payload["debug_log"] = debug_log_status
    if debug_log_status.get("warnings"):
        out_payload["warnings"].extend(debug_log_status.get("warnings"))
    return out_payload


if _IMPORT_ERROR_TEXT is not None:
    OUT = _minimal_import_failure(_IMPORT_ERROR_TEXT)
else:
    try:
        OUT = _build_success()
    except Exception:
        OUT = _build_failure(traceback.format_exc())
