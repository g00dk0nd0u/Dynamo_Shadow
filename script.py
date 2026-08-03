# script.py
# Dynamo_Shadow v1 input diagnostics orchestration.
#
# This script intentionally does not perform shadow, sun-position, shadow
# polygon, grid accumulation, or equal-time contour calculations yet. It only
# orchestrates diagnostics implemented in shadow_*.py modules and constructs OUT.

import os
import sys
import traceback

_RUNTIME_CHECKPOINT = globals().get("RUNTIME_CHECKPOINT")


def _checkpoint(stage, detail=None):
    callback = _RUNTIME_CHECKPOINT
    if callback is None:
        return
    try:
        callback(stage, detail)
    except BaseException:
        pass


_checkpoint("SCRIPT_ENTER")


def _ensure_local_module_path():
    """Force the script/workspace directory to the front for local imports."""
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
    normalized_directory = _normalized_path(directory)
    if normalized_directory:
        retained = []
        for entry in sys.path:
            try:
                normalized_entry = _normalized_path(entry)
            except Exception:
                normalized_entry = None
            if normalized_entry != normalized_directory:
                retained.append(entry)
        sys.path[:] = [normalized_directory] + retained
    return normalized_directory


def _normalized_path(value):
    if not value:
        return None
    return os.path.normcase(os.path.normpath(os.path.abspath(value)))


_SCRIPT_DIRECTORY = _ensure_local_module_path()
_LOADER_BOOTSTRAP = globals().get("RUNTIME_IMPORT_BOOTSTRAP")

_checkpoint("SHADOW_IMPORTS_BEFORE")
try:
    import shadow_utils as _shadow_utils
    from shadow_policies import (
        CODE_BUILD_ID,
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
        FORMAL_SHADOW_PROJECTION_POLICY,
        FORMAL_SHADOW_UNION_POLICY,
        SHADOW_PREVIEW_POLICY,
    )
    from shadow_inputs import _read_inputs, _summarize_input, _diagnose_shadow_casters, _diagnose_site_boundary
    from shadow_settings import _normalize_settings
    from shadow_measurement_plane import _build_law56_2_awareness_context, _construct_measurement_plane
    from shadow_geometry import _diagnose_shadow_caster_geometry
    from shadow_footprint import _build_footprint_extraction_summary
    from shadow_readiness import _build_pipeline_readiness
    from shadow_debug import _write_debug_log_if_enabled, _build_debug_log_status, _sanitize_text_for_debug
    from shadow_units import _build_unit_conversion_diagnostics
    from shadow_sun import _build_sun_position_diagnostics
    from shadow_projection import _build_shadow_projection_diagnostics
    from shadow_formal_projection import _build_formal_shadow_polygons
    from shadow_preview import _build_shadow_preview
    from shadow_union import _build_unified_shadow_slices
except BaseException:
    _IMPORT_ERROR_TEXT = traceback.format_exc()
else:
    _IMPORT_ERROR_TEXT = None
_checkpoint("SHADOW_IMPORTS_AFTER", "failure" if _IMPORT_ERROR_TEXT else "ok")
if "_shadow_utils" in globals():
    try:
        setattr(_shadow_utils, "RUNTIME_CHECKPOINT", _RUNTIME_CHECKPOINT)
    except BaseException:
        pass


