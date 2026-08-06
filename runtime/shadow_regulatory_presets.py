"""Regulatory shadow preset resolution and Dynamo Player settings overlay."""

from shadow_settings import _coerce_settings_to_dict


PRESETS = {
    "standard_all": {"profile": "standard_8_16", "start": "08:00", "end": "16:00", "levels": [120, 150, 180, 240, 300], "near": None, "far": None, "preset_purpose": "contour_candidate_set", "comparison_ready": False},
    "standard_3_2": {"preset_purpose": "selected_limit_pair", "comparison_ready": True, "profile": "standard_8_16", "start": "08:00", "end": "16:00", "levels": [120, 180], "near": 180, "far": 120},
    "standard_4_2_5": {"preset_purpose": "selected_limit_pair", "comparison_ready": True, "profile": "standard_8_16", "start": "08:00", "end": "16:00", "levels": [150, 240], "near": 240, "far": 150},
    "standard_5_3": {"preset_purpose": "selected_limit_pair", "comparison_ready": True, "profile": "standard_8_16", "start": "08:00", "end": "16:00", "levels": [180, 300], "near": 300, "far": 180},
    "hokkaido_all": {"profile": "hokkaido_9_15", "start": "09:00", "end": "15:00", "levels": [90, 120, 150, 180, 240], "near": None, "far": None, "preset_purpose": "contour_candidate_set", "comparison_ready": False},
    "hokkaido_2_1_5": {"preset_purpose": "selected_limit_pair", "comparison_ready": True, "profile": "hokkaido_9_15", "start": "09:00", "end": "15:00", "levels": [90, 120], "near": 120, "far": 90},
    "hokkaido_3_2": {"preset_purpose": "selected_limit_pair", "comparison_ready": True, "profile": "hokkaido_9_15", "start": "09:00", "end": "15:00", "levels": [120, 180], "near": 180, "far": 120},
    "hokkaido_4_2_5": {"preset_purpose": "selected_limit_pair", "comparison_ready": True, "profile": "hokkaido_9_15", "start": "09:00", "end": "15:00", "levels": [150, 240], "near": 240, "far": 150},
}


def resolve_regulatory_shadow_preset(value):
    """Resolve a Player value without certifying the applicable ordinance."""
    preset_id = str(value).strip() if value is not None else ""
    item = PRESETS.get(preset_id)
    if item is None:
        return {
            "preset_id": preset_id or None,
            "valid": False,
            "blockers": [{"failure_code": "invalid_regulatory_shadow_preset", "preset_id": preset_id or None}],
            "legal_judgement_generated": False,
            "ordinance_selection_certified": False,
            "permit_ready_certified": False,
            "preset_purpose": None,
            "comparison_ready": False,
            "selection_source": "dynamo_player_user_selection",
            "ordinance_applicability_confirmed": False,
            "source_metadata": {
                "national_framework_reference": "Building Standards Act Article 56-2",
                "local_ordinance_reference_required": True,
                "local_ordinance_id": None,
                "local_ordinance_revision": None,
            },
        }
    return {
        "preset_id": preset_id,
        "profile": item["profile"],
        "true_solar_start_time": item["start"],
        "true_solar_end_time": item["end"],
        "equal_time_contour_levels_minutes": sorted(float(level) for level in item["levels"]),
        "near_limit_minutes": None if item["near"] is None else float(item["near"]),
        "far_limit_minutes": None if item["far"] is None else float(item["far"]),
        "valid": True,
        "blockers": [],
        "legal_judgement_generated": False,
        "ordinance_selection_certified": False,
        "permit_ready_certified": False,
        "preset_purpose": item.get("preset_purpose", "selected_limit_pair"),
        "comparison_ready": bool(item.get("comparison_ready", item.get("near") is not None and item.get("far") is not None)),
        "selection_source": "dynamo_player_user_selection",
        "ordinance_applicability_confirmed": False,
        "source_metadata": {
            "national_framework_reference": "Building Standards Act Article 56-2",
            "local_ordinance_reference_required": True,
            "local_ordinance_id": None,
            "local_ordinance_revision": None,
        },
    }


def overlay_player_settings(settings, regulatory_shadow_preset=None,
                            site_latitude_deg=None, site_longitude_deg=None):
    """Return a fresh settings dict with supplied Player values taking priority."""
    base, input_format, warnings, errors = _coerce_settings_to_dict(settings)
    overlaid = dict(base)
    resolved = None
    if regulatory_shadow_preset is not None:
        resolved = resolve_regulatory_shadow_preset(regulatory_shadow_preset)
        if resolved.get("valid"):
            for key in ("profile", "true_solar_start_time", "true_solar_end_time",
                        "equal_time_contour_levels_minutes"):
                overlaid[key] = resolved[key]
    if site_latitude_deg is not None:
        overlaid.pop("latitude", None)
        overlaid["site_latitude_deg"] = site_latitude_deg
    if site_longitude_deg is not None:
        overlaid.pop("longitude", None)
        overlaid["site_longitude_deg"] = site_longitude_deg
    return overlaid, resolved, input_format, warnings, errors
