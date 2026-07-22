import builtins
import importlib
import os

import shadow_utils
from shadow_inputs import _diagnose_shadow_casters, _diagnose_site_boundary
from shadow_geometry import _diagnose_shadow_caster_geometry
from shadow_debug import _build_debug_log_payload

GENERIC_ID = -2000151
WALL_ID = -2000011

class Id2024:
    def __init__(self, value): self.Value = value
class IdLegacy:
    def __init__(self, value): self.IntegerValue = value
class Category:
    def __init__(self, id_obj, name=''): self.Id=id_obj; self.Name=name
class NativeFamilyInstance:
    def __init__(self, category_id=GENERIC_ID, id_obj=None, geometry=None, fail=False):
        self.Id=IdLegacy(101); self.Category=Category(id_obj or IdLegacy(category_id), 'Generic Models'); self._geometry=geometry or []; self.fail=fail
    def get_Geometry(self, options):
        if self.fail: raise RuntimeError('C:/Users/alice/secret/model.rvt failed')
        return self._geometry
class Wrapper:
    def __init__(self, native): self.InternalElement=native
class Solid:
    def __init__(self, volume=1, faces=None, edges=None): self.Volume=volume; self.Faces=faces or []; self.Edges=edges or []
class Face:
    Area=1
    def __init__(self, normal_z=-1):
        self.FaceNormal=type('V', (), {'X':0,'Y':0,'Z':normal_z})()
        self.EdgeLoops=[]
class Edge:
    def AsCurve(self): return Curve()
class Curve:
    Length=1
    def GetEndPoint(self, i): return type('P', (), {'X':i,'Y':0,'Z':0})()
    def Tessellate(self): return []
class GeometryInstance:
    def __init__(self, geom): self.geom=geom
    def GetInstanceGeometry(self): return self.geom

def setup_module(module):
    class BIC:
        OST_GenericModel = GENERIC_ID
        OST_Mass = -2003400
        OST_Walls = WALL_ID
    shadow_utils.BuiltInCategory = BIC

def test_wrapper_internal_element_generic_model_accepted():
    native=NativeFamilyInstance(geometry=[])
    d=_diagnose_shadow_casters([Wrapper(native)])
    assert d['accepted_count']==1 and d['rejected_count']==0
    assert d['items'][0]['unwrap_strategy']=='InternalElement'
    assert d['items'][0]['official_revit_api_category']=='OST_GenericModel'

def test_unwrap_element_native_family_instance(monkeypatch):
    native=NativeFamilyInstance()
    builtins.UnwrapElement=lambda v: native
    try:
        d=_diagnose_shadow_casters([object()])
        assert d['accepted_count']==1
        assert d['items'][0]['unwrap_strategy']=='UnwrapElement'
    finally:
        del builtins.UnwrapElement

def test_category_id_value_and_integer_value():
    assert _diagnose_shadow_casters([NativeFamilyInstance(id_obj=Id2024(GENERIC_ID))])['accepted_count']==1
    assert _diagnose_shadow_casters([NativeFamilyInstance(id_obj=IdLegacy(GENERIC_ID))])['accepted_count']==1

def test_geometry_instance_positive_solid_counted_and_site_none_continues():
    solid=Solid(2, faces=[Face(-1)], edges=[Edge()])
    native=NativeFamilyInstance(geometry=[GeometryInstance([solid])])
    casters=_diagnose_shadow_casters([native])
    site=_diagnose_site_boundary(None)
    g=_diagnose_shadow_caster_geometry([native], casters, {'normalized':{}}, {'readiness':{'measurement_plane_constructed':True}})
    assert site['provided'] is False and site['boundary_dependent_steps_skipped'] is True
    assert g['solid_count']>=1 and g['positive_solid_count']>=1
    assert g['bottom_face_candidate_count']>=1
    assert g['geometry_readable_caster_count']>=1

def test_unsupported_category_rejected():
    assert _diagnose_shadow_casters([NativeFamilyInstance(category_id=WALL_ID)])['rejected_count']==1

