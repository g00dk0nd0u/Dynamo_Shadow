import json
import inspect
from pathlib import Path

import pytest

import shadow_reverse_forward_expansion as expansion_module
from shadow_forward_reverse_validation import build_forward_reverse_validation
from shadow_reverse_exact_oracle import build_micro_grid_exact_oracle
from shadow_reverse_forward_expansion import (_cells_from_v2, _expand_round,
    build_forward_validated_reverse_expansion, build_greedy_discrete_model)


def test_centered_mismatch_recovers_and_finishes_forward_safe():
    fixture = json.loads((Path(__file__).parents[1]/"fixtures/forward_reverse_validation/centered_mismatch.json").read_text())
    result = build_forward_reverse_validation(fixture)
    expanded = result["reverse_expansion"]
    assert result["reverse_v2"]["envelope_fit"]["maximum_height_excess_m"] == 0.5
    assert expanded["complete"] is True
    assert expanded["envelope_fit"]["maximum_height_excess_m"] == 0.0
    assert expanded["envelope_fit"]["fully_inside"] is True
    validation = expanded["full_forward_validation"]
    assert validation["overall_status"] == "within_selected_limits"
    assert validation["near_max_minutes"] <= validation["near_limit_minutes"]
    assert validation["far_max_minutes"] <= validation["far_limit_minutes"]


def test_micro_oracle_bounds_heuristic_volume_contract():
    model = {"height_step_m": .5, "sample_minutes": [0, 15, 30],
        "height_cells": [{"area_m2": 1.0}, {"area_m2": 1.0}],
        "measurement_points": [{"zone": "near", "limit_minutes": 15}],
        "shadow_contributions": [[[[99, 1, 99][k] for k in range(3)]],
                                 [[[99, 99, 1][k] for k in range(3)]]]}
    oracle = build_micro_grid_exact_oracle(model, maximum_height_m=1.0)
    heuristic = build_greedy_discrete_model(model, maximum_height_m=1.0)
    oracle_volume_m3 = oracle["objective_volume_m3"]
    heuristic_volume_m3 = heuristic["heuristic_volume_m3"]
    assert oracle["exact_within_discrete_model"] is True
    assert heuristic["global_optimum_proven"] is False
    assert heuristic_volume_m3 <= oracle_volume_m3
    optimality_gap_percent = 100.0*(oracle_volume_m3-heuristic_volume_m3)/oracle_volume_m3
    assert optimality_gap_percent >= 0.0


def test_micro_greedy_uses_production_multiple_accept_sweep_schedule():
    # Re-ranking after every move reaches [0, 0, 2]; the production sweep ranks
    # once, then accepts all three still-feasible first increments.
    model = {"height_step_m": 1, "sample_minutes": [0, 10, 20],
        "height_cells": [{"area_m2": 1} for _ in range(3)],
        "measurement_points": [{"zone": "near", "limit_minutes": 10}],
        "shadow_contributions": [[[2, 1, 2]], [[2, 1, 99]], [[2, 99, 99]]]}
    heuristic = build_greedy_discrete_model(model, maximum_height_m=2)
    assert heuristic["heights_m"] == [1.0, 1.0, 1.0]


def test_notched_boundary_crossing_cell_is_not_authoritative():
    grid = []
    for index, (x, y) in enumerate(((0., 0.), (1., 0.), (0., 1.), (1., 1.))):
        grid.append({"grid_index": index, "x_m": x, "y_m": y, "bounded": True,
                     "inside_site": True, "height_limit_m": 10.})
    reverse = {"height_field": {"grid_spec": {"x_count": 2, "y_count": 2, "resolution_m": 1.},
                                 "grid_points": grid}}
    notch = [(-1., -1.), (2., -1.), (2., 2.), (.6, 2.), (.6, .5),
             (.4, .5), (.4, 2.), (-1., 2.)]
    site = {"outer_loop": [{"x_m": x, "y_m": y} for x, y in notch]}
    cells, _ = _cells_from_v2(reverse, 31., site)
    assert cells == []


