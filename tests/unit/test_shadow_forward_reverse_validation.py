from shadow_forward_reverse_validation import (evaluate_prism_against_reverse_envelope,
                                                interpolate_reverse_height)

def surface(omit=False):
    points=[{'x_m':0,'y_m':0,'height_limit_m':5},{'x_m':1,'y_m':0,'height_limit_m':6},
            {'x_m':1,'y_m':1,'height_limit_m':7},{'x_m':0,'y_m':1,'height_limit_m':6}]
    triangles=[] if omit else [{'vertex_grid_indices':[0,1,2]},{'vertex_grid_indices':[0,2,3]}]
    return {'height_field':{'grid_points':points},'top_surface_mesh':{'triangles':triangles}}

def test_triangle_vertices_and_linear_interior_interpolate():
    result=surface()
    assert interpolate_reverse_height(result,0,0)==5
    assert interpolate_reverse_height(result,1,1)==7
    assert interpolate_reverse_height(result,.5,.5)==6

def test_fit_below_above_and_omitted_surface():
    polygon=[(.1,.1),(.9,.1),(.9,.9),(.1,.9)]
    assert evaluate_prism_against_reverse_envelope(polygon,4,surface())['fully_inside']
    above=evaluate_prism_against_reverse_envelope(polygon,7,surface())
    assert not above['fully_inside'] and above['exceeded_point_count']>0 and above['maximum_height_excess_m']>.5
    omitted=evaluate_prism_against_reverse_envelope(polygon,4,surface(True))
    assert not omitted['fully_inside'] and omitted['unbounded_point_count']==omitted['validation_point_count']

def test_fit_summary_order_is_deterministic():
    polygon=[(.1,.1),(.9,.1),(.9,.9),(.1,.9)]
    assert evaluate_prism_against_reverse_envelope(polygon,6,surface()) == evaluate_prism_against_reverse_envelope(list(reversed(polygon)),6,surface())
