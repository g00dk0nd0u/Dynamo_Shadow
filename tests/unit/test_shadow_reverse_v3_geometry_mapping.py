import pytest
from shadow_duration import integrate_shadow_states_trapezoidal
from shadow_reverse_allowance_patterns import (build_pattern_from_continuous_sunlight_interval,
    build_trapezoidal_sample_ownership_cells, map_pattern_to_geometric_constraints,
    GEOMETRY_MAPPING_PRESERVE_V2_EXACT, GEOMETRY_MAPPING_SAMPLE_OWNERSHIP)


def test_ownership_cells_partition_window_and_match_trapezoidal_boolean_weights():
    samples = [480.0, 495.0, 510.0, 525.0]
    cells = build_trapezoidal_sample_ownership_cells(samples)
    assert [(c["start_minutes"], c["end_minutes"]) for c in cells] == [
        (480.0, 487.5), (487.5, 502.5), (502.5, 517.5), (517.5, 525.0)]
    assert all(cells[i]["end_minutes"] == cells[i+1]["start_minutes"] for i in range(3))
    for states in ([False, False, False, False], [True, False, True, False], [True]*4):
        assert sum(c["duration_minutes"] for c, state in zip(cells, states) if state) == pytest.approx(
            integrate_shadow_states_trapezoidal(states, samples))


def test_general_run_uses_midpoints_but_v2_keeps_exact_interval():
    pattern = {"sample_minutes": [480, 495, 510, 525],
               "sunlight_required_states": [False, True, True, False],
               "source_continuous_sunlight_interval": None}
    mapped = map_pattern_to_geometric_constraints(pattern)
    assert mapped["geometric_constraint_intervals"] == [{"start_minutes": 487.5, "end_minutes": 517.5,
        "source_start_sample_index": 1, "source_end_sample_index": 2,
        "semantics": "trapezoidal_sample_ownership_cell_union"}]
    exact = build_pattern_from_continuous_sunlight_interval(480, 960, 600, 840, 15, 240)
    mapped = map_pattern_to_geometric_constraints(exact)
    assert mapped["geometric_constraint_intervals"][0]["start_minutes"] == 600
    assert mapped["geometric_constraint_intervals"][0]["end_minutes"] == 840


def test_same_mask_retains_exact_and_ownership_geometry_variants_without_mutation():
    pattern = build_pattern_from_continuous_sunlight_interval(480, 960, 600, 840, 15, 240)
    original = dict(pattern)
    exact = map_pattern_to_geometric_constraints(pattern, GEOMETRY_MAPPING_PRESERVE_V2_EXACT)
    ownership = map_pattern_to_geometric_constraints(pattern, GEOMETRY_MAPPING_SAMPLE_OWNERSHIP)
    assert pattern == original
    assert exact["sunlight_required_states"] == ownership["sunlight_required_states"]
    assert (exact["geometric_constraint_intervals"][0]["start_minutes"],
            exact["geometric_constraint_intervals"][0]["end_minutes"]) == (600, 840)
    assert (ownership["geometric_constraint_intervals"][0]["start_minutes"],
            ownership["geometric_constraint_intervals"][0]["end_minutes"]) == (592.5, 832.5)
    assert integrate_shadow_states_trapezoidal(
        ownership["shadow_allowed_states"], ownership["sample_minutes"]) <= 240
