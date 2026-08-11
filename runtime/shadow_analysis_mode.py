"""Dynamo Host support for Forward / Reverse analysis-mode dispatch."""

from shadow_accuracy_presets import resolve_calculation_accuracy_preset
from shadow_contour_preview import build_equal_time_contour_preview
from shadow_measurement_plane import _construct_measurement_plane
from shadow_level_adapter import resolve_average_ground_level
from shadow_project_location_adapter import (apply_true_north_to_settings,
    mark_true_north_applied, resolve_runtime_true_north)
from shadow_preview import build_shadow_preview
from shadow_regulatory_presets import overlay_player_settings, resolve_regulatory_shadow_preset
from shadow_reverse_low_rise import build_low_rise_reverse_shadow_core
from shadow_reverse_preview import build_reverse_shadow_preview
from shadow_settings import _normalize_settings
from shadow_site_area_adapter import extract_site_boundary_area
from shadow_site_geometry import build_site_boundary_geometry
from shadow_site_result_preview import build_site_result_preview

FORWARD_SHADOW = "forward_shadow"
REVERSE_SHADOW = "reverse_shadow"
_LABELS = {
    "Forward Shadow / 順日影": FORWARD_SHADOW,
    "Reverse Shadow / 逆日影": REVERSE_SHADOW,
}


def resolve_analysis_mode(value):
    legacy = value is None or (isinstance(value, str) and not value.strip())
    normalized = FORWARD_SHADOW if legacy else _LABELS.get(value, value)
    valid = normalized in (FORWARD_SHADOW, REVERSE_SHADOW)
    return {
        "mode_id": normalized if valid else None,
        "requested_value": value,
        "valid": valid,
        "legacy_default_used": legacy,
        "blockers": [] if valid else [{"failure_code": "invalid_analysis_mode"}],
    }


def clear_reverse_preview():
    return build_reverse_shadow_preview({}, {}, {"reverse_shadow_preview_mode": "clear"})


def clear_forward_previews():
    settings = {"preview_mode": "clear", "equal_time_contour_preview_mode": "clear"}
    results = {
        "formal_shadow_preview": build_shadow_preview({}, {}, settings),
        "equal_time_contour_preview": build_equal_time_contour_preview({}, {}, settings),
        "site_result_preview": build_site_result_preview({}, {}, {}, {}, settings),
    }
    complete = all(item.get("complete") is True for item in results.values())
    return {"complete": complete, "results": results}


def build_reverse_workflow(raw_inputs, input_source, summarize_input):
    warnings = []
    cleanup = clear_forward_previews()
    cleanup_ok = cleanup.get("complete") is True
    if not cleanup_ok:
        warnings.append("analysis_mode_opposite_preview_cleanup_incomplete")

    area = extract_site_boundary_area(raw_inputs.get("site_boundary"))
    site = build_site_boundary_geometry(area)
    overlaid, preset, _, overlay_warnings, _ = overlay_player_settings(
        raw_inputs.get("settings"), raw_inputs.get("regulatory_shadow_preset"),
        raw_inputs.get("site_latitude_deg"), raw_inputs.get("site_longitude_deg"))
    true_north = resolve_runtime_true_north(overlaid)
    overlaid = apply_true_north_to_settings(overlaid, true_north)
    if preset is None:
        preset = resolve_regulatory_shadow_preset("standard_all")
    resolved_agl = resolve_average_ground_level(raw_inputs.get("level"))
    settings = _normalize_settings(overlaid, resolved_agl)
    settings["true_north"] = true_north
    plane = _construct_measurement_plane(settings)
    accuracy = resolve_calculation_accuracy_preset(raw_inputs.get("calculation_accuracy_preset"))
    core = build_low_rise_reverse_shadow_core(site, preset, plane, settings, accuracy)
    reverse_sun_samples = []
    for zone in (core.get("zones") or {}).values():
        reverse_sun_samples.extend((zone.get("sun_ray_fan") or {}).get("samples", []))
    true_north = mark_true_north_applied(true_north, {"slices": reverse_sun_samples})
    settings["true_north"] = true_north

    preview_settings = dict(settings.get("normalized") or {})
    preview_settings["reverse_shadow_preview_mode"] = (
        "replace" if core.get("complete") is True and cleanup_ok else "clear")
    preview = build_reverse_shadow_preview(core, plane, preview_settings)
    preview_ok = preview.get("complete") is True
    core_ok = core.get("complete") is True
    warnings.extend(overlay_warnings)
    warnings.extend(area.get("warnings", []))
    warnings.extend(site.get("warnings", []))
    warnings.extend(settings.get("warnings", []))
    warnings.extend(true_north.get("warnings", []))
    warnings.extend(plane.get("warnings", []))
    warnings.extend(core.get("warnings", []))
    warnings.extend(preview.get("warnings", []))
    return {
        "success": core_ok,
        "partial_success": bool(core_ok and (not preview_ok or not cleanup_ok)),
        "analysis_mode": resolve_analysis_mode(REVERSE_SHADOW),
        "forward_pipeline_executed": False,
        "inputs": {"source": input_source, **{key: summarize_input(value) for key, value in raw_inputs.items()}},
        "input_usage": {"building_elements": "ignored", "level": "used_as_average_ground_level",
                        "site_boundary": "required", "settings": "used"},
        "site_boundary_area_extraction": area,
        "site_boundary_geometry": site,
        "settings_normalized": settings,
        "true_north": true_north,
        "regulatory_shadow_preset": preset,
        "measurement_plane": plane,
        "calculation_accuracy": core.get("reverse_shadow_accuracy"),
        "reverse_shadow": core,
        "reverse_shadow_preview": preview,
        "mode_cleanup": cleanup,
        "final_forward_equal_time_validation_required": True,
        "legal_judgement_generated": False,
        "ordinance_selection_certified": False,
        "permit_ready_certified": False,
        "warnings": warnings,
    }
