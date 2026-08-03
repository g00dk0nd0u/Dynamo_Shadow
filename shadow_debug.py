# Development debug log helpers for Dynamo_Shadow diagnostics.
#
# Debug logs are intentionally small, sanitized, fixed-name review artifacts.
# They must not contain raw Revit objects, full geometry payloads, personal paths,
# or timestamped run-log filenames.

import json
import os
import re

from shadow_policies import DEBUG_LOG_POLICY, TOOL_NAME, STAGE_NAME
from shadow_utils import _safe_text, _type_name

_DEBUG_SCHEMA_VERSION = "v1"
_DEFAULT_STATUS_WARNINGS = []
_REDACTED_PATH = "<redacted_path>"
_REDACTED_EMAIL = "<redacted_email>"
_REDACTED_PRIVATE_TEXT = "<redacted_private_text>"
_SUSPICIOUS_KEYS = set([
    "name", "family_name", "type_name", "path", "full_path", "filepath", "file_path",
    "source_path", "model_path", "document_path", "central_model_path", "username",
    "user", "email", "client", "project", "project_name", "model_name", "raw",
    "raw_object", "revit_object", "geometry", "solid", "face", "edge", "object", "repr",
])


def _redact_private_text(text):
    """Redact local paths, network paths, emails, and common private markers."""
    redacted = _safe_text(text)
    redacted = re.sub(r"[A-Za-z]:[\\/](?:Users[\\/])?[^\s\"'<>|]+", _REDACTED_PATH, redacted)
    redacted = re.sub(r"/(?:Users|home)/[^\s\"'<>|]+", _REDACTED_PATH, redacted)
    redacted = re.sub(r"\\\\[^\\\s]+\\[^\s\"'<>|]+", _REDACTED_PATH, redacted)
    redacted = re.sub(r"(?<!:)//(?!localhost(?:/|$))[^/\s]+/[^\s\"'<>|]+", _REDACTED_PATH, redacted)
    redacted = re.sub(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", _REDACTED_EMAIL, redacted)
    redacted = re.sub(r"OneDrive(?:\s*-\s*[^/\\\n\r\t]+)?", _REDACTED_PRIVATE_TEXT, redacted, flags=re.IGNORECASE)
    redacted = re.sub(r"\b(?:Desktop|Documents|Downloads)\b", _REDACTED_PRIVATE_TEXT, redacted, flags=re.IGNORECASE)
    redacted = re.sub(r"(?:[^\s\"'<>|]*[\\/]){4,}[^\s\"'<>|]*", _REDACTED_PATH, redacted)
    return redacted


def _sanitize_text_for_debug(text):
    redacted = _redact_private_text(text)
    redacted = redacted.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    redacted = redacted.replace("\\", "/")
    redacted = re.sub(r"\s+", " ", redacted).strip()
    if len(redacted) > 500:
        return redacted[:500] + "...<truncated>"
    return redacted


def _build_debug_log_status(enabled, attempted, path=None, written=False, error=None, warnings=None):
    relative_path = _sanitize_text_for_debug(path) if path else None
    return {
        "enabled": bool(enabled),
        "attempted": bool(attempted),
        "written": bool(written),
        "path": relative_path,
        "relative_path": relative_path,
        "warnings": [_sanitize_text_for_debug(w) for w in list(warnings or _DEFAULT_STATUS_WARNINGS)],
        "error": _sanitize_text_for_debug(error) if error else None,
    }


def _sanitize_for_debug(value, depth=0):
    """Return a small JSON-safe representation suitable for committed logs."""
    if depth > 6:
        return "<max_depth_reached>"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _sanitize_text_for_debug(value)
    if isinstance(value, (list, tuple)):
        limited = [_sanitize_for_debug(v, depth + 1) for v in list(value)[:20]]
        if len(value) > 20:
            limited.append({"truncated_count": len(value) - 20})
        return limited
    if isinstance(value, dict):
        result = {}
        for key in sorted(value.keys(), key=lambda k: _safe_text(k)):
            key_text = _safe_text(key)
            lowered = key_text.lower()
            if lowered in _SUSPICIOUS_KEYS:
                continue
            result[_sanitize_text_for_debug(key_text)] = _sanitize_for_debug(value.get(key), depth + 1)
        return result
    return {"type": _sanitize_text_for_debug(_type_name(value)), "repr_omitted": True}


def _summary_counts(section):
    if not isinstance(section, dict):
        return section
    keys = [
        "count", "accepted_count", "rejected_count", "provided", "available", "constructed",
        "ready", "attempted", "solid_count", "positive_solid_count", "mesh_count", "curve_count", "face_count",
        "edge_count", "geometry_readable_caster_count", "geometry_instance_count",
        "bottom_face_candidate_count", "edge_loop_candidate_count", "footprint_loop_candidate_count",
        "closed_loop_candidate_count", "closed_footprint_loop_candidate_count",
        "boundary_dependent_steps_skipped", "warning_count",
    ]
    result = {}
    for key in keys:
        if key in section:
            result[key] = _sanitize_for_debug(section.get(key))
    if "items" in section:
        wanted = ["wrapper_type", "wrapper_type_module", "candidate_type", "candidate_type_module", "native_type", "native_type_module", "unwrapped", "unwrap_strategy", "unwrap_attempts", "unwrap_failure_reasons", "native_candidate_usable", "native_property_access_ready", "is_valid_object_status", "element_id", "element_id_object_type", "element_id_property_read_method", "element_id_value_read_method", "element_id_access_error_type", "element_id_access_error", "element_id_read_method", "category_available", "category_source", "category_object_type", "category_property_read_method", "category_id", "category_id_read_method", "category_name_read_method", "category_access_error_type", "category_access_error", "category_read_method", "category_id_raw_type", "official_revit_api_category", "document_reacquire_attempted", "document_reacquire_succeeded", "document_reacquire_strategy", "property_access_diagnostics", "candidate_probes", "accepted", "accepted_shadow_caster", "geometry_probe_attempted", "geometry_access_method", "geometry_readable", "geometry_instance_count", "solid_count", "positive_solid_count", "face_count", "edge_count", "bottom_face_candidate_count", "closed_footprint_loop_candidate_count", "warnings"]
        result["items"] = _sanitize_for_debug([{k: item.get(k) for k in wanted if k in item} for item in (section.get("items") or [])[:20]])
    for key in ("readiness", "summary", "totals", "warnings", "blockers_for_equal_time_shadow", "blockers_for_footprint_extraction", "blockers_for_measurement_plane"):
        if key in section:
            result[key] = _sanitize_for_debug(section.get(key))
    if not result:
        result = _sanitize_for_debug(section)
    return result


def _polygon_convexity_summary(points):
    """Summarize XY convexity without retaining footprint coordinates."""
    if not isinstance(points, (list, tuple)) or len(points) < 3:
        return {"is_convex": None, "concave_vertex_count": None}
    xy = []
    try:
        for point in points:
            if not isinstance(point, dict):
                raise TypeError("point is not a mapping")
            xy.append((float(point["x"]), float(point["y"])))
    except (KeyError, TypeError, ValueError, OverflowError):
        return {"is_convex": None, "concave_vertex_count": None}

    tolerance = 1e-12
    signed_area = 0.0
    for index in range(len(xy)):
        current = xy[index]
        following = xy[(index + 1) % len(xy)]
        signed_area += current[0] * following[1] - following[0] * current[1]
    signed_area *= 0.5
    if abs(signed_area) <= tolerance:
        return {"is_convex": None, "concave_vertex_count": None}

    expected_sign = 1 if signed_area > 0.0 else -1
    concave_vertex_count = 0
    non_collinear_turn_count = 0
    for index in range(len(xy)):
        previous = xy[index - 1]
        current = xy[index]
        following = xy[(index + 1) % len(xy)]
        cross = ((current[0] - previous[0]) * (following[1] - current[1])
                 - (current[1] - previous[1]) * (following[0] - current[0]))
        if abs(cross) <= tolerance:
            continue
        non_collinear_turn_count += 1
        if cross * expected_sign < 0.0:
            concave_vertex_count += 1
    if non_collinear_turn_count == 0:
        return {"is_convex": None, "concave_vertex_count": None}
    return {
        "is_convex": concave_vertex_count == 0,
        "concave_vertex_count": concave_vertex_count,
    }


def _debug_int(value, default=None):
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError, OverflowError):
        return default


