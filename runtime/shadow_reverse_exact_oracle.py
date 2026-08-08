"""Exact exhaustive oracle for deliberately tiny discrete Reverse models."""
import itertools
import math

from shadow_duration import integrate_shadow_states_trapezoidal

METHOD = "micro_grid_discrete_exhaustive_oracle_v1"
DEFAULT_MAXIMUM_HEIGHT_M = 31.0
DEFAULT_MAXIMUM_STATE_SPACE = 1000000


def _empty(maximum_height_m, height_step_m, cells, upper):
    return {"method": METHOD, "exact_within_discrete_model": False,
        "maximum_height_m": maximum_height_m, "height_step_m": height_step_m,
        "height_cell_count": len(cells), "state_space_upper_bound": upper,
        "search_nodes": 0, "pruned_nodes": 0, "objective_volume_m3": None,
        "forward_constraints_satisfied": False, "near_worst_minutes": None,
        "far_worst_minutes": None, "best_heights_m": None, "blockers": [],
        "warnings": ["Exact only within the supplied finite micro-grid model; not a continuous or legal optimum."],
        "legal_judgement_generated": False, "ordinance_selection_certified": False,
        "permit_ready_certified": False, "final_forward_equal_time_validation_required": True}


def build_micro_grid_exact_oracle(model, maximum_height_m=DEFAULT_MAXIMUM_HEIGHT_M,
                                  maximum_state_space=DEFAULT_MAXIMUM_STATE_SPACE):
    cells = list((model or {}).get("height_cells") or [])
    step = (model or {}).get("height_step_m")
    try:
        cap, step, maximum = float(maximum_height_m), float(step), int(maximum_state_space)
        samples = [float(v) for v in model["sample_minutes"]]
        if not math.isfinite(cap) or cap <= 0 or not math.isfinite(step) or step <= 0 or maximum <= 0 or not cells:
            raise ValueError()
        levels = [index * step for index in range(int(math.floor((cap + 1e-9) / step)) + 1)]
        if cap - levels[-1] > 1e-9:
            levels.append(cap)
        if not levels: raise ValueError()
        contribution = model["shadow_contributions"]
        points = model["measurement_points"]
        if len(contribution) != len(cells) or any(len(row) != len(points) for row in contribution): raise ValueError()
        if any(len(times) != len(samples) for row in contribution for times in row): raise ValueError()
    except (KeyError, TypeError, ValueError, OverflowError):
        result = _empty(maximum_height_m, step, cells, None)
        result["blockers"].append({"failure_code": "invalid_micro_grid_oracle_input"})
        return result
    upper = len(levels) ** len(cells)
    result = _empty(cap, step, cells, upper)
    if upper > maximum:
        result["blockers"].append({"failure_code": "micro_grid_state_space_limit_exceeded",
            "maximum_state_space": maximum, "automatic_heuristic_fallback_used": False})
        return result
    areas = [float(cell.get("area_m2", 1.0)) for cell in cells]
    # contribution[cell][point][time] is the minimum selected cell height causing shadow.
    best = None
    for heights in itertools.product(reversed(levels), repeat=len(cells)):
        result["search_nodes"] += 1
        durations = []
        feasible = True
        for point_index, point in enumerate(points):
            states = [any(heights[cell_index] + 1e-9 >= float(contribution[cell_index][point_index][time_index])
                          and heights[cell_index] > 0 for cell_index in range(len(cells)))
                      for time_index in range(len(samples))]
            duration = integrate_shadow_states_trapezoidal(states, samples)
            durations.append(duration)
            if duration > float(point["limit_minutes"]) + 1e-9:
                feasible = False; break
        if not feasible:
            result["pruned_nodes"] += 1
            continue
        volume = sum(areas[i] * heights[i] for i in range(len(cells)))
        key = (volume, tuple(heights))
        if best is None or key > best[0]: best = (key, heights, durations)
    if best is None:
        result["blockers"].append({"failure_code": "micro_grid_no_feasible_assignment"}); return result
    durations = best[2]
    near = [durations[i] for i,p in enumerate(points) if p.get("zone") == "near"]
    far = [durations[i] for i,p in enumerate(points) if p.get("zone") == "far"]
    result.update({"exact_within_discrete_model": True, "objective_volume_m3": best[0][0],
        "best_heights_m": list(best[1]), "forward_constraints_satisfied": True,
        "near_worst_minutes": max(near) if near else None,
        "far_worst_minutes": max(far) if far else None})
    return result
