import pytest

from shadow_duration import integrate_shadow_states_trapezoidal
from shadow_reverse_exact_oracle import build_micro_grid_exact_oracle


def _model(cell_count=1):
    return {"height_step_m": 1, "sample_minutes": [0, 10, 20],
        "height_cells": [{"area_m2": 1} for _ in range(cell_count)],
        "measurement_points": [{"zone": "near", "limit_minutes": 10}],
        "shadow_contributions": [[[2, 2, 2]] for _ in range(cell_count)]}


def _reevaluate(model, result):
    heights = result["best_heights_m"]
    states = [any(height > 0 and height + 1e-9 >= model["shadow_contributions"][i][0][k]
                  for i, height in enumerate(heights)) for k in range(3)]
    return integrate_shadow_states_trapezoidal(states, model["sample_minutes"])


def test_hand_calculable_tiny_optimum_and_forward_reevaluation():
    model = _model()
    # Height >=2 shadows all 20 minutes, so the only feasible height is 0 or 1.
    result = build_micro_grid_exact_oracle(model, maximum_height_m=3)
    assert result["exact_within_discrete_model"] is True
    assert result["objective_volume_m3"] == 1
    assert _reevaluate(model, result) <= model["measurement_points"][0]["limit_minutes"]


def test_multiple_optima_have_deterministic_tie_break():
    model = _model(2)
    model["measurement_points"][0]["limit_minutes"] = 5
    model["shadow_contributions"] = [[[2, 99, 99]], [[99, 99, 2]]]
    # One endpoint shadow costs five trapezoidal minutes. [2,1] and [1,2]
    # are equal optima; the documented fixed lexicographic tie-break selects [2,1].
    result = build_micro_grid_exact_oracle(model, maximum_height_m=2)
    assert result["objective_volume_m3"] == 3
    assert result["best_heights_m"] == [2, 1]
    assert result == build_micro_grid_exact_oracle(model, maximum_height_m=2)


def test_maximum_height_cap_is_binding_and_monotone():
    model = _model()
    model["shadow_contributions"] = [[[99, 99, 99]]]
    low = build_micro_grid_exact_oracle(model, maximum_height_m=2.5)
    high = build_micro_grid_exact_oracle(model, maximum_height_m=4.5)
    assert low["objective_volume_m3"] == 2.5
    assert low["objective_volume_m3"] <= high["objective_volume_m3"]
    assert _reevaluate(model, low) == 0


def test_state_space_guard_never_falls_back():
    result = build_micro_grid_exact_oracle(_model(3), maximum_height_m=10,
                                           maximum_state_space=100)
    assert result["exact_within_discrete_model"] is False
    assert result["objective_volume_m3"] is None
    assert result["search_nodes"] == 0
    assert result["blockers"][0]["failure_code"] == "micro_grid_state_space_limit_exceeded"
    assert result["blockers"][0]["automatic_heuristic_fallback_used"] is False


@pytest.mark.parametrize("value", [0, -1, float("inf"), "bad"])
def test_invalid_maximum_height_is_not_silently_defaulted(value):
    result = build_micro_grid_exact_oracle(_model(), maximum_height_m=value)
    assert result["exact_within_discrete_model"] is False
    assert result["blockers"][0]["failure_code"] == "invalid_micro_grid_oracle_input"


@pytest.mark.parametrize("mutation", [
    lambda model: model["height_cells"][0].update(area_m2=0),
    lambda model: model["measurement_points"][0].update(limit_minutes=-1),
    lambda model: model.update(sample_minutes=[0, 20, 10]),
    lambda model: model["shadow_contributions"][0][0].__setitem__(0, float("nan")),
])
def test_invalid_discrete_model_values_are_blocked(mutation):
    model = _model()
    mutation(model)
    result = build_micro_grid_exact_oracle(model)
    assert result["exact_within_discrete_model"] is False
    assert result["objective_volume_m3"] is None
    assert result["blockers"][0]["failure_code"] == "invalid_micro_grid_oracle_input"
