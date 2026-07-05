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
    )
    from shadow_inputs import _read_inputs, _summarize_input, _diagnose_shadow_casters, _diagnose_site_boundary
    from shadow_settings import _normalize_settings
    from shadow_measurement_plane import _build_law56_2_awareness_context, _construct_measurement_plane
    from shadow_geometry import _diagnose_shadow_caster_geometry
    from shadow_footprint import _build_footprint_extraction_summary
    from shadow_readiness import _build_pipeline_readiness
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
    return {
        "success": False,
        "tool": "Dynamo_Shadow",
        "stage": "v1_footprint_extraction_diagnostics",
        "message": "script.py failed while importing diagnostic modules.",
        "warnings": [],
        "error": error_text,
    }


def _build_success():
    _sync_dynamo_runtime_globals()
    raw_inputs, input_source = _read_inputs()
    warnings = []

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
    pipeline_readiness = _build_pipeline_readiness(shadow_casters, site_boundary, settings_normalized, shadow_caster_geometry, measurement_plane, footprint_extraction)
    warnings.extend(shadow_casters.get("warnings", []))
    warnings.extend(site_boundary.get("warnings", []))
    warnings.extend(settings_normalized.get("warnings", []))
    warnings.extend(law56_2_awareness.get("warnings", []))
    warnings.extend(measurement_plane.get("warnings", []))
    warnings.extend(shadow_caster_geometry.get("warnings", []))
    warnings.extend(footprint_extraction.get("warnings", []))
    warnings.extend(pipeline_readiness.get("blockers_for_equal_time_shadow", []))
    warnings.extend(pipeline_readiness.get("blockers_for_footprint_extraction", []))
    warnings.extend(pipeline_readiness.get("blockers_for_measurement_plane", []))
    warnings.extend(pipeline_readiness.get("blockers_for_future_projection_context", []))
    warnings.extend(pipeline_readiness.get("blockers_for_future_shadow_projection", []))
    warnings.extend(pipeline_readiness.get("blockers_for_legal_judgement_masks", []))
    if not pipeline_readiness.get("boundary_dependent_steps_ready"):
        warnings.extend(pipeline_readiness.get("blockers_for_boundary_dependent_steps", []))

    return {
        "success": True,
        "tool": TOOL_NAME,
        "stage": STAGE_NAME,
        "message": "Dynamo_Shadow v1 input diagnostics only; footprint extraction diagnostics added. Bottom face / edge loop candidates are diagnosed, but no formal footprint polygon generation, Revit element creation, true solar time calculation, sun vector calculation, shadow projection, legal judgement, 5m/10m measurement line generation, or equal-time contours are implemented.",
        "legal_constants": LEGAL_CONSTANTS,
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
    }


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
        pipeline_readiness = _build_pipeline_readiness(shadow_casters or {}, site_boundary or {}, settings_normalized or {}, shadow_caster_geometry, measurement_plane, footprint_extraction)
    except Exception:
        pipeline_readiness = None

    return {
        "success": False,
        "tool": TOOL_NAME,
        "stage": STAGE_NAME,
        "message": "script.py failed while building v1 footprint extraction diagnostics.",
        "legal_constants": LEGAL_CONSTANTS,
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
        "warnings": [],
        "error": error_text,
    }


if _IMPORT_ERROR_TEXT is not None:
    OUT = _minimal_import_failure(_IMPORT_ERROR_TEXT)
else:
    try:
        OUT = _build_success()
    except Exception:
        OUT = _build_failure(traceback.format_exc())
