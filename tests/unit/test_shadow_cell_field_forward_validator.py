import itertools

import pytest

from shadow_cell_field_forward_validator import (build_cell_field_forward_validation,
    build_cell_field_shadow_states, cell_footprint, is_cell_shadowed)
from shadow_duration import integrate_shadow_states_trapezoidal
from shadow_forward_equivalent_validator import is_prism_shadowed


def _cell(index=0, height=10.0):
    return {"cell_index": index, "min_x_m": 0.0, "max_x_m": 1.0, "min_y_m": 0.0,
            "max_y_m": 1.0, "height_m": height}


def test_whole_building_uses_or_and_trapezoidal_semantics():
    solar = [{"shadow_direction_model": {"x": 1.0, "y": 0.0}, "shadow_length_factor": 1.0}]*3
    states = build_cell_field_shadow_states([(2.0, .5)], [_cell(), _cell(1)], 4.0, solar)
    assert states == [[True, True, True]]
    assert integrate_shadow_states_trapezoidal(states[0], [0, 15, 30]) == 30.0


def test_square_fast_path_matches_expected_segment_intersection():
    solar = {"shadow_direction_model": {"x": 1.0, "y": 0.0}, "shadow_length_factor": 1.0}
    assert is_cell_shadowed((2.0, .5), _cell(), 10.0, 4.0, solar) is True
    assert is_cell_shadowed((2.0, 2.0), _cell(), 10.0, 4.0, solar) is False


@pytest.mark.parametrize("point,direction,factor,height", itertools.product(
    [(-1., .5), (0., 0.), (1., 1.), (2., .5), (.5, 2.), (2., 2.)],
    [(1., 0.), (-1., 0.), (0., 1.), (.6, -.8)], [0., .5, 2.], [3., 4., 10.]))
def test_square_predicate_matches_prismatic_validator(point, direction, factor, height):
    solar = {"shadow_direction_model": {"x": direction[0], "y": direction[1]},
             "shadow_length_factor": factor}
    assert is_cell_shadowed(point, _cell(), height, 4., solar) == is_prism_shadowed(
        point, cell_footprint(_cell()), height, 4., solar)


def _validation_inputs():
    cells = [dict(_cell(), min_x_m=0., max_x_m=1., min_y_m=0., max_y_m=1.)]
    site = {"complete": True, "outer_loop": [{"x_m": -1., "y_m": -1.}, {"x_m": 2., "y_m": -1.},
        {"x_m": 2., "y_m": 2.}, {"x_m": -1., "y_m": 2.}]}
    preset = {"true_solar_start_time": "08:00", "true_solar_end_time": "08:30",
        "valid": True, "comparison_ready": True, "near_limit_minutes": 180., "far_limit_minutes": 120.}
    settings = {"normalized": {"site_latitude_deg": 35., "true_north_deg": 0.}}
    return cells, site, preset, settings


@pytest.mark.parametrize("name,value", [("spatial_resolution_m", 0), ("spatial_resolution_m", float("nan")),
    ("temporal_step_minutes", 0), ("maximum_grid_points", 0), ("maximum_shadow_checks", 0)])
def test_invalid_sampling_inputs_block_before_grid_generation(name, value):
    cells, site, preset, settings = _validation_inputs()
    kwargs = {name: value}
    result = build_cell_field_forward_validation(cells, site, preset, settings, 4., **kwargs)
    assert result["complete"] is False
    assert result["blockers"][0]["failure_code"] == "invalid_cell_field_forward_validation_input"


def test_full_validation_shadow_check_guard_is_explicit_without_coarse_fallback():
    cells, site, preset, settings = _validation_inputs()
    result = build_cell_field_forward_validation(cells, site, preset, settings, 4., maximum_shadow_checks=1)
    assert result["complete"] is False
    blocker = result["blockers"][0]
    assert blocker["failure_code"] == "reverse_expansion_complexity_limit_exceeded"
    assert blocker["limit_type"] == "full_validation_shadow_checks"
    assert blocker["automatic_coarse_fallback_used"] is False
