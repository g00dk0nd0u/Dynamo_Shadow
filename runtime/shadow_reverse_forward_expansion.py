"""Deterministic Forward-validated expansion of an unchanged Reverse v2 baseline."""
import math

from shadow_cell_field_forward_validator import (build_cell_field_forward_validation,
                                                  is_cell_shadowed)
from shadow_duration import integrate_shadow_states_trapezoidal
from shadow_forward_equivalent_validator import build_forward_solar_samples
from shadow_reverse_low_rise import METHOD_V2, build_low_rise_reverse_shadow_core_v2

METHOD = "forward_validated_finite_cell_reverse_expansion_v1"
DEFAULT_MAXIMUM_HEIGHT_M = 31.0
MAX_CONSTRAINT_GENERATION_ITERATIONS = 16
MAX_EXPANSION_EFFECT_EVALUATIONS = 25000000
VERTICAL_HEIGHT_STEP_M = 0.5


def _base(maximum_height_m):
    return {"method": METHOD, "available": False, "complete": False, "selected_source": None,
        "master_representation": "finite_site_cell_x_discrete_height_x_forward_sample_state",
        "maximum_height_m": maximum_height_m, "cell_resolution_m": None,
        "vertical_height_step_m": VERTICAL_HEIGHT_STEP_M, "temporal_step_minutes": 15,
        "baseline": {"method": METHOD_V2, "cell_volume_m3": None, "v2_bounded_volume_m3": None,
                     "forward_validation": None},
        "cell_field": {"cells": [], "cell_count": 0, "volume_m3": None, "authoritative": True},
        "expansion": {"accepted_height_increment_count": 0, "rejected_height_increment_count": 0,
                      "candidate_effect_evaluation_count": 0, "effect_cache_entry_count": 0},
        "constraint_generation": {"iteration_count": 0, "initial_active_point_count": 0,
            "final_active_point_count": 0, "added_points": [], "stalled": False},
        "full_forward_validation": {"complete": False}, "comparison": {},
        "optimization": {"global_optimum_proven": False, "oracle_optimality_gap_percent": None},
        "final_forward_equal_time_validation_required": True, "legal_judgement_generated": False,
        "ordinance_selection_certified": False, "permit_ready_certified": False,
        "complexity": {"single_process": True, "automatic_coarse_fallback_used": False},
        "blockers": [], "warnings": ["Cell volume is a geometric optimizer objective, not GFA, FAR, or legal buildable floor area."]}


def _cells_from_v2(reverse, cap):
    field = reverse["height_field"]; spec = field["grid_spec"]
    nx, ny, resolution = spec["x_count"], spec["y_count"], float(spec["resolution_m"])
    points = field["grid_points"]; cells = []
    for iy in range(ny-1):
        for ix in range(nx-1):
            ids = (iy*nx+ix, iy*nx+ix+1, (iy+1)*nx+ix+1, (iy+1)*nx+ix)
            corners = [points[index] for index in ids]
            if not all(point.get("bounded") and point.get("inside_site") for point in corners):
                continue
            height = min(float(point["height_limit_m"]) for point in corners)
            height = min(cap, math.floor((height+1e-9)/VERTICAL_HEIGHT_STEP_M)*VERTICAL_HEIGHT_STEP_M)
            min_x = float(corners[0]["x_m"]); min_y = float(corners[0]["y_m"])
            cells.append({"cell_index": len(cells), "ix": ix, "iy": iy,
                "min_x_m": min_x, "max_x_m": min_x+resolution,
                "min_y_m": min_y, "max_y_m": min_y+resolution,
                "center_x_m": min_x+resolution/2.0, "center_y_m": min_y+resolution/2.0,
                "area_m2": resolution*resolution, "baseline_height_m": height, "height_m": height,
                "maximum_height_m": cap, "height_increment_count": 0, "bounded": True})
    return cells, resolution


def _volume(cells):
    return sum(cell["area_m2"]*cell["height_m"] for cell in cells)


def _point_key(point):
    return (point["zone"], round(float(point["x_m"]), 9), round(float(point["y_m"]), 9))


def _active_points(reverse, validation):
    points = []
    for zone in ("near", "far"):
        for item in reverse["measurement_points"][zone]["points"]:
            points.append({"zone": zone, "x_m": float(item["x_m"]), "y_m": float(item["y_m"])})
        worst = validation.get("worst_%s_point" % zone)
        if worst:
            points.append({"zone": zone, "x_m": float(worst["x_m"]), "y_m": float(worst["y_m"])})
    return sorted({_point_key(point): point for point in points}.values(), key=_point_key)