def test_geometry_failure_warning_safe():
    d=_diagnose_shadow_casters([NativeFamilyInstance(fail=True)])
    assert d['accepted_count']==1
    assert d['items'][0]['geometry_access']['geometry_readable'] is False
    assert d['items'][0]['warnings']

def test_import_without_revit_api():
    import shadow_revit_api
    assert hasattr(shadow_revit_api, 'BuiltInCategory')

def test_debug_log_sanitizes_private_text():
    payload={'success':True,'shadow_casters':_diagnose_shadow_casters([NativeFamilyInstance(fail=True)]),'shadow_caster_geometry':{},'site_boundary':{},'measurement_plane':{},'warnings':['C:/Users/alice/MyProject.rvt alice@example.com']}
    debug=_build_debug_log_payload(payload)
    text=str(debug)
    assert 'C:/Users' not in text and 'alice@example.com' not in text

def test_formal_footprint_generated_from_box_bottom_loop():
    from shadow_footprint import _build_footprint_extraction_summary
    candidates = [{
        'candidate_index': 0,
        'endpoints_m_sample': [
            {'x': 0, 'y': 0, 'z': 0}, {'x': 2, 'y': 0, 'z': 0},
            {'x': 2, 'y': 0, 'z': 0}, {'x': 2, 'y': 1, 'z': 0},
            {'x': 2, 'y': 1, 'z': 0}, {'x': 0, 'y': 1, 'z': 0},
            {'x': 0, 'y': 1, 'z': 0}, {'x': 0, 'y': 0, 'z': 0},
        ],
        'closed_candidate': True,
        'horizontal_candidate': True,
        'curve_types': ['Line'],
        'has_arc_or_non_line_curve': False,
    }]
    geometry = {'accepted_caster_count': 1, 'items': [{'index': 0, 'accepted_shadow_caster': True, 'footprint_extraction': {'candidates': candidates, 'best_candidate': candidates[0]}}]}
    summary = _build_footprint_extraction_summary(geometry, {'readiness': {'measurement_plane_constructed': True}}, {'readiness': {'ready_for_equal_time_shadow_calculation': True}}, {})
    formal = summary['formal_footprints']
    assert formal['available'] is True
    assert formal['polygon_count'] == 1
    assert formal['outer_loop_count'] == 1
    assert formal['items'][0]['area_m2'] == 2.0
    assert formal['items'][0]['point_count'] == 4


def test_formal_footprint_rejects_self_intersection():
    from shadow_footprint import _build_formal_footprints_from_candidates
    candidate = {'candidate_index': 0, 'horizontal_candidate': True, 'curve_types': ['Line'], 'has_arc_or_non_line_curve': False, 'endpoints_m_sample': [
        {'x': 0, 'y': 0}, {'x': 1, 'y': 1},
        {'x': 1, 'y': 1}, {'x': 0, 'y': 1},
        {'x': 0, 'y': 1}, {'x': 1, 'y': 0},
        {'x': 1, 'y': 0}, {'x': 0, 'y': 0},
    ]}
    formal = _build_formal_footprints_from_candidates([{'index': 0, 'accepted_shadow_caster': True, 'footprint_extraction': {'candidates': [candidate]}}])
    assert formal['available'] is False
    assert formal['invalid_loop_count'] == 1
    assert 'self-intersecting' in formal['invalid_loops'][0]['reasons'][0]


_DEFAULT_CURVE_TYPES = object()

def _formal_candidate(curve_types=_DEFAULT_CURVE_TYPES, horizontal=True, non_line=False, source_face_index=2):
    return {
        'candidate_index': 0,
        'source_face_index': source_face_index,
        'loop_index': 3,
        'curve_types': ['Line'] if curve_types is _DEFAULT_CURVE_TYPES else curve_types,
        'has_arc_or_non_line_curve': non_line,
        'horizontal_candidate': horizontal,
        'endpoints_m_sample': [
            {'x': 0, 'y': 0, 'z': 0}, {'x': 1, 'y': 0, 'z': 0},
            {'x': 1, 'y': 0, 'z': 0}, {'x': 1, 'y': 1, 'z': 0},
            {'x': 1, 'y': 1, 'z': 0}, {'x': 0, 'y': 1, 'z': 0},
            {'x': 0, 'y': 1, 'z': 0}, {'x': 0, 'y': 0, 'z': 0},
        ],
    }


