# Law 56-2 awareness and measurement-plane diagnostics.
from shadow_policies import LAW56_2_AWARENESS_POLICY, LAW56_2_FUTURE_REQUIRED_INPUTS, MEASUREMENT_PLANE_POLICY
from shadow_units import _meters_to_internal_length, _internal_length_to_meters


def _build_law56_2_awareness_context(settings_normalized, site_boundary=None):
    normalized = (settings_normalized or {}).get("normalized") or {}
    profile = normalized.get("profile")
    if profile in ("hokkaido_9_15", "hokkaido"):
        selected = LAW56_2_AWARENESS_POLICY["hokkaido_time_window"]
        source = "settings.profile"
    else:
        selected = LAW56_2_AWARENESS_POLICY["standard_time_window"]
        source = "standard_8_16_default_diagnostic"
    warnings = []
    if (site_boundary or {}).get("provided") is not True:
        warnings.append("site_boundary is not required for measurement plane construction, but is required for future beyond-5m and own-site legal judgement masks.")
    return {
        "policy": LAW56_2_AWARENESS_POLICY,
        "article": "Building Standard Law Article 56-2 shadow restriction awareness",
        "date_basis": LAW56_2_AWARENESS_POLICY["date_basis"],
        "time_basis": LAW56_2_AWARENESS_POLICY["time_basis"],
        "active_time_window_profile": profile,
        "standard_time_window": LAW56_2_AWARENESS_POLICY["standard_time_window"],
        "hokkaido_time_window": LAW56_2_AWARENESS_POLICY["hokkaido_time_window"],
        "selected_time_window": selected,
        "selected_time_window_source": source,
        "measurement_plane_basis": LAW56_2_AWARENESS_POLICY["measurement_plane_basis"],
        "boundary_distance_rule_awareness": LAW56_2_AWARENESS_POLICY["boundary_distance_rule_awareness"],
        "exclusion_awareness": LAW56_2_AWARENESS_POLICY["exclusion_awareness"],
        "multiple_buildings_policy_awareness": LAW56_2_AWARENESS_POLICY["multiple_buildings_policy_awareness"],
        "relaxation_awareness": LAW56_2_AWARENESS_POLICY["relaxation_awareness"],
        "ordinance_dependent_values": LAW56_2_AWARENESS_POLICY["ordinance_dependent_values"],
        "future_required_inputs": LAW56_2_FUTURE_REQUIRED_INPUTS,
        "implemented_now": ["awareness diagnostics", "time window profile selection for diagnostics", "measurement plane policy context"],
        "not_implemented_in_this_pr": LAW56_2_AWARENESS_POLICY["not_implemented_in_this_pr"],
        "warnings": warnings,
        "info": ["Time windows are true-solar-time awareness only; no true solar time calculation, JST clock-time conversion, sun vector calculation, or legal judgement is performed."],
    }

