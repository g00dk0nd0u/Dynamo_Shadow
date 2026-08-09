import json
from pathlib import Path

from shadow_forward_reverse_validation import build_forward_reverse_validation
from shadow_reverse_exact_oracle import build_micro_grid_exact_oracle
from shadow_reverse_forward_expansion import _expand_round


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
    heuristic_volume = 1.0
    assert oracle["exact_within_discrete_model"] is True
    assert heuristic_volume <= oracle["objective_volume_m3"]
    gap = 100.0*(oracle["objective_volume_m3"]-heuristic_volume)/oracle["objective_volume_m3"]
    assert gap >= 0.0


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