def _formal_from_candidates(candidates_by_caster):
    from shadow_footprint import _build_formal_footprints_from_candidates
    return _build_formal_footprints_from_candidates([
        {'index': i, 'accepted_shadow_caster': True, 'footprint_extraction': {'candidates': candidates}}
        for i, candidates in enumerate(candidates_by_caster)
    ])


def test_formal_footprint_rejects_arc_candidate():
    formal = _formal_from_candidates([[_formal_candidate(curve_types=['Line', 'Arc'], non_line=True)]])
    assert formal['available'] is False
    assert formal['invalid_loop_count'] == 1
    assert 'Line edges only' in formal['invalid_loops'][0]['reasons'][0]
    assert formal['ready_for_shadow_projection_input'] is False


def test_formal_footprint_rejects_spline_candidate():
    formal = _formal_from_candidates([[_formal_candidate(curve_types=['NurbSpline'])]])
    assert formal['available'] is False
    assert formal['invalid_loop_count'] == 1
    assert 'non-Line' in formal['invalid_loops'][0]['reasons'][0]


def test_formal_footprint_rejects_unknown_curve_types():
    for curve_types in ([], None):
        formal = _formal_from_candidates([[_formal_candidate(curve_types=curve_types)]])
        assert formal['available'] is False
        assert formal['invalid_loop_count'] == 1
        assert 'curve types were not verified' in formal['invalid_loops'][0]['reasons'][0]


def test_formal_footprint_rejects_non_horizontal_candidate():
    formal = _formal_from_candidates([[_formal_candidate(horizontal=False)]])
    assert formal['available'] is False
    assert formal['invalid_loop_count'] == 1
    assert 'verified horizontal' in formal['invalid_loops'][0]['reasons'][0]


def test_formal_footprint_rejects_unknown_horizontal_candidate():
    formal = _formal_from_candidates([[_formal_candidate(horizontal=None)]])
    assert formal['available'] is False
    assert formal['invalid_loop_count'] == 1
    assert 'verified horizontal' in formal['invalid_loops'][0]['reasons'][0]


def test_formal_footprint_partial_when_one_caster_has_line_and_arc_loops():
    formal = _formal_from_candidates([[
        _formal_candidate(),
        _formal_candidate(curve_types=['Line', 'Arc'], non_line=True),
    ]])
    assert formal['available'] is True
    assert formal['complete'] is False
    assert formal['partial_success'] is True
    assert formal['invalid_loop_count'] == 1
    assert formal['ready_for_shadow_projection_input'] is False


def test_formal_footprint_partial_when_one_of_multiple_casters_fails():
    formal = _formal_from_candidates([[_formal_candidate()], [_formal_candidate(curve_types=['Arc'], non_line=True)]])
    assert formal['successful_caster_count'] == 1
    assert formal['failed_caster_count'] == 1
    assert formal['complete'] is False
    assert formal['partial_success'] is True


def test_formal_footprint_accepts_concave_line_horizontal_loop():
    candidate = _formal_candidate()
    candidate['endpoints_m_sample'] = [
        {'x': 0, 'y': 0}, {'x': 2, 'y': 0},
        {'x': 2, 'y': 0}, {'x': 2, 'y': 2},
        {'x': 2, 'y': 2}, {'x': 1, 'y': 1},
        {'x': 1, 'y': 1}, {'x': 0, 'y': 2},
        {'x': 0, 'y': 2}, {'x': 0, 'y': 0},
    ]
    formal = _formal_from_candidates([[candidate]])
    assert formal['available'] is True
    assert formal['complete'] is True
    assert formal['items'][0]['point_count'] == 5
    assert formal['items'][0]['area_m2'] == 3.0


