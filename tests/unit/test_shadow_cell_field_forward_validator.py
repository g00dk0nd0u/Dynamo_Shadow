from shadow_cell_field_forward_validator import build_cell_field_shadow_states, is_cell_shadowed
from shadow_duration import integrate_shadow_states_trapezoidal


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