def _build_runtime_code_diagnostics():
    bootstrap = _LOADER_BOOTSTRAP if isinstance(_LOADER_BOOTSTRAP, dict) else {}
    local_names = bootstrap.get("local_module_names")
    if not isinstance(local_names, list):
        local_names = sorted(
            name for name in sys.modules
            if name.startswith("shadow_") and name != "shadow_policies"
        )
        if "shadow_policies" in sys.modules:
            local_names.append("shadow_policies")
            local_names.sort()
    modules = []
    for module_name in local_names:
        module = sys.modules.get(module_name)
        module_file = getattr(module, "__file__", None) if module is not None else None
        module_filename = os.path.basename(module_file) if module_file else None
        try:
            module_dir = _normalized_path(os.path.dirname(os.path.abspath(module_file)))
        except Exception:
            module_dir = None
        modules.append({
            "module_name": module_name,
            "module_filename": module_filename,
            "loaded_from_workspace": bool(module_file and module_dir == _SCRIPT_DIRECTORY),
            "module_file_available": bool(module_file),
        })
    path_zero = bool(sys.path and _normalized_path(sys.path[0]) == _SCRIPT_DIRECTORY)
    return {
        "code_build_id": globals().get("CODE_BUILD_ID", "2026-07-28-module-isolation-v1"),
        "loader_build_id": bootstrap.get("loader_build_id"),
        "loader_bootstrap_received": isinstance(_LOADER_BOOTSTRAP, dict),
        "workspace_resolved": bool(bootstrap.get("workspace_resolved", _SCRIPT_DIRECTORY)),
        "workspace_inserted_at_sys_path_zero": bool(bootstrap.get("workspace_inserted_at_sys_path_zero", path_zero)),
        "import_caches_invalidated": bool(bootstrap.get("import_caches_invalidated", False)),
        "cached_module_count_removed": int(bootstrap.get("cached_module_count_removed", 0)),
        "removed_cached_modules": list(bootstrap.get("removed_cached_modules", [])),
        "script_directory_resolved": bool(_SCRIPT_DIRECTORY),
        "script_directory_at_sys_path_zero": path_zero,
        "all_local_modules_from_workspace": bool(modules) and all(item["loaded_from_workspace"] for item in modules),
        "modules": modules,
    }