def test_formal_footprint_accepts_outer_and_inner_line_horizontal_loops():
    inner = _formal_candidate()
    inner['candidate_index'] = 1
    inner['endpoints_m_sample'] = [
        {'x': 0.25, 'y': 0.25}, {'x': 0.25, 'y': 0.75},
        {'x': 0.25, 'y': 0.75}, {'x': 0.75, 'y': 0.75},
        {'x': 0.75, 'y': 0.75}, {'x': 0.75, 'y': 0.25},
        {'x': 0.75, 'y': 0.25}, {'x': 0.25, 'y': 0.25},
    ]
    formal = _formal_from_candidates([[_formal_candidate(), inner]])
    assert formal['complete'] is True
    assert formal['outer_loop_count'] == 1
    assert formal['inner_loop_count'] == 1


def _candidate_from_edges(edges, candidate_index=0, source_face_index=2):
    candidate = _formal_candidate(source_face_index=source_face_index)
    candidate['candidate_index'] = candidate_index
    candidate['endpoints_m_sample'] = []
    for a, b in edges:
        candidate['endpoints_m_sample'].extend([{'x': a[0], 'y': a[1]}, {'x': b[0], 'y': b[1]}])
    return candidate


def test_formal_footprint_stitches_reversed_edge_rectangle():
    edges = [((0, 0), (2, 0)), ((2, 1), (2, 0)), ((2, 1), (0, 1)), ((0, 0), (0, 1))]
    formal = _formal_from_candidates([[_candidate_from_edges(edges)]])
    assert formal['complete'] is True
    assert formal['items'][0]['area_m2'] == 2.0
    assert formal['items'][0]['role'] == 'outer'
    assert formal['items'][0]['orientation'] == 'ccw'


def test_formal_footprint_stitches_shuffled_rectangle_edges():
    edges = [((2, 1), (0, 1)), ((0, 0), (2, 0)), ((0, 1), (0, 0)), ((2, 0), (2, 1))]
    formal = _formal_from_candidates([[_candidate_from_edges(edges)]])
    assert formal['complete'] is True
    assert formal['items'][0]['point_count'] == 4
    assert formal['items'][0]['area_m2'] == 2.0


def test_formal_footprint_rejects_open_loop_segment_graph():
    edges = [((0, 0), (1, 0)), ((1, 0), (1, 1)), ((1, 1), (0, 1))]
    formal = _formal_from_candidates([[_candidate_from_edges(edges)]])
    assert formal['available'] is False
    assert formal['invalid_loop_count'] == 1
    assert 'open' in formal['invalid_loops'][0]['reasons'][0]


def test_formal_footprint_rejects_branch_segment_graph():
    edges = [((0, 0), (1, 0)), ((1, 0), (1, 1)), ((1, 1), (0, 0)), ((1, 0), (2, 0))]
    formal = _formal_from_candidates([[_candidate_from_edges(edges)]])
    assert formal['available'] is False
    assert formal['invalid_loop_count'] == 1
    assert 'branch' in formal['invalid_loops'][0]['reasons'][0]


def test_formal_footprint_rejects_duplicate_edge():
    edges = [((0, 0), (1, 0)), ((1, 0), (1, 1)), ((1, 1), (0, 0)), ((1, 0), (0, 0))]
    formal = _formal_from_candidates([[_candidate_from_edges(edges)]])
    assert formal['available'] is False
    assert formal['invalid_loop_count'] == 1
    assert 'duplicate edge' in formal['invalid_loops'][0]['reasons'][0]


def test_formal_footprint_rejects_tiny_edge():
    edges = [((0, 0), (0.0001, 0)), ((0.0001, 0), (1, 1)), ((1, 1), (0, 0))]
    formal = _formal_from_candidates([[_candidate_from_edges(edges)]])
    assert formal['available'] is False
    assert formal['invalid_loop_count'] == 1
    assert 'short edge' in formal['invalid_loops'][0]['reasons'][0]