def _debug_float(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def _solar_calculation_debug_summary(solar_calculation):
    """Return an allowlisted summary without retaining the full slice table."""
    solar = solar_calculation if isinstance(solar_calculation, dict) else {}
    keys = [
        "available", "complete", "calculation_mode", "solar_parameter_mode",
        "solar_parameter_mode_inferred_for_backward_compatibility", "solar_parameter_source",
        "solar_parameter_source_available", "solar_parameters_resolved",
        "calculation_date", "day_of_year", "days_in_year",
        "parameter_reference_hour_local_standard", "equation_of_time_minutes",
        "solar_declination_deg", "input_time_basis", "standard_meridian_deg",
        "site_latitude_deg", "site_longitude_deg", "true_north_deg",
        "longitude_correction_minutes", "equation_of_time_applied",
        "longitude_correction_applied", "slice_count",
        "date_based_declination_calculated", "date_based_equation_of_time_calculated",
        "permit_ready_certified", "blockers", "warnings",
    ]
    defaults = {
        "available": False, "complete": False,
        "solar_parameter_mode_inferred_for_backward_compatibility": False,
        "solar_parameter_source_available": False, "solar_parameters_resolved": False,
        "slice_count": 0, "date_based_declination_calculated": False,
        "date_based_equation_of_time_calculated": False,
        "permit_ready_certified": False, "blockers": [], "warnings": [],
    }
    return _sanitize_for_debug({key: solar.get(key, defaults.get(key)) for key in keys})


def _solar_specification_debug_summary(solar_calculation):
    """Compact, allowlisted formal-solar contract summary."""
    solar = solar_calculation if isinstance(solar_calculation, dict) else {}
    spec = solar.get("solar_specification") if isinstance(solar.get("solar_specification"), dict) else {}
    return _sanitize_for_debug({
        "version": spec.get("specification_version"), "status": spec.get("status"),
        "selected_profile": spec.get("profile"), "selected_mode": spec.get("solar_parameter_mode"),
        "time_basis": spec.get("time_basis"), "slice_count": solar.get("slice_count", 0),
        "window": {"start": spec.get("window_start"), "end": spec.get("window_end")},
        "step_minutes": spec.get("computational_step_minutes"),
        "declination_source": spec.get("declination_source"),
        "conversion_flags": {"longitude": spec.get("longitude_correction_applied"), "equation_of_time": spec.get("equation_of_time_applied")},
        "coordinate_conventions": {"true_north": spec.get("true_north_convention"), "azimuth": spec.get("azimuth_convention")},
        "formal_readiness": solar.get("formal_solar_calculation_ready", False),
        "permit_ready_certified": False, "blockers": solar.get("blockers", []), "warnings": solar.get("warnings", []),
    })


def _formal_footprint_debug_summary(footprint_extraction):
    """Return an allowlisted, coordinate-free formal-footprint summary."""
    extraction = footprint_extraction if isinstance(footprint_extraction, dict) else {}
    formal = extraction.get("formal_footprints") or {}
    if not isinstance(formal, dict):
        formal = {}

    items = []
    for item in (formal.get("items") or [])[:20]:
        if not isinstance(item, dict):
            continue
        points = item.get("points_m")
        summary = {
            "polygon_index": _debug_int(item.get("polygon_index")),
            "source_caster_index": _debug_int(item.get("source_caster_index")),
            "source_candidate_index": _debug_int(item.get("source_candidate_index")),
            "source_face_index": _debug_int(item.get("source_face_index")),
            "source_loop_index": _debug_int(item.get("source_loop_index")),
            "point_count": _debug_int(item.get("point_count"), len(points) if isinstance(points, (list, tuple)) else 0),
            "area_m2": _debug_float(item.get("area_m2")),
            "area_m2_signed": _debug_float(item.get("area_m2_signed")),
            "orientation": _sanitize_for_debug(item.get("orientation")),
            "role": _sanitize_for_debug(item.get("role")),
            "containment_depth": _debug_int(item.get("containment_depth")),
            "classification_group_key": _sanitize_for_debug(item.get("classification_group_key")) if isinstance(item.get("classification_group_key"), (list, tuple)) else None,
            "closed": bool(item.get("closed", False)),
            "units": _sanitize_for_debug(item.get("units")),
            "generation_method": _sanitize_for_debug(item.get("generation_method")),
            "native_source_loop_index": _debug_int(item.get("native_source_loop_index")),
            "native_curve_count": _debug_int(item.get("native_curve_count")),
            "native_orientation_method": _sanitize_for_debug(item.get("native_orientation_method")),
            "native_flip_performed": bool(item.get("native_flip_performed", False)),
        }
        summary.update(_polygon_convexity_summary(points))
        items.append(summary)

    invalid_loops = []
    for item in (formal.get("invalid_loops") or [])[:20]:
        if isinstance(item, dict):
            reasons = item.get("reasons") if isinstance(item.get("reasons"), (list, tuple)) else []
            invalid_summary = {
                "caster_index": _debug_int(item.get("caster_index")),
                "candidate_index": _debug_int(item.get("candidate_index")),
                "source_face_index": _debug_int(item.get("source_face_index")),
                "source_loop_index": _debug_int(item.get("source_loop_index")),
                "reasons": [_sanitize_text_for_debug(reason) for reason in reasons[:20]],
            }
            if "generation_method" in item:
                invalid_summary["generation_method"] = _sanitize_for_debug(item.get("generation_method"))
            if "reason_codes" in item:
                invalid_summary["reason_codes"] = _sanitize_for_debug(item.get("reason_codes") or [])
            invalid_loops.append(invalid_summary)

    candidates = []
    for caster in (footprint_extraction or {}).get("best_candidates") or []:
        if isinstance(caster, dict): candidates.append(caster)
    extraction_items = (footprint_extraction or {}).get("items") or []
    per_face = [item.get("footprint_extraction") or {} for item in extraction_items if isinstance(item, dict)]
    reason_counts = {}
    for item in invalid_loops:
        for code in item.get("reason_codes") or []:
            reason_counts[code] = reason_counts.get(code, 0) + 1

    return {
        "available": bool(formal.get("available", False)),
        "complete": bool(formal.get("complete", False)),
        "partial_success": bool(formal.get("partial_success", False)),
        "ready_for_shadow_projection_input": bool(formal.get("ready_for_shadow_projection_input", False)),
        "tolerance_m_used": _debug_float(formal.get("tolerance_m_used")),
        "caster_count": _debug_int(formal.get("caster_count"), 0),
        "successful_caster_count": _debug_int(formal.get("successful_caster_count"), 0),
        "failed_caster_count": _debug_int(formal.get("failed_caster_count"), 0),
        "polygon_count": _debug_int(formal.get("polygon_count"), 0),
        "outer_loop_count": _debug_int(formal.get("outer_loop_count"), 0),
        "inner_loop_count": _debug_int(formal.get("inner_loop_count"), 0),
        "unknown_role_count": _debug_int(formal.get("unknown_role_count"), 0),
        "invalid_loop_count": _debug_int(formal.get("invalid_loop_count"), 0),
        "boolean_union_performed": bool(formal.get("boolean_union_performed", False)),
        "native_primary_path_expected": True,
        "native_face_attempt_count": _debug_int((footprint_extraction or {}).get("native_face_attempt_count"), sum(_debug_int(fp.get("native_face_attempt_count"), 0) for fp in per_face)),
        "native_face_success_count": _debug_int((footprint_extraction or {}).get("native_face_success_count"), sum(_debug_int(fp.get("native_face_success_count"), 0) for fp in per_face)),
        "native_loop_count": _debug_int((footprint_extraction or {}).get("native_loop_count"), sum(_debug_int(fp.get("native_loop_count"), 0) for fp in per_face)),
        "native_line_loop_count": sum(1 for item in items if item.get("generation_method") == "native_curve_loop_line_exact"),
        "native_non_line_loop_count": _debug_int((footprint_extraction or {}).get("non_line_native_loop_count"), sum(_debug_int(fp.get("non_line_native_loop_count"), 0) for fp in per_face)),
        "fallback_face_count": _debug_int((footprint_extraction or {}).get("fallback_face_count"), sum(_debug_int(fp.get("fallback_face_count"), 0) for fp in per_face)),
        "fallback_loop_count": _debug_int((footprint_extraction or {}).get("fallback_loop_count"), sum(_debug_int(fp.get("fallback_loop_count"), 0) for fp in per_face)),
        "mixed_generation_methods": bool((footprint_extraction or {}).get("mixed_generation_methods")) or any(bool(fp.get("mixed_generation_methods")) for fp in per_face),
        "native_dispose_warning_count": sum(1 for warning in ((footprint_extraction or {}).get("warnings") or []) if warning == "native_curve_loop_dispose_failed"),
        "formal_native_polygon_count": sum(1 for item in items if item.get("generation_method") == "native_curve_loop_line_exact"),
        "formal_fallback_polygon_count": sum(1 for item in items if item.get("generation_method") == "python_endpoint_stitch_fallback"),
        "invalid_reason_counts": reason_counts,
        "items": items,
        "invalid_loops": invalid_loops,
        "blockers": _sanitize_for_debug(formal.get("blockers") or []),
        "warnings": _sanitize_for_debug(formal.get("warnings") or []),
    }



def _unit_conversion_summary(out_payload):
    diagnostics = (out_payload or {}).get("unit_conversion_diagnostics") or {}
    keys = [
        "available",
        "diagnostic_only",
        "backend",
        "length",
        "area",
        "volume",
        "raw_fields_preserved",
        "converted_fields_added",
        "converted_fields_suffix",
        "used_for_legal_judgement",
        "used_for_shadow_projection",
        "warnings",
    ]
    return _sanitize_for_debug({key: diagnostics.get(key) for key in keys if key in diagnostics})


def _runtime_code_summary(out_payload):
    diagnostics = (out_payload or {}).get("runtime_code_diagnostics") or {}
    keys = [
        "code_build_id", "loader_build_id", "loader_bootstrap_received",
        "workspace_resolved", "workspace_inserted_at_sys_path_zero",
        "import_caches_invalidated", "cached_module_count_removed",
        "removed_cached_modules", "script_directory_resolved",
        "script_directory_at_sys_path_zero", "all_local_modules_from_workspace",
    ]
    result = {key: diagnostics.get(key) for key in keys if key in diagnostics}
    allowed_module_keys = (
        "module_name", "module_filename", "loaded_from_workspace", "module_file_available"
    )
    result["modules"] = [
        {key: item.get(key) for key in allowed_module_keys if key in item}
        for item in (diagnostics.get("modules") or [])[:20]
        if isinstance(item, dict)
    ]
    return _sanitize_for_debug(result)


def _formal_shadow_polygon_debug_summary(formal_shadow):
    """Compact, coordinate-free summary; runtime native objects are never visited."""
    formal = formal_shadow if isinstance(formal_shadow, dict) else {}
    reason_counts = {}; areas = []; point_counts = []
    vector_contract_passed = runtime_verified = runtime_failed = runtime_unverified = 0
    analyzer_ok = analyzer_fail = analyzer_dispose_fail = native_loops = line_loops = non_line_loops = 0
    outer = inner = failed_slices = failed_caster_slices = comparisons = 0
    per_slice = []
    for item in (formal.get("slices") or [])[:17]:
        if (item.get("direction_vector_contract_check") or {}).get("antiparallel_api_conversion") is True:
            vector_contract_passed += 1
        runtime_check = item.get("actual_polygon_direction_check") or {}
        if item.get("revit_runtime_direction_verified") is True: runtime_verified += 1
        elif runtime_check.get("section_axis_min_m") is not None or runtime_check.get("reason") == "one or more runtime polygons failed": runtime_failed += 1
        else: runtime_unverified += 1
        polygons = 0; failed_casters = 0
        for caster in item.get("casters") or []:
            cps = caster.get("polygons") or []; polygons += len(cps)
            if not cps: failed_casters += 1; failed_caster_slices += 1
            for polygon in cps:
                areas.append(_debug_float(polygon.get("area_m2"))); point_counts.append(_debug_int(polygon.get("point_count"), 0))
                if polygon.get("role") == "inner": inner += 1
                else: outer += 1
                native_loops += 1; line_loops += 0 if polygon.get("contains_non_line_curve") else 1
                if polygon.get("contains_non_line_curve"): non_line_loops += 1
            for blocker in caster.get("blockers") or []:
                code = blocker.get("failure_code") if isinstance(blocker, dict) else str(blocker); reason_counts[code] = reason_counts.get(code, 0) + 1
            for analyzer in caster.get("analyzers") or []:
                if analyzer.get("create_succeeded"): analyzer_ok += 1
                else: analyzer_fail += 1
                if analyzer.get("dispose_attempted") and not analyzer.get("dispose_succeeded"): analyzer_dispose_fail += 1
        if not item.get("complete"): failed_slices += 1
        if item.get("comparison"): comparisons += 1
        per_slice.append({"slice_index": _debug_int(item.get("slice_index")), "complete": bool(item.get("complete")), "polygon_count": polygons, "failed_caster_count": failed_casters})
    areas = [x for x in areas if x is not None]; point_counts = [x for x in point_counts if x is not None]
    return _sanitize_for_debug({
        "available": bool(formal.get("available")), "complete": bool(formal.get("complete")), "partial_success": bool(formal.get("partial_success")),
        "engine": formal.get("engine"), "prototype_scope": formal.get("prototype_scope"), "time_slice_count": formal.get("time_slice_count", 0),
        "caster_count": formal.get("caster_count", 0), "split_solid_count": formal.get("split_solid_count", 0), "polygon_count": formal.get("polygon_count", 0),
        "outer_loop_count": outer, "inner_loop_count": inner, "failed_slice_count": failed_slices, "failed_caster_slice_count": failed_caster_slices,
        "analyzer_create_success_count": analyzer_ok, "analyzer_create_failure_count": analyzer_fail, "analyzer_dispose_failure_count": analyzer_dispose_fail,
        "native_loop_count": native_loops, "native_line_loop_count": line_loops, "native_non_line_loop_count": non_line_loops,
        "vector_contract_passed_count": vector_contract_passed,
        "runtime_polygon_direction_verified_count": runtime_verified,
        "runtime_polygon_direction_failed_count": runtime_failed,
        "runtime_polygon_direction_unverified_count": runtime_unverified,
        "failure_reason_counts": reason_counts, "per_slice": per_slice,
        "minimum_area_m2": min(areas) if areas else None, "maximum_area_m2": max(areas) if areas else None,
        "minimum_point_count": min(point_counts) if point_counts else None, "maximum_point_count": max(point_counts) if point_counts else None,
        "diagnostic_convex_hull_comparison_count": comparisons,
    })

def _unified_shadow_summary(union):
    union = union if isinstance(union, dict) else {}
    slices = union.get("slices") or []
    return _sanitize_for_debug({
        "engine": union.get("engine"), "available": bool(union.get("available")),
        "complete": bool(union.get("complete")), "time_slice_count": union.get("time_slice_count", 0),
        "successful_slice_count": union.get("successful_slice_count", 0), "failed_slice_count": union.get("failed_slice_count", 0),
        "input_polygon_count": union.get("input_polygon_count", 0), "output_polygon_count": union.get("output_polygon_count", 0),
        "input_component_count": union.get("input_component_count", 0), "output_component_count": union.get("output_component_count", 0),
        "boolean_operation_attempt_count": union.get("boolean_operation_attempt_count", 0),
        "boolean_operation_success_count": union.get("boolean_operation_success_count", 0),
        "boolean_operation_failure_count": union.get("boolean_operation_failure_count", 0),
        "total_input_area_m2": sum(float(s.get("input_area_m2_sum") or 0) for s in slices),
        "total_unified_area_m2": sum(float(s.get("unified_area_m2") or 0) for s in slices),
        "total_overlap_removed_area_m2": sum(float(s.get("overlap_removed_area_m2") or 0) for s in slices),
        "ready_for_duration_accumulation": bool(union.get("ready_for_duration_accumulation")),
        "blockers": union.get("blockers") or [], "warnings": union.get("warnings") or [],
    })

def _summarize_out_for_debug(out_payload):
    out_payload = out_payload or {}
    settings = out_payload.get("settings_normalized") or {}
    return {
        "success": bool(out_payload.get("success")),
        "message": _sanitize_for_debug(out_payload.get("message")),
        "input_summary": _sanitize_for_debug(out_payload.get("inputs")),
        "settings_summary": _sanitize_for_debug({
            "provided": settings.get("provided"),
            "schema_version": settings.get("schema_version"),
            "normalized": settings.get("normalized"),
            "readiness": settings.get("readiness"),
            "defaults_applied": settings.get("defaults_applied"),
            "missing_required_keys": settings.get("missing_required_keys"),
            "invalid_keys": settings.get("invalid_keys"),
            "warnings": settings.get("warnings"),
        }),
        "shadow_caster_summary": _summary_counts(out_payload.get("shadow_casters")),
        "site_boundary_summary": _summary_counts(out_payload.get("site_boundary")),
        "site_boundary_skipped": bool((out_payload.get("site_boundary") or {}).get("boundary_dependent_steps_skipped", False)),
        "measurement_plane_summary": _summary_counts(out_payload.get("measurement_plane")),
        "shadow_caster_geometry_summary": _summary_counts(out_payload.get("shadow_caster_geometry")),
        "footprint_extraction_summary": _summary_counts(out_payload.get("footprint_extraction")),
        "formal_footprint_summary": _formal_footprint_debug_summary(out_payload.get("footprint_extraction")),
        "formal_shadow_polygon_summary": _formal_shadow_polygon_debug_summary(out_payload.get("formal_shadow_polygons")),
        "unified_shadow_summary": _unified_shadow_summary(out_payload.get("unified_shadow_slices")),
        "shadow_preview": _sanitize_for_debug(out_payload.get("shadow_preview")),
        "solar_calculation_summary": _solar_calculation_debug_summary(out_payload.get("solar_calculation_v1")),
        "solar_specification_summary": _solar_specification_debug_summary(out_payload.get("solar_calculation_v1")),
        "pipeline_readiness": _sanitize_for_debug(out_payload.get("pipeline_readiness")),
        "unit_conversion_summary": _unit_conversion_summary(out_payload),
        "runtime_code_diagnostics": _runtime_code_summary(out_payload),
        "warnings": _sanitize_for_debug(out_payload.get("warnings") or []),
        "warnings_count": len(out_payload.get("warnings") or []),
        "error_summary": _sanitize_for_debug(out_payload.get("error")),
        "not_implemented_summary": _sanitize_for_debug({
            "footprint_extraction": (out_payload.get("footprint_extraction_policy") or {}).get("not_implemented_in_this_pr"),
            "planned_pipeline_pending": [item for item in (out_payload.get("planned_pipeline") or [])[16:]
                                         if item not in ("formal footprint polygon generation",
                                             "formal model-coordinate shadow direction calculation",
                                             "formal time-slice shadow projection per caster",
                                             "logical union of shadows per time slice")],
        }),
    }


def _build_debug_log_payload(out_payload, raw_inputs=None):
    summary = _summarize_out_for_debug(out_payload or {})
    payload = {
        "debug_schema_version": _DEBUG_SCHEMA_VERSION,
        "tool": _sanitize_for_debug((out_payload or {}).get("tool", TOOL_NAME)),
        "stage": _sanitize_for_debug((out_payload or {}).get("stage", STAGE_NAME)),
        "success": summary["success"],
        "message": summary["message"],
        "input_summary": summary["input_summary"],
        "settings_summary": summary["settings_summary"],
        "shadow_caster_summary": summary["shadow_caster_summary"],
        "site_boundary_summary": summary["site_boundary_summary"],
        "site_boundary_skipped": summary["site_boundary_skipped"],
        "measurement_plane_summary": summary["measurement_plane_summary"],
        "shadow_caster_geometry_summary": summary["shadow_caster_geometry_summary"],
        "footprint_extraction_summary": summary["footprint_extraction_summary"],
        "formal_footprint_summary": summary["formal_footprint_summary"],
        "formal_shadow_polygon_summary": summary["formal_shadow_polygon_summary"],
        "unified_shadow_summary": summary["unified_shadow_summary"],
        "shadow_preview": summary["shadow_preview"],
        "solar_calculation_summary": summary["solar_calculation_summary"],
        "solar_specification_summary": summary["solar_specification_summary"],
        "pipeline_readiness": summary["pipeline_readiness"],
        "unit_conversion_summary": summary["unit_conversion_summary"],
        "runtime_code_diagnostics": summary["runtime_code_diagnostics"],
        "warnings": summary["warnings"],
        "warnings_count": summary["warnings_count"],
        "error_summary": summary["error_summary"],
        "not_implemented_summary": summary["not_implemented_summary"],
        "generated_for_review": True,
        "sanitized": True,
    }
    if raw_inputs is not None:
        payload["raw_input_summary"] = _sanitize_for_debug(raw_inputs)
    return payload


def _get_debug_base_dir():
    try:
        module_file = globals().get("__file__")
        if module_file:
            return os.path.dirname(os.path.abspath(module_file)), None
    except Exception as exc:
        return os.getcwd(), "debug log base directory fallback used; module path unavailable: {0}".format(_sanitize_text_for_debug(exc))
    return os.getcwd(), "debug log base directory fallback used; module path unavailable."


def _safe_debug_log_dir(settings_normalized=None):
    normalized = ((settings_normalized or {}).get("normalized") or {})
    return normalized.get("debug_log_dir") or DEBUG_LOG_POLICY["default_directory"]


def _safe_debug_log_path(settings_normalized=None):
    normalized = ((settings_normalized or {}).get("normalized") or {})
    directory = normalized.get("debug_log_dir") or DEBUG_LOG_POLICY["default_directory"]
    filename = normalized.get("debug_log_filename") or DEBUG_LOG_POLICY["default_filename"]
    relative_path = os.path.join(directory, filename).replace("\\", "/")
    base_dir, warning = _get_debug_base_dir()
    absolute_path = os.path.abspath(os.path.join(base_dir, relative_path))
    return {
        "absolute_path": absolute_path,
        "relative_path": relative_path,
        "warning": warning,
    }


def _write_debug_log_if_enabled(out_payload, settings_normalized=None):
    normalized = ((settings_normalized or {}).get("normalized") or {})
    enabled = bool(normalized.get("debug_log_enabled", False))
    if not enabled:
        return _build_debug_log_status(False, False)

    path_info = _safe_debug_log_path(settings_normalized)
    warnings = []
    if path_info.get("warning"):
        warnings.append(path_info.get("warning"))
    try:
        directory = os.path.dirname(path_info["absolute_path"])
        if directory and not os.path.isdir(directory):
            os.makedirs(directory)
        payload = _build_debug_log_payload(out_payload)
        with open(path_info["absolute_path"], "w") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        return _build_debug_log_status(True, True, path=path_info["relative_path"], written=True, warnings=warnings)
    except Exception as exc:
        warning = "debug log write failed; diagnostics continue: {0}".format(_sanitize_text_for_debug(exc))
        warnings.append(warning)
        return _build_debug_log_status(True, True, path=path_info["relative_path"], written=False, error=warning, warnings=warnings)