def _expand_round(baseline_cells, active, samples, solar, measurement_height, limits, maximum_checks):
    cells = [dict(cell) for cell in baseline_cells]
    point_pairs = [(point["x_m"], point["y_m"]) for point in active]
    states = [[any(is_cell_shadowed(point_pairs[p], cells[c], cells[c]["height_m"], measurement_height, s)
                       for c in range(len(cells))) for s in solar] for p in range(len(active))]
    cache = {}; accepted = rejected = evaluations = 0
    while True:
        ranked = []
        old_durations = [integrate_shadow_states_trapezoidal(row, samples) for row in states]
        for ci, cell in enumerate(cells):
            height = cell["height_m"]+VERTICAL_HEIGHT_STEP_M
            if height > cell["maximum_height_m"]+1e-9:
                continue
            key = (ci, height, 0)
            effect = cache.get(key)
            if effect is None:
                effect = tuple(p*len(solar)+k for p, point in enumerate(point_pairs) for k, s in enumerate(solar)
                    if is_cell_shadowed(point, cells[ci], height, measurement_height, s))
                cache[key] = effect; evaluations += len(active)*len(solar)
                if evaluations > maximum_checks:
                    return None, {"guard": True, "accepted": accepted, "rejected": rejected,
                                  "evaluations": evaluations, "cache": len(cache)}
            candidate_states = [list(row) for row in states]
            for flat in effect:
                candidate_states[flat//len(solar)][flat%len(solar)] = True
            durations = [integrate_shadow_states_trapezoidal(row, samples) for row in candidate_states]
            feasible = all(durations[p] <= limits[active[p]["zone"]]+1e-9 for p in range(len(active)))
            if not feasible:
                rejected += 1; continue
            consumption = sum(durations[p]-old_durations[p] for p in range(len(active)))
            utilization = max([durations[p]/limits[active[p]["zone"]] for p in range(len(active))] or [0.0])
            score = (0 if consumption <= 1e-9 else 1, consumption, utilization, ci)
            ranked.append((score, ci, height, effect))
        if not ranked:
            break
        accepted_this_sweep = 0
        for _, ci, height, effect in sorted(ranked):
            # Earlier moves in this sweep may consume or overlap the same states.
            candidate_states = [list(row) for row in states]
            for flat in effect:
                candidate_states[flat//len(solar)][flat%len(solar)] = True
            durations = [integrate_shadow_states_trapezoidal(row, samples) for row in candidate_states]
            if not all(durations[p] <= limits[active[p]["zone"]]+1e-9 for p in range(len(active))):
                rejected += 1; continue
            cells[ci]["height_m"] = height; cells[ci]["height_increment_count"] += 1
            states = candidate_states; accepted += 1; accepted_this_sweep += 1
        if not accepted_this_sweep:
            break
    return cells, {"guard": False, "accepted": accepted, "rejected": rejected,
                   "evaluations": evaluations, "cache": len(cache)}


def build_forward_validated_reverse_expansion(site_boundary_geometry, resolved_regulatory_preset,
        measurement_plane, settings_normalized, calculation_accuracy_preset,
        maximum_height_m=DEFAULT_MAXIMUM_HEIGHT_M, maximum_effect_evaluations=MAX_EXPANSION_EFFECT_EVALUATIONS,
        maximum_constraint_generation_iterations=MAX_CONSTRAINT_GENERATION_ITERATIONS):
    result = _base(maximum_height_m)
    try:
        cap = float(maximum_height_m)
        if not math.isfinite(cap) or cap <= 0: raise ValueError()
    except (TypeError, ValueError, OverflowError):
        result["blockers"].append({"failure_code": "invalid_reverse_expansion_maximum_height_m"}); return result
    reverse = build_low_rise_reverse_shadow_core_v2(site_boundary_geometry, resolved_regulatory_preset,
                                                     measurement_plane, settings_normalized,
                                                     calculation_accuracy_preset)
    if not reverse.get("complete"):
        result["blockers"] += reverse.get("blockers") or []; return result
    cells, resolution = _cells_from_v2(reverse, cap); result["cell_resolution_m"] = resolution
    if not cells:
        result["blockers"].append({"failure_code": "reverse_expansion_no_fully_contained_cells"}); return result
    baseline_volume = _volume(cells); v2_volume = reverse["top_surface_mesh"]["bounded_candidate_volume_m3"]
    measurement_height = float(measurement_plane["measurement_height_m"])
    baseline_validation = build_cell_field_forward_validation(cells, site_boundary_geometry,
        resolved_regulatory_preset, settings_normalized, measurement_height)
    result["baseline"].update({"cell_volume_m3": baseline_volume,
        "v2_bounded_volume_m3": v2_volume, "forward_validation": baseline_validation})
    if baseline_validation.get("overall_status") != "within_selected_limits":
        result["blockers"].append({"failure_code": "reverse_expansion_v2_baseline_forward_validation_failed"}); return result
    active = _active_points(reverse, baseline_validation); initial_count = len(active)
    result["constraint_generation"]["initial_active_point_count"] = initial_count
    fixture = {"site_latitude_deg": settings_normalized["normalized"]["site_latitude_deg"],
               "true_north_deg": settings_normalized["normalized"]["true_north_deg"]}
    sample_data = build_forward_solar_samples(fixture, resolved_regulatory_preset, 15)
    limits = {"near": float(resolved_regulatory_preset["near_limit_minutes"]),
              "far": float(resolved_regulatory_preset["far_limit_minutes"])}
    totals = {"accepted": 0, "rejected": 0, "evaluations": 0, "cache": 0}; final_cells = None; validation = None
    for iteration in range(1, int(maximum_constraint_generation_iterations)+1):
        final_cells, metrics = _expand_round(cells, active, sample_data["sample_minutes"],
            sample_data["solar_samples"], measurement_height, limits, int(maximum_effect_evaluations))
        for key in totals: totals[key] += metrics[key]
        result["constraint_generation"]["iteration_count"] = iteration
        if metrics["guard"]:
            result["blockers"].append({"failure_code": "reverse_expansion_complexity_limit_exceeded",
                "limit_type": "candidate_effect_evaluations", "automatic_coarse_fallback_used": False}); return result
        validation = build_cell_field_forward_validation(final_cells, site_boundary_geometry,
            resolved_regulatory_preset, settings_normalized, measurement_height)
        if validation.get("overall_status") == "within_selected_limits": break
        added = []
        for zone in ("near", "far"):
            comparison = validation.get("comparison", {}).get(zone, {})
            point = comparison.get("point")
            if comparison.get("status") == "exceeds_selected_limit" and point:
                candidate = {"zone": zone, "x_m": point["x_m"], "y_m": point["y_m"]}
                if _point_key(candidate) not in {_point_key(p) for p in active}: added.append(candidate)
        if not added:
            result["constraint_generation"]["stalled"] = True
            result["blockers"].append({"failure_code": "reverse_expansion_constraint_generation_stalled"}); return result
        active = sorted(active+added, key=_point_key); result["constraint_generation"]["added_points"] += added
    else:
        result["blockers"].append({"failure_code": "reverse_expansion_constraint_generation_iteration_limit_exceeded"}); return result
    expanded_volume = _volume(final_cells); gain = expanded_volume-v2_volume
    selected = "forward_validated_expanded_cell_candidate" if gain > 1e-9 else "v2_parity"
    result.update({"available": True, "complete": True, "selected_source": selected})
    result["cell_field"].update({"cells": final_cells, "cell_count": len(final_cells), "volume_m3": expanded_volume})
    result["expansion"].update({"accepted_height_increment_count": totals["accepted"],
        "rejected_height_increment_count": totals["rejected"],
        "candidate_effect_evaluation_count": totals["evaluations"], "effect_cache_entry_count": totals["cache"]})
    result["constraint_generation"]["final_active_point_count"] = len(active)
    result["full_forward_validation"] = validation
    result["comparison"] = {"v2_bounded_volume_m3": v2_volume, "expanded_candidate_volume_m3": expanded_volume,
        "volume_gain_m3": gain, "volume_gain_percent": 100.0*gain/v2_volume if v2_volume else None}
    result["complexity"].update({"cell_count": len(final_cells), "active_measurement_point_count": len(active),
        "sample_count": len(sample_data["sample_minutes"]), "full_validation_grid_point_count": validation["grid_point_count"]})
    return result


def prism_fits_cell_field(footprint, height_m, cells, tolerance=1e-9):
    """Conservative QA check that every sampled footprint point has a covering cell."""
    from shadow_reverse_envelope_evaluation import _sample_polygon
    points = _sample_polygon([(float(p[0]), float(p[1])) for p in footprint], 0.5)
    deficits = []
    for x, y in points:
        heights = [cell["height_m"] for cell in cells if cell["min_x_m"]-tolerance <= x <= cell["max_x_m"]+tolerance
                   and cell["min_y_m"]-tolerance <= y <= cell["max_y_m"]+tolerance]
        deficits.append(max(0.0, float(height_m)-(max(heights) if heights else 0.0)))
    return {"fully_inside": max(deficits or [float(height_m)]) <= tolerance,
            "maximum_height_excess_m": max(deficits or [float(height_m)]), "validation_point_count": len(points)}