def test_increment_is_quantized_capped_deterministic_and_sparse_cached():
    cells = [{"cell_index": 0, "min_x_m": 0., "max_x_m": 1., "min_y_m": 0., "max_y_m": 1.,
              "area_m2": 1., "baseline_height_m": 4., "height_m": 4., "maximum_height_m": 5.,
              "height_increment_count": 0, "bounded": True}]
    active = [{"zone": "near", "x_m": 2., "y_m": .5}]
    solar = [{"shadow_direction_model": {"x": 1., "y": 0.}, "shadow_length_factor": 1.}]*3
    first, metrics = _expand_round(cells, active, [0, 15, 30], solar, 4., {"near": 30.}, 100)
    second, _ = _expand_round(cells, active, [0, 15, 30], solar, 4., {"near": 30.}, 100)
    assert first == second
    assert first[0]["height_m"] == 5.0
    assert first[0]["height_increment_count"] == 2
    assert 0 < metrics["cache"] < 3*len(solar)


def test_active_limit_rejection_and_explicit_complexity_guard():
    cells = [{"cell_index": 0, "min_x_m": 0., "max_x_m": 1., "min_y_m": 0., "max_y_m": 1.,
              "area_m2": 1., "baseline_height_m": 4., "height_m": 4., "maximum_height_m": 5.,
              "height_increment_count": 0, "bounded": True}]
    active = [{"zone": "near", "x_m": 1.25, "y_m": .5}]
    solar = [{"shadow_direction_model": {"x": 1., "y": 0.}, "shadow_length_factor": 1.}]*3
    rejected, metrics = _expand_round(cells, active, [0, 15, 30], solar, 4., {"near": 0.}, 100)
    assert rejected[0]["height_m"] == 4.0
    assert metrics["rejected"] > 0
    guarded, guard_metrics = _expand_round(cells, active, [0, 15, 30], solar, 4., {"near": 30.}, 0)
    assert guarded is None
    assert guard_metrics["guard"] is True


def test_effect_batch_is_not_evaluated_when_it_exceeds_remaining_budget(monkeypatch):
    cells = [{"cell_index": 0, "min_x_m": 0., "max_x_m": 1., "min_y_m": 0., "max_y_m": 1.,
              "area_m2": 1., "height_m": 4., "maximum_height_m": 5.,
              "height_increment_count": 0}]
    active = [{"zone": "near", "x_m": 2., "y_m": .5}]
    solar = [{}, {}, {}]
    calls = []
    monkeypatch.setattr(expansion_module, "is_cell_shadowed", lambda *args: calls.append(args) or False)
    guarded, metrics = _expand_round(cells, active, [0, 15, 30], solar, 4., {"near": 30.}, 2)
    assert guarded is None
    assert metrics["guard"] is True
    assert metrics["evaluations"] == 0
    # Initial-state evaluation is outside the candidate-effect budget; no
    # additional calls for the candidate batch are made.
    assert len(calls) == len(solar)