_checkpoint("RUNTIME_DIAGNOSTICS_BEFORE")
_RUNTIME_CODE_DIAGNOSTICS = _build_runtime_code_diagnostics()
_checkpoint("RUNTIME_DIAGNOSTICS_AFTER", "dict")


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
        "error_code": "module_import_failure",
        "runtime_code_diagnostics": _RUNTIME_CODE_DIAGNOSTICS,
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
        "shadow_preview": {"enabled": False, "mode": "off", "attempted": False, "available": False, "created_element_count": 0, "deleted_element_count": 0, "warnings": ["Preview unavailable because module imports failed."]},
        "shadow_preview_policy": globals().get("SHADOW_PREVIEW_POLICY"),
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
    site_boundary = _diagnose_optional_site_boundary(raw_inputs.get("site_boundary"))
    settings_normalized = _normalize_settings(raw_inputs.get("settings"), raw_inputs.get("level"))
    law56_2_awareness = _build_law56_2_awareness_context(settings_normalized, site_boundary)
    measurement_plane = _construct_measurement_plane(settings_normalized, raw_inputs.get("level"))
    shadow_caster_geometry, runtime_geometry = _diagnose_shadow_caster_geometry(raw_inputs.get("building_elements"), shadow_casters, settings_normalized, measurement_plane, return_runtime_geometry=True)
    footprint_extraction = _build_footprint_extraction_summary(shadow_caster_geometry, measurement_plane, settings_normalized, site_boundary)
    sun_time_slices, sun_position_diagnostics, sun_position_policy, solar_calculation_v1 = _build_sun_position_diagnostics(settings_normalized)
    shadow_projection_diagnostics, shadow_projection_policy = _build_shadow_projection_diagnostics(shadow_caster_geometry, measurement_plane, sun_time_slices)
    try:
        formal_shadow_polygons = _build_formal_shadow_polygons(runtime_geometry, measurement_plane, sun_time_slices, settings_normalized, shadow_projection_diagnostics)
    except BaseException as exc:
        formal_shadow_polygons = {"available": False, "complete": False, "partial_success": False, "engine": "revit_extrusion_analyzer_v1", "formal_geometry": True, "diagnostic_convex_hull_used_as_fallback": False, "blockers": [{"failure_code": "formal_shadow_engine_unhandled_exception", "failure_type": type(exc).__name__, "failure_message": _sanitize_text_for_debug(exc)}], "warnings": [], "slices": []}
    try:
        unified_shadow_slices = _build_unified_shadow_slices(formal_shadow_polygons, measurement_plane, settings_normalized)
    except BaseException as exc:
        unified_shadow_slices = {"engine": "revit_boolean_solid_union_v1", "available": False, "complete": False, "partial_success": False, "ready_for_duration_accumulation": False, "slices": [], "blockers": [{"failure_code": "formal_shadow_union_unhandled_exception", "failure_type": type(exc).__name__}], "warnings": []}
    try:
        shadow_preview = _build_shadow_preview(unified_shadow_slices, measurement_plane, settings_normalized)
    except BaseException:
        shadow_preview = {"enabled": False, "mode": "off", "attempted": True, "available": False, "complete": False, "partial_success": False, "unified_shadow_source_available": bool(unified_shadow_slices.get("available")), "created_element_count": 0, "deleted_element_count": 0, "created_element_ids": [], "groups": [], "warnings": ["Preview failed non-fatally; unified formal shadow output remains available."]}
    pipeline_readiness = _build_pipeline_readiness(shadow_casters, site_boundary, settings_normalized, shadow_caster_geometry, measurement_plane, footprint_extraction, formal_shadow_polygons, solar_calculation_v1, unified_shadow_slices)
    warnings.extend(shadow_casters.get("warnings", []))
    warnings.extend(site_boundary.get("warnings", []))
    warnings.extend(settings_normalized.get("warnings", []))
    warnings.extend(law56_2_awareness.get("warnings", []))
    warnings.extend(measurement_plane.get("warnings", []))
    warnings.extend(shadow_caster_geometry.get("warnings", []))
    warnings.extend(footprint_extraction.get("warnings", []))
    warnings.extend(sun_position_diagnostics.get("warnings", []))
    warnings.extend(shadow_projection_diagnostics.get("warnings", []))
    warnings.extend(formal_shadow_polygons.get("warnings", []))
    warnings.extend(shadow_preview.get("warnings", []))
    warnings.extend(pipeline_readiness.get("blockers_for_equal_time_shadow", []))
    warnings.extend(pipeline_readiness.get("blockers_for_footprint_extraction", []))
    warnings.extend(pipeline_readiness.get("blockers_for_measurement_plane", []))
    warnings.extend(pipeline_readiness.get("blockers_for_future_projection_context", []))
    warnings.extend(pipeline_readiness.get("blockers_for_future_shadow_projection", []))
    warnings.extend(pipeline_readiness.get("blockers_for_legal_judgement_masks", []))
    warnings.extend(unit_conversion_diagnostics.get("warnings", []))
    if not pipeline_readiness.get("boundary_dependent_steps_ready"):
        warnings.extend(pipeline_readiness.get("blockers_for_boundary_dependent_steps", []))

    site_boundary_degraded = site_boundary.get("diagnostic_failed") is True
    out_payload = {
        "success": True,
        "partial_success": site_boundary_degraded,
        "degraded_components": ["site_boundary"] if site_boundary_degraded else [],
        "shadow_calculation_completed": True,
        "boundary_dependent_steps_completed": bool(pipeline_readiness.get("boundary_dependent_steps_ready")),
        "runtime_code_diagnostics": _RUNTIME_CODE_DIAGNOSTICS,
        "tool": TOOL_NAME,
        "stage": STAGE_NAME,
        "message": "Dynamo_Shadow Revit-native formal time-slice shadow and per-slice union prototype with optional DirectShape visual QA. No duration accumulation, equal-time contours, or legal judgement is performed.",
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
        "solar_specification": (solar_calculation_v1 or {}).get("solar_specification"),
        "sun_position_policy": sun_position_policy,
        "shadow_projection_diagnostics": shadow_projection_diagnostics,
        "shadow_projection_policy": shadow_projection_policy,
        "formal_shadow_polygons": formal_shadow_polygons,
        "formal_shadow_projection_policy": FORMAL_SHADOW_PROJECTION_POLICY,
        "unified_shadow_slices": unified_shadow_slices,
        "formal_shadow_union_policy": FORMAL_SHADOW_UNION_POLICY,
        "shadow_preview": shadow_preview,
        "shadow_preview_policy": SHADOW_PREVIEW_POLICY,
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
    _checkpoint("DEBUG_JSON_WRITE_BEFORE")
    debug_log_status = _write_debug_log_if_enabled(out_payload, settings_normalized)
    _checkpoint("DEBUG_JSON_WRITE_AFTER", "ok")
    out_payload["debug_log"] = debug_log_status
    if debug_log_status.get("warnings"):
        out_payload["warnings"].extend(debug_log_status.get("warnings"))
    return out_payload


def _diagnose_optional_site_boundary(value):
    """Keep this optional diagnostic outside the core-pipeline failure path."""
    try:
        return _diagnose_site_boundary(value)
    except BaseException as exc:
        items = _shadow_utils._to_list(value)
        error_type = type(exc).__name__
        message = _sanitize_text_for_debug(exc)
        warning = (
            "Optional site_boundary diagnostics failed; boundary-dependent outputs "
            "are unavailable. The continuing result is an unbounded technical shadow "
            "result, not a complete legal judgement result."
        )
        return {
            "provided": bool(items),
            "count": len(items),
            "available": False,
            "accepted_count": 0,
            "rejected_count": len(items),
            "boundary_dependent_steps_available": False,
            "boundary_dependent_steps_skipped": True,
            "equal_time_shadow_available_without_site_boundary": True,
            "diagnostic_failed": True,
            "error_code": "optional_site_boundary_diagnostic_failure",
            "error_type": error_type,
            "sanitized_error_message": message,
            "items": [],
            "loop_diagnostics": {"attempted": False, "appears_closed": None},
            "warnings": [warning],
            "info": ["Core footprint, solar, projection, accumulation, and contour stages remain independent of site_boundary."],
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
    sun_time_slices = []
    sun_position_diagnostics = None
    sun_position_policy = SUN_POSITION_POLICY
    solar_calculation_v1 = None
    shadow_projection_diagnostics = None
    shadow_projection_policy = SHADOW_PROJECTION_POLICY
    formal_shadow_polygons = None
    unified_shadow_slices = None
    shadow_preview = None
    try:
        unit_conversion_diagnostics = _build_unit_conversion_diagnostics()
    except Exception:
        unit_conversion_diagnostics = {"available": False, "diagnostic_only": True, "warnings": ["unit conversion diagnostics could not be built during failure handling"]}
    try:
        shadow_casters = _diagnose_shadow_casters(raw_inputs.get("building_elements"))
    except Exception:
        shadow_casters = None
    try:
        site_boundary = _diagnose_optional_site_boundary(raw_inputs.get("site_boundary"))
    except BaseException:
        site_boundary = {"available": False, "boundary_dependent_steps_available": False}
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
        sun_time_slices, sun_position_diagnostics, sun_position_policy, solar_calculation_v1 = _build_sun_position_diagnostics(settings_normalized or {})
        shadow_projection_diagnostics, shadow_projection_policy = _build_shadow_projection_diagnostics(shadow_caster_geometry, measurement_plane, sun_time_slices)
        formal_shadow_polygons = _build_formal_shadow_polygons({"casters": []}, measurement_plane, sun_time_slices, settings_normalized or {}, shadow_projection_diagnostics)
        unified_shadow_slices = _build_unified_shadow_slices(formal_shadow_polygons, measurement_plane, settings_normalized or {})
        shadow_preview = _build_shadow_preview(unified_shadow_slices, measurement_plane, settings_normalized or {})
        pipeline_readiness = _build_pipeline_readiness(shadow_casters or {}, site_boundary or {}, settings_normalized or {}, shadow_caster_geometry, measurement_plane, footprint_extraction, formal_shadow_polygons, solar_calculation_v1, unified_shadow_slices)
    except Exception:
        pipeline_readiness = None

    out_payload = {
        "success": False,
        "runtime_code_diagnostics": _RUNTIME_CODE_DIAGNOSTICS,
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
        "solar_specification": (solar_calculation_v1 or {}).get("solar_specification"),
        "sun_position_policy": sun_position_policy,
        "shadow_projection_diagnostics": shadow_projection_diagnostics,
        "shadow_projection_policy": shadow_projection_policy,
        "formal_shadow_polygons": formal_shadow_polygons,
        "formal_shadow_projection_policy": FORMAL_SHADOW_PROJECTION_POLICY,
        "shadow_preview": shadow_preview,
        "shadow_preview_policy": SHADOW_PREVIEW_POLICY,
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
elif not _RUNTIME_CODE_DIAGNOSTICS.get("all_local_modules_from_workspace"):
    OUT = _minimal_import_failure("One or more local diagnostic modules were not loaded from the current workspace.")
    OUT["error_code"] = "local_module_source_mismatch"
else:
    try:
        _checkpoint("BUILD_SUCCESS_BEFORE")
        OUT = _build_success()
        _checkpoint("BUILD_SUCCESS_AFTER", "dict")
    except BaseException:
        _checkpoint("SCRIPT_EXCEPTION", "failure")
        OUT = _build_failure(traceback.format_exc())

_checkpoint("SCRIPT_RETURN_READY", "none" if OUT is None else "dict")
