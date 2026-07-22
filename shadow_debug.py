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
        wanted = ["wrapper_type", "native_type", "unwrap_strategy", "element_id", "category_id", "official_revit_api_category", "accepted", "accepted_shadow_caster", "geometry_access_method", "geometry_readable", "geometry_instance_count", "solid_count", "positive_solid_count", "face_count", "edge_count", "bottom_face_candidate_count", "closed_footprint_loop_candidate_count", "warnings"]
        result["items"] = _sanitize_for_debug([{k: item.get(k) for k in wanted if k in item} for item in (section.get("items") or [])[:20]])
    for key in ("readiness", "summary", "totals", "warnings", "blockers_for_equal_time_shadow", "blockers_for_footprint_extraction", "blockers_for_measurement_plane"):
        if key in section:
            result[key] = _sanitize_for_debug(section.get(key))
    if not result:
        result = _sanitize_for_debug(section)
    return result



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
        "pipeline_readiness": _sanitize_for_debug(out_payload.get("pipeline_readiness")),
        "unit_conversion_summary": _unit_conversion_summary(out_payload),
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
        "pipeline_readiness": summary["pipeline_readiness"],
        "unit_conversion_summary": summary["unit_conversion_summary"],
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
