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
        }
        summary.update(_polygon_convexity_summary(points))
        items.append(summary)

    invalid_loops = []
    for item in (formal.get("invalid_loops") or [])[:20]:
        if isinstance(item, dict):
            reasons = item.get("reasons") if isinstance(item.get("reasons"), (list, tuple)) else []
            invalid_loops.append({
                "caster_index": _debug_int(item.get("caster_index")),
                "candidate_index": _debug_int(item.get("candidate_index")),
                "source_face_index": _debug_int(item.get("source_face_index")),
                "source_loop_index": _debug_int(item.get("source_loop_index")),
                "reasons": [_sanitize_text_for_debug(reason) for reason in reasons[:20]],
            })

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
        "pipeline_readiness": _sanitize_for_debug(out_payload.get("pipeline_readiness")),
        "unit_conversion_summary": _unit_conversion_summary(out_payload),
        "runtime_code_diagnostics": _runtime_code_summary(out_payload),
        "warnings": _sanitize_for_debug(out_payload.get("warnings") or []),
        "warnings_count": len(out_payload.get("warnings") or []),
        "error_summary": _sanitize_for_debug(out_payload.get("error")),
        "not_implemented_summary": _sanitize_for_debug({
            "footprint_extraction": (out_payload.get("footprint_extraction_policy") or {}).get("not_implemented_in_this_pr"),
            "planned_pipeline_pending": (out_payload.get("planned_pipeline") or [])[16:],
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