def test_formal_footprint_classifies_reversed_winding_outer_and_inner_by_containment():
    outer = _candidate_from_edges([((0, 0), (0, 2)), ((0, 2), (2, 2)), ((2, 2), (2, 0)), ((2, 0), (0, 0))], 0)
    inner = _candidate_from_edges([((0.5, 0.5), (1.5, 0.5)), ((1.5, 0.5), (1.5, 1.5)), ((1.5, 1.5), (0.5, 1.5)), ((0.5, 1.5), (0.5, 0.5))], 1)
    formal = _formal_from_candidates([[outer, inner]])
    assert formal['complete'] is True
    roles = {p['source_candidate_index']: (p['role'], p['orientation'], p['containment_depth']) for p in formal['items']}
    assert roles[0] == ('outer', 'ccw', 0)
    assert roles[1] == ('inner', 'cw', 1)


def test_formal_footprint_preserves_multiple_casters_without_union():
    c0 = _candidate_from_edges([((0, 0), (1, 0)), ((1, 0), (1, 1)), ((1, 1), (0, 1)), ((0, 1), (0, 0))])
    c1 = _candidate_from_edges([((0.5, 0.5), (1.5, 0.5)), ((1.5, 0.5), (1.5, 1.5)), ((1.5, 1.5), (0.5, 1.5)), ((0.5, 1.5), (0.5, 0.5))])
    formal = _formal_from_candidates([[c0], [c1]])
    assert formal['complete'] is True
    assert formal['polygon_count'] == 2
    assert formal['successful_caster_count'] == 2
    assert formal['boolean_union_performed'] is False
    assert sorted(p['source_caster_index'] for p in formal['items']) == [0, 1]



def test_formal_footprint_classifies_same_face_outer_and_hole():
    outer = _candidate_from_edges([((0, 0), (4, 0)), ((4, 0), (4, 4)), ((4, 4), (0, 4)), ((0, 4), (0, 0))], 0, source_face_index=10)
    inner = _candidate_from_edges([((1, 1), (2, 1)), ((2, 1), (2, 2)), ((2, 2), (1, 2)), ((1, 2), (1, 1))], 1, source_face_index=10)
    formal = _formal_from_candidates([[outer, inner]])
    assert formal['complete'] is True
    assert formal['outer_loop_count'] == 1
    assert formal['inner_loop_count'] == 1
    roles = {p['source_candidate_index']: p for p in formal['items']}
    assert roles[0]['role'] == 'outer'
    assert roles[0]['orientation'] == 'ccw'
    assert roles[0]['containment_depth'] == 0
    assert roles[0]['classification_group_key'] == [0, 10]
    assert roles[1]['role'] == 'inner'
    assert roles[1]['orientation'] == 'cw'
    assert roles[1]['containment_depth'] == 1
    assert roles[1]['classification_group_key'] == [0, 10]


def test_formal_footprint_same_caster_different_faces_nested_rectangles_are_outer():
    large = _candidate_from_edges([((0, 0), (4, 0)), ((4, 0), (4, 4)), ((4, 4), (0, 4)), ((0, 4), (0, 0))], 0, source_face_index=20)
    small = _candidate_from_edges([((1, 1), (2, 1)), ((2, 1), (2, 2)), ((2, 2), (1, 2)), ((1, 2), (1, 1))], 1, source_face_index=21)
    formal = _formal_from_candidates([[large, small]])
    assert formal['complete'] is True
    assert formal['outer_loop_count'] == 2
    assert formal['inner_loop_count'] == 0
    assert {tuple(p['classification_group_key']) for p in formal['items']} == {(0, 20), (0, 21)}
    assert {p['containment_depth'] for p in formal['items']} == {0}