def _orchestration_fakes(monkeypatch, validations, v2_volume=1.0, expanded_height=2.0):
    reverse = {"complete": True, "blockers": [], "top_surface_mesh": {"bounded_candidate_volume_m3": v2_volume},
        "measurement_points": {"near": {"points": [{"x_m": 1., "y_m": 1.}]},
                               "far": {"points": [{"x_m": 2., "y_m": 2.}]}}}
    baseline_cell = {"cell_index": 0, "ix": 0, "iy": 0, "min_x_m": 0., "max_x_m": 1.,
        "min_y_m": 0., "max_y_m": 1., "center_x_m": .5, "center_y_m": .5, "area_m2": 1.,
        "baseline_height_m": 1., "height_m": 1., "maximum_height_m": 31.,
        "height_increment_count": 0, "bounded": True}
    monkeypatch.setattr(expansion_module, "build_low_rise_reverse_shadow_core_v2", lambda *args: reverse)
    monkeypatch.setattr(expansion_module, "_cells_from_v2", lambda reverse, cap, site: ([dict(baseline_cell, maximum_height_m=cap)], 1.))
    monkeypatch.setattr(expansion_module, "build_forward_solar_samples", lambda *args: {
        "sample_minutes": [0., 15.], "solar_samples": [{}, {}]})
    sequence = iter(validations)
    monkeypatch.setattr(expansion_module, "build_cell_field_forward_validation", lambda *args, **kwargs: next(sequence))
    starts = []
    def expand(cells, *args):
        starts.append(cells[0]["height_m"])
        candidate = [dict(cells[0], height_m=expanded_height)]
        return candidate, {"guard": False, "accepted": 1, "rejected": 0, "evaluations": 2, "cache": 1}
    monkeypatch.setattr(expansion_module, "_expand_round", expand)
    site = {"outer_loop": [{"x_m": 0., "y_m": 0.}, {"x_m": 1., "y_m": 0.},
                           {"x_m": 1., "y_m": 1.}, {"x_m": 0., "y_m": 1.}]}
    preset = {"near_limit_minutes": 180., "far_limit_minutes": 120.}
    settings = {"normalized": {"site_latitude_deg": 35., "true_north_deg": 0.}}
    return starts, (site, preset, {"measurement_height_m": 4.}, settings, "standard")


def _safe_validation(point_x=3.):
    return {"complete": True, "overall_status": "within_selected_limits", "blockers": [],
        "worst_near_point": {"x_m": point_x, "y_m": 3.}, "worst_far_point": {"x_m": 4., "y_m": 4.},
        "grid_point_count": 10, "near_max_minutes": 0., "far_max_minutes": 0.}


def _violating_validation(point):
    return {"complete": True, "overall_status": "exceeds_selected_limits", "blockers": [],
        "comparison": {"near": {"status": "exceeds_selected_limit", "point": point},
                       "far": {"status": "within_selected_limit"}}, "grid_point_count": 10}


def test_constraint_generation_adds_point_and_restarts_from_baseline(monkeypatch):
    added = {"x_m": 9., "y_m": 9.}
    starts, args = _orchestration_fakes(monkeypatch,
        [_safe_validation(), _violating_validation(added), _safe_validation()])
    result = build_forward_validated_reverse_expansion(*args, maximum_height_m=10.)
    assert result["complete"] is True
    assert starts == [1., 1.]
    assert result["constraint_generation"]["iteration_count"] == 2
    assert result["constraint_generation"]["added_points"] == [{"zone": "near", "x_m": 9., "y_m": 9.}]


def test_remaining_global_effect_budget_is_passed_to_next_round(monkeypatch):
    added = {"x_m": 9., "y_m": 9.}
    _, args = _orchestration_fakes(monkeypatch,
        [_safe_validation(), _violating_validation(added), _safe_validation()])
    round_budgets = []
    def expand(cells, active, samples, solar, measurement_height, limits, maximum_checks):
        round_budgets.append(maximum_checks)
        used = 6 if len(round_budgets) == 1 else 4
        return [dict(cells[0], height_m=2.)], {"guard": False, "accepted": 1,
            "rejected": 0, "evaluations": used, "cache": 1}
    monkeypatch.setattr(expansion_module, "_expand_round", expand)
    result = build_forward_validated_reverse_expansion(*args, maximum_effect_evaluations=10)
    assert result["complete"] is True
    assert round_budgets == [10, 4]
    assert result["expansion"]["candidate_effect_evaluation_count"] <= 10


def test_exhausted_global_effect_budget_blocks_before_next_round(monkeypatch):
    added = {"x_m": 9., "y_m": 9.}
    _, args = _orchestration_fakes(monkeypatch, [_safe_validation(), _violating_validation(added)])
    round_budgets = []
    def expand(cells, active, samples, solar, measurement_height, limits, maximum_checks):
        round_budgets.append(maximum_checks)
        return [dict(cells[0], height_m=2.)], {"guard": False, "accepted": 1,
            "rejected": 0, "evaluations": maximum_checks, "cache": 1}
    monkeypatch.setattr(expansion_module, "_expand_round", expand)
    result = build_forward_validated_reverse_expansion(*args, maximum_effect_evaluations=10)
    assert result["complete"] is False
    assert round_budgets == [10]
    assert result["expansion"]["candidate_effect_evaluation_count"] == 10
    assert result["blockers"][-1]["failure_code"] == "reverse_expansion_complexity_limit_exceeded"
    assert result["blockers"][-1]["limit_type"] == "candidate_effect_evaluations"