def _construct_measurement_plane(settings_normalized, level=None):
    normalized = (settings_normalized or {}).get("normalized") or {}
    mp_norm = (settings_normalized or {}).get("measurement_plane") or {}
    agl = normalized.get("average_ground_level_elevation_m")
    mh = normalized.get("measurement_height_m")
    available = mp_norm.get("available") is True and agl is not None and mh is not None
    elevation = agl + mh if available else None
    settings_ready = ((settings_normalized or {}).get("readiness") or {}).get("ready_for_equal_time_shadow_calculation") is True
    blockers_mp = []
    if agl is None:
        blockers_mp.append("average_ground_level_elevation_m missing")
    if mh is None:
        blockers_mp.append("measurement_height_m missing")
    if mp_norm.get("available") is not True:
        blockers_mp.append("measurement plane unavailable")
    blockers_projection = [] if available and settings_ready else list(blockers_mp)
    if not settings_ready:
        blockers_projection.append("settings not ready for equal-time shadow calculation")
    blockers_legal = ["legal judgement masks not implemented", "site_boundary / own site / target area masks required for legal judgement but not constructed in this PR"]
    warnings = []
    if not available:
        warnings.append("Measurement plane could not be constructed; this is non-fatal for input diagnostics.")
    if level is not None:
        warnings.append("Level reference is present but is not used as average ground level or measurement plane.")

    return {
        "policy": MEASUREMENT_PLANE_POLICY,
        "law56_2_awareness": LAW56_2_AWARENESS_POLICY,
        "provided": (settings_normalized or {}).get("provided") is True,
        "available": available,
        "construction_attempted": True,
        "coordinate_system": "legal_si_meters",
        "units": "meter",
        "plane_type": "horizontal_plane",
        "horizontal": True,
        "normal_raw": {"x": 0.0, "y": 0.0, "z": 1.0, "units": "unitless", "note": "same abstract +Z direction; not derived from Revit geometry"},
        "normal_m": {"x": 0.0, "y": 0.0, "z": 1.0, "units": "unitless"},
        "origin_m": {"x": 0.0, "y": 0.0, "z": elevation, "units": "meter", "note": "abstract legal SI coordinate origin for diagnostics only; not a Revit point"} if available else None,
        "basis": "settings.average_ground_level_elevation_m + settings.measurement_height_m",
        "unit": "meter",
        "elevation_m": elevation,
        "elevation_internal_candidate": _meters_to_internal_length(elevation)[0] if elevation is not None else None,
        "internal_conversion_available": True,
        "plane_equation": "z = {0}".format(elevation) if available else None,
        "average_ground_level_elevation_m": agl,
        "measurement_height_m": mh,
        "formula": "measurement_plane_elevation_m = average_ground_level_elevation_m + measurement_height_m",
        "source_keys": {"average_ground_level_elevation_m": "settings.average_ground_level_elevation_m", "measurement_height_m": "settings.measurement_height_m"},
        "level_reference_present": level is not None,
        "level_used_as_average_ground_level": False,
        "level_used_as_measurement_plane": False,
        "legal_meaning": ["Article 56-2 measurement horizontal plane at designated height above average ground level.", "This is not a Revit Level.", "This is not a Revit element.", "This is not a legal judgement result."],
        "readiness": {"measurement_plane_constructed": available, "ready_for_future_footprint_projection_context": available, "ready_for_future_shadow_projection_context": available and settings_ready, "ready_for_legal_judgement_masks": False, "blockers_for_measurement_plane": blockers_mp, "blockers_for_future_shadow_projection_context": blockers_projection, "blockers_for_legal_judgement_masks": blockers_legal},
        "blockers": blockers_mp + blockers_legal,
        "warnings": warnings,
        "info": ["Measurement plane is an internal diagnostic data object only; no Revit element, DirectShape, ModelCurve, or debug plane is created."],
    }

def _measurement_plane_relation(bbox, face_summaries, measurement_plane):
    elev = (measurement_plane or {}).get("elevation_m")
    base = {"used_for_legal_judgement": False, "used_for_shadow_geometry": False, "formal_intersection_test_performed": False}
    if (measurement_plane or {}).get("available") is not True:
        base.update({"available": False, "formal_intersection_available": False, "raw_comparison_available": False, "meter_comparison_available": False, "measurement_plane_elevation_m": None, "geometry_units": "revit_raw_internal_units", "measurement_plane_units": "meter", "unit_conversion_status": "diagnostic_conversion_available", "raw_relation_candidate": "unknown", "meter_relation_candidate": "unknown", "reason": "measurement plane is unavailable; geometry diagnostics continue."})
        return base
    zs = []
    for key in ("min_raw", "max_raw"):
        z = ((bbox or {}).get(key) or {}).get("z")
        if z is not None: zs.append(z)
    for f in face_summaries:
        z = ((f.get("origin_raw") or {}).get("z"))
        if z is not None: zs.append(z)
    zms = []
    for z in zs:
        zm, _ = _internal_length_to_meters(z)
        if zm is not None: zms.append(zm)
    if not zs:
        rel = mrel = "unknown"; raw_available = meter_available = False; reason = "no z values available for diagnostic comparison."
    else:
        raw_available = True; meter_available = bool(zms)
        rel = "caster_above_measurement_plane_raw_candidate" if min(zs) > elev else ("caster_below_measurement_plane_raw_candidate" if max(zs) < elev else "caster_intersects_measurement_plane_raw_range_candidate")
        mrel = "caster_above_measurement_plane_meter_candidate" if zms and min(zms) > elev else ("caster_below_measurement_plane_meter_candidate" if zms and max(zms) < elev else ("caster_intersects_measurement_plane_meter_range_candidate" if zms else "unknown"))
        reason = "meter relation is diagnostic only; no formal intersection, shadow geometry, or legal judgement is performed."
    base.update({"available": True, "formal_intersection_available": False, "raw_comparison_available": raw_available, "meter_comparison_available": meter_available, "measurement_plane_elevation_m": elev, "geometry_units": "revit_raw_internal_units", "measurement_plane_units": "meter", "unit_conversion_status": "diagnostic_conversion_available", "raw_relation_candidate": rel, "meter_relation_candidate": mrel, "reason": reason})
    return base
