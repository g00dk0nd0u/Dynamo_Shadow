import math

from shadow_duration import integrate_shadow_states_trapezoidal
from shadow_forward_equivalent_validator import (build_prismatic_forward_equivalent_duration,
    is_prism_shadowed)
from shadow_sun import _sun_position_for_true_solar_minutes
from shadow_regulatory_presets import resolve_regulatory_shadow_preset
from shadow_site_masks import build_measurement_masks

RECT = [(0, 0), (2, 0), (2, 2), (0, 2)]

def solar(minutes=720, north=0):
    return _sun_position_for_true_solar_minutes(minutes, 35, -23.439, north)

def test_height_at_measurement_plane_never_shadows():
    assert not is_prism_shadowed((1, -5), RECT, 4, 4, solar())

def test_finite_toward_sun_segment_hits_or_misses_rectangle():
    item = {'shadow_direction_model': {'x': 0, 'y': -1}, 'shadow_length_factor': 2}
    assert is_prism_shadowed((1, -3), RECT, 6, 4, item)
    assert not is_prism_shadowed((4, -3), RECT, 6, 4, item)

def test_concavity_does_not_use_bounding_box():
    l_shape = [(0,0),(4,0),(4,1),(1,1),(1,4),(0,4)]
    item = {'shadow_direction_model': {'x': 0, 'y': -1}, 'shadow_length_factor': 1}
    assert not is_prism_shadowed((3, 3), l_shape, 5, 4, item)

def test_true_north_rotates_shadow_relation():
    noon = solar(720, 0); rotated = solar(720, 90)
    point = (1, 3)
    assert is_prism_shadowed(point, RECT, 10, 4, noon)
    assert not is_prism_shadowed(point, RECT, 10, 4, rotated)

def test_shared_trapezoidal_helper_is_exact():
    assert integrate_shadow_states_trapezoidal([False, True, True, False], [0, 15, 30, 45]) == 30.0

def test_half_metre_grid_and_measurement_masks_are_deterministic():
    fixture={'site_boundary':[[0,0],[4,0],[4,4],[0,4]],'building_footprint':[[1,1],[3,1],[3,3],[1,3]],
      'building_height_m':4,'measurement_height_m':4,'site_latitude_deg':35,'true_north_deg':0}
    preset=resolve_regulatory_shadow_preset('standard_3_2')
    first=build_prismatic_forward_equivalent_duration(fixture,preset)
    second=build_prismatic_forward_equivalent_duration(fixture,preset)
    assert first['grid_spec']==second['grid_spec'] and first['duration_grid']==second['duration_grid']
    assert all(p['shadow_duration_minutes']==0 for p in first['duration_grid'])
    site={'complete':True,'outer_loop':[{'x_m':x,'y_m':y} for x,y in fixture['site_boundary']]}
    assert build_measurement_masks(first,site)==build_measurement_masks(second,site)