def test_constraint_generation_stalled_is_explicit(monkeypatch):
    already_active = {"x_m": 1., "y_m": 1.}
    _, args = _orchestration_fakes(monkeypatch, [_safe_validation(), _violating_validation(already_active)])
    result = build_forward_validated_reverse_expansion(*args)
    assert result["complete"] is False
    assert result["constraint_generation"]["stalled"] is True
    assert result["blockers"][-1]["failure_code"] == "reverse_expansion_constraint_generation_stalled"


def test_v2_parity_does_not_disguise_cell_candidate(monkeypatch):
    _, args = _orchestration_fakes(monkeypatch, [_safe_validation(), _safe_validation()],
                                   v2_volume=2., expanded_height=1.)
    result = build_forward_validated_reverse_expansion(*args)
    assert result["complete"] is True
    assert result["selected_source"] == "v2_parity"
    assert result["cell_field"]["candidate_source"] == "forward_validated_expanded_cell_candidate"
    assert result["cell_field"]["selected_for_output"] is False


def test_incomplete_full_validation_propagates_original_blocker(monkeypatch):
    incomplete = {"complete": False, "blockers": [{"failure_code": "reverse_expansion_complexity_limit_exceeded",
        "limit_type": "full_validation_shadow_checks"}]}
    _, args = _orchestration_fakes(monkeypatch, [_safe_validation(), incomplete])
    result = build_forward_validated_reverse_expansion(*args)
    assert result["complete"] is False
    assert result["constraint_generation"]["stalled"] is False
    assert result["blockers"] == incomplete["blockers"]


def test_incomplete_baseline_validation_propagates_original_blocker(monkeypatch):
    incomplete = {"complete": False, "blockers": [{"failure_code": "invalid_cell_field_forward_validation_input"}]}
    _, args = _orchestration_fakes(monkeypatch, [incomplete])
    result = build_forward_validated_reverse_expansion(*args)
    assert result["complete"] is False
    assert result["blockers"] == incomplete["blockers"]


@pytest.mark.parametrize("cap", [10., 45., 60.])
def test_public_maximum_height_accepts_arbitrary_positive_finite_values(monkeypatch, cap):
    _, args = _orchestration_fakes(monkeypatch, [_safe_validation(), _safe_validation()], expanded_height=1.)
    result = build_forward_validated_reverse_expansion(*args, maximum_height_m=cap)
    assert result["maximum_height_m"] == cap
    assert result["cell_field"]["cells"][0]["maximum_height_m"] == cap


@pytest.mark.parametrize("cap", [0, -1, float("nan"), float("inf"), "bad"])
def test_public_maximum_height_rejects_invalid_values(cap):
    result = build_forward_validated_reverse_expansion(None, None, None, None, None, maximum_height_m=cap)
    assert result["complete"] is False
    assert result["blockers"][0]["failure_code"] == "invalid_reverse_expansion_maximum_height_m"


def test_public_maximum_height_default_is_31m():
    assert inspect.signature(build_forward_validated_reverse_expansion).parameters["maximum_height_m"].default == 31.0


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), "bad", None])
@pytest.mark.parametrize("argument,failure_code", [
    ("maximum_effect_evaluations", "invalid_reverse_expansion_maximum_effect_evaluations"),
    ("maximum_constraint_generation_iterations",
     "invalid_reverse_expansion_maximum_constraint_generation_iterations"),
])
def test_public_complexity_arguments_return_explicit_blocker(argument, failure_code, value):
    kwargs = {argument: value}
    result = build_forward_validated_reverse_expansion(None, None, None, None, None, **kwargs)
    assert result["complete"] is False
    assert result["blockers"][0]["failure_code"] == failure_code