def test_formal_footprint_multiple_solid_like_nested_faces_do_not_create_hole():
    large = _candidate_from_edges([((0, 0), (5, 0)), ((5, 0), (5, 5)), ((5, 5), (0, 5)), ((0, 5), (0, 0))], 0, source_face_index=30)
    small = _candidate_from_edges([((2, 2), (3, 2)), ((3, 2), (3, 3)), ((3, 3), (2, 3)), ((2, 3), (2, 2))], 1, source_face_index=31)
    formal = _formal_from_candidates([[large, small]])
    assert formal['complete'] is True
    assert [p['role'] for p in sorted(formal['items'], key=lambda p: p['source_candidate_index'])] == ['outer', 'outer']
    assert formal['inner_loop_count'] == 0
    assert formal['boolean_union_performed'] is False


def test_formal_footprint_stitches_endpoint_across_rounding_boundary_within_tolerance():
    tol = 0.01
    # The first segment ends at x=1.0049 and the next starts at x=1.0051.
    # Their distance is within tolerance, while round(x / tol) would place them in adjacent buckets.
    edges = [
        ((0, 0), (1.0049, 0)),
        ((1.0051, 0), (1, 1)),
        ((1, 1), (0, 1)),
        ((0, 1), (0, 0)),
    ]
    formal = _build_formal_for_edges_with_tolerance(edges, tol)
    assert formal['complete'] is True
    assert formal['polygon_count'] == 1


def test_formal_footprint_rejects_endpoint_gap_above_tolerance_as_open():
    tol = 0.01
    edges = [
        ((0, 0), (1, 0)),
        ((1.02, 0), (1, 1)),
        ((1, 1), (0, 1)),
        ((0, 1), (0, 0)),
    ]
    formal = _build_formal_for_edges_with_tolerance(edges, tol)
    assert formal['available'] is False
    assert formal['invalid_loop_count'] == 1
    assert 'open' in formal['invalid_loops'][0]['reasons'][0]


def _build_formal_for_edges_with_tolerance(edges, tolerance_m):
    from shadow_footprint import _build_formal_footprints_from_candidates
    return _build_formal_footprints_from_candidates([
        {'index': 0, 'accepted_shadow_caster': True, 'footprint_extraction': {'candidates': [_candidate_from_edges(edges)]}}
    ], tolerance_m=tolerance_m)


def test_footprint_summary_uses_settings_closure_tolerance_m():
    from shadow_footprint import _build_footprint_extraction_summary
    edges = [
        ((0, 0), (1, 0)),
        ((1.005, 0), (1, 1)),
        ((1, 1), (0, 1)),
        ((0, 1), (0, 0)),
    ]
    item = {'index': 0, 'accepted_shadow_caster': True, 'footprint_extraction': {'candidates': [_candidate_from_edges(edges)]}}
    geometry = {'items': [item], 'accepted_caster_count': 1, 'footprint_loop_candidate_count': 1}
    strict = _build_footprint_extraction_summary(geometry, {}, {'normalized': {'closure_tolerance_m': 0.001}}, {})
    loose = _build_footprint_extraction_summary(geometry, {}, {'normalized': {'closure_tolerance_m': 0.01}}, {})
    assert strict['formal_footprints']['tolerance_m_used'] == 0.001
    assert strict['formal_footprints']['available'] is False
    assert loose['formal_footprints']['tolerance_m_used'] == 0.01
    assert loose['formal_footprints']['available'] is True



def test_formal_footprint_missing_source_face_index_is_independent_outer():
    candidate = _candidate_from_edges([((0, 0), (1, 0)), ((1, 0), (1, 1)), ((1, 1), (0, 1)), ((0, 1), (0, 0))])
    candidate['source_face_index'] = None
    formal = _formal_from_candidates([[candidate]])
    assert formal['complete'] is True
    assert formal['outer_loop_count'] == 1
    assert formal['inner_loop_count'] == 0
    item = formal['items'][0]
    assert item['role'] == 'outer'
    assert item['containment_depth'] == 0
    assert item['classification_group_key'] == [0, None, 0]
