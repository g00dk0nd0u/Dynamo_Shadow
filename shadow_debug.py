# Development debug log helpers for Dynamo_Shadow diagnostics.
#
# Debug logs are intentionally small, sanitized, fixed-name review artifacts.
# They must not contain raw Revit objects, full geometry payloads, personal paths,
# or timestamped run-log filenames.

import json
import os

from shadow_policies import DEBUG_LOG_POLICY, TOOL_NAME, STAGE_NAME
from shadow_utils import _safe_text, _type_name

_DEBUG_SCHEMA_VERSION = "v1"
_DEFAULT_STATUS_WARNINGS = []


def _build_debug_log_status(enabled, attempted, path=None, written=False, error=None, warnings=None):
    relative_path = path if path else None
    return {
        "enabled": bool(enabled),
        "attempted": bool(attempted),
        "written": bool(written),
        "path": relative_path,
        "relative_path": relative_path,
        "warnings": list(warnings or _DEFAULT_STATUS_WARNINGS),
        "error": _safe_text(error) if error else None,
    }


def _sanitize_for_debug(value, depth=0):
    """Return a small JSON-safe representation suitable for committed logs."""
    if depth > 6:
        return "<max_depth_reached>"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        text = value.replace("\\", "/")
        if len(text) > 500:
            return text[:500] + "...<truncated>"
        return text
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
            if lowered in ("name", "family_name", "type_name"):
                continue
            if lowered in ("path", "full_path", "filepath", "file_path"):
                continue
            if lowered in ("raw", "raw_object", "revit_object", "geometry", "solid", "face", "edge"):
                continue
            result[key_text] = _sanitize_for_debug(value.get(key), depth + 1)
        return result
    return {"type": _type_name(value), "repr_omitted": True}


def _summary_counts(section):
    if not isinstance(section, dict):
        return section
    keys = [
        "count", "accepted_count", "rejected_count", "provided", "available", "constructed",
        "ready", "attempted", "solid_count", "mesh_count", "curve_count", "face_count",
        "edge_count", "bottom_face_candidate_count", "edge_loop_candidate_count",
        "closed_loop_candidate_count", "warning_count",
    ]
    result = {}
    for key in keys:
        if key in section:
            result[key] = _sanitize_for_debug(section.get(key))
    for key in ("readiness", "summary", "totals", "warnings", "blockers_for_equal_time_shadow", "blockers_for_footprint_extraction", "blockers_for_measurement_plane"):
        if key in section:
            result[key] = _sanitize_for_debug(section.get(key))
    if not result:
        result = _sanitize_for_debug(section)
    return result


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
        "measurement_plane_summary": _summary_counts(out_payload.get("measurement_plane")),
        "shadow_caster_geometry_summary": _summary_counts(out_payload.get("shadow_caster_geometry")),
        "footprint_extraction_summary": _summary_counts(out_payload.get("footprint_extraction")),
        "pipeline_readiness": _sanitize_for_debug(out_payload.get("pipeline_readiness")),
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
        "tool": (out_payload or {}).get("tool", TOOL_NAME),
        "stage": (out_payload or {}).get("stage", STAGE_NAME),
        "success": summary["success"],
        "message": summary["message"],
        "input_summary": summary["input_summary"],
        "settings_summary": summary["settings_summary"],
        "shadow_caster_summary": summary["shadow_caster_summary"],
        "site_boundary_summary": summary["site_boundary_summary"],
        "measurement_plane_summary": summary["measurement_plane_summary"],
        "shadow_caster_geometry_summary": summary["shadow_caster_geometry_summary"],
        "footprint_extraction_summary": summary["footprint_extraction_summary"],
        "pipeline_readiness": summary["pipeline_readiness"],
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


def _safe_debug_log_dir(settings_normalized=None):
    normalized = ((settings_normalized or {}).get("normalized") or {})
    return normalized.get("debug_log_dir") or DEBUG_LOG_POLICY["default_directory"]


def _safe_debug_log_path(settings_normalized=None):
    normalized = ((settings_normalized or {}).get("normalized") or {})
    directory = normalized.get("debug_log_dir") or DEBUG_LOG_POLICY["default_directory"]
    filename = normalized.get("debug_log_filename") or DEBUG_LOG_POLICY["default_filename"]
    return os.path.join(directory, filename).replace("\\", "/")


def _write_debug_log_if_enabled(out_payload, settings_normalized=None):
    normalized = ((settings_normalized or {}).get("normalized") or {})
    enabled = bool(normalized.get("debug_log_enabled", False))
    if not enabled:
        return _build_debug_log_status(False, False)

    path = _safe_debug_log_path(settings_normalized)
    warnings = []
    try:
        directory = _safe_debug_log_dir(settings_normalized)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory)
        payload = _build_debug_log_payload(out_payload)
        with open(path, "w") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        return _build_debug_log_status(True, True, path=path, written=True, warnings=warnings)
    except Exception as exc:
        warning = "debug log write failed; diagnostics continue: {0}".format(_safe_text(exc))
        warnings.append(warning)
        return _build_debug_log_status(True, True, path=path, written=False, error=warning, warnings=warnings)
