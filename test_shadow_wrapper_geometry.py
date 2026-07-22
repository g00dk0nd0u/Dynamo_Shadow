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


def _candidate_from_segments(segments, candidate_index=0, caster_index=None, face_index=0):
    endpoints = []
    for start, end in segments:
        endpoints.append({'x': start[0], 'y': start[1], 'z': 0})
        endpoints.append({'x': end[0], 'y': end[1], 'z': 0})
    candidate = {
        'candidate_index': candidate_index,
        'source_face_index': face_index,
        'loop_index': candidate_index,
        'endpoints_m': endpoints,
        'closed_candidate': True,
        'horizontal_candidate': True,
    }
    if caster_index is not None:
        candidate['caster_index'] = caster_index
    return candidate


def _item(index, candidates):
    return {'index': index, 'accepted_shadow_caster': True, 'footprint_extraction': {'candidates': candidates, 'best_candidate': candidates[0] if candidates else None}}


def _rectangle_segments(x0=0, y0=0, x1=2, y1=1):
    return [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]


def test_formal_footprint_simple_rectangle_outer():
    from shadow_footprint import _build_formal_footprints_from_candidates
    formal = _build_formal_footprints_from_candidates([_item(0, [_candidate_from_segments(_rectangle_segments())])])
    assert formal['available'] is True
    assert formal['complete'] is True
    assert formal['items'][0]['point_count'] == 4
    assert formal['items'][0]['area_m2'] == 2.0
    assert formal['items'][0]['role'] == 'outer'
    assert formal['items'][0]['orientation'] == 'ccw'


def test_formal_footprint_rebuilds_rectangle_with_reversed_edges():
    from shadow_footprint import _build_formal_footprints_from_candidates
    segments = [((0, 0), (2, 0)), ((2, 1), (2, 0)), ((0, 1), (2, 1)), ((0, 1), (0, 0))]
    formal = _build_formal_footprints_from_candidates([_item(0, [_candidate_from_segments(segments)])])
    assert formal['available'] is True
    assert formal['complete'] is True
    assert formal['items'][0]['area_m2'] == 2.0
    assert formal['items'][0]['point_count'] == 4


def test_formal_footprint_rebuilds_shuffled_rectangle():
    from shadow_footprint import _build_formal_footprints_from_candidates
    segments = [_rectangle_segments()[2], _rectangle_segments()[0], _rectangle_segments()[3], _rectangle_segments()[1]]
    formal = _build_formal_footprints_from_candidates([_item(0, [_candidate_from_segments(segments)])])
    assert formal['available'] is True
    assert formal['complete'] is True
    assert formal['items'][0]['area_m2'] == 2.0


def test_formal_footprint_concave_shape_preserves_area():
    from shadow_footprint import _build_formal_footprints_from_candidates, _has_self_intersection
    segments = [((0, 0), (3, 0)), ((3, 0), (3, 2)), ((3, 2), (2, 2)), ((2, 2), (2, 1)), ((2, 1), (1, 1)), ((1, 1), (1, 2)), ((1, 2), (0, 2)), ((0, 2), (0, 0))]
    formal = _build_formal_footprints_from_candidates([_item(0, [_candidate_from_segments(segments)])])
    assert formal['available'] is True
    assert formal['complete'] is True
    assert formal['items'][0]['area_m2'] == 5.0
    assert _has_self_intersection(formal['items'][0]['points_m']) is False


def test_formal_footprint_outer_and_hole_ignore_input_winding():
    from shadow_footprint import _build_formal_footprints_from_candidates
    outer_cw = list(reversed([((0, 0), (4, 0)), ((4, 0), (4, 4)), ((4, 4), (0, 4)), ((0, 4), (0, 0))]))
    hole_ccw = [((1, 1), (3, 1)), ((3, 1), (3, 3)), ((3, 3), (1, 3)), ((1, 3), (1, 1))]
    formal = _build_formal_footprints_from_candidates([_item(0, [_candidate_from_segments(outer_cw, 0), _candidate_from_segments(hole_ccw, 1)])])
    roles = sorted([p['role'] for p in formal['items']])
    assert roles == ['inner', 'outer']
    assert formal['outer_loop_count'] == 1
    assert formal['inner_loop_count'] == 1
    assert [p for p in formal['items'] if p['role'] == 'outer'][0]['orientation'] == 'ccw'
    assert [p for p in formal['items'] if p['role'] == 'inner'][0]['orientation'] == 'cw'


def test_formal_footprint_rejects_self_intersection():
    from shadow_footprint import _build_formal_footprints_from_candidates
    segments = [((0, 0), (1, 1)), ((1, 1), (0, 1)), ((0, 1), (1, 0)), ((1, 0), (0, 0))]
    formal = _build_formal_footprints_from_candidates([_item(0, [_candidate_from_segments(segments)])])
    assert formal['available'] is False
    assert formal['invalid_loop_count'] == 1
    assert 'self-intersecting' in formal['invalid_loops'][0]['reasons'][0]


def test_formal_footprint_rejects_open_loop():
    from shadow_footprint import _build_formal_footprints_from_candidates
    segments = [((0, 0), (2, 0)), ((2, 0), (2, 1)), ((2, 1), (0, 1))]
    formal = _build_formal_footprints_from_candidates([_item(0, [_candidate_from_segments(segments)])])
    assert formal['available'] is False
    assert formal['invalid_loop_count'] == 1
    assert any('open or isolated endpoint' in reason for reason in formal['invalid_loops'][0]['reasons'])


def test_formal_footprint_rejects_branch():
    from shadow_footprint import _build_formal_footprints_from_candidates
    segments = _rectangle_segments() + [((0, 0), (-1, 0))]
    formal = _build_formal_footprints_from_candidates([_item(0, [_candidate_from_segments(segments)])])
    assert formal['available'] is False
    assert formal['invalid_loop_count'] == 1
    assert any('branch detected' in reason for reason in formal['invalid_loops'][0]['reasons'])


def test_formal_footprint_rejects_duplicate_edge():
    from shadow_footprint import _build_formal_footprints_from_candidates
    segments = _rectangle_segments() + [((2, 0), (0, 0))]
    formal = _build_formal_footprints_from_candidates([_item(0, [_candidate_from_segments(segments)])])
    assert formal['available'] is False
    assert formal['invalid_loop_count'] == 1
    assert any('duplicate edge' in reason for reason in formal['invalid_loops'][0]['reasons'])


def test_formal_footprint_rejects_tiny_edge():
    from shadow_footprint import _build_formal_footprints_from_candidates
    segments = [((0, 0), (0.0005, 0)), ((0.0005, 0), (2, 0)), ((2, 0), (2, 1)), ((2, 1), (0, 1)), ((0, 1), (0, 0))]
    formal = _build_formal_footprints_from_candidates([_item(0, [_candidate_from_segments(segments)])], tolerance_m=0.001)
    assert formal['available'] is False
    assert any('shorter than or equal to tolerance' in reason for reason in formal['invalid_loops'][0]['reasons'])


def test_formal_footprint_multiple_casters_remain_separate_no_union():
    from shadow_footprint import _build_formal_footprints_from_candidates
    formal = _build_formal_footprints_from_candidates([_item(0, [_candidate_from_segments(_rectangle_segments())]), _item(1, [_candidate_from_segments(_rectangle_segments(3, 0, 5, 1))])])
    assert formal['available'] is True
    assert formal['complete'] is True
    assert formal['caster_count'] == 2
    assert formal['successful_caster_count'] == 2
    assert formal['polygon_count'] == 2
    assert formal['boolean_union_performed'] is False


def test_formal_footprint_partial_caster_failure_blocks_projection_input():
    from shadow_footprint import _build_formal_footprints_from_candidates
    good = _item(0, [_candidate_from_segments(_rectangle_segments())])
    bad = _item(1, [_candidate_from_segments([((0, 0), (1, 0)), ((1, 0), (1, 1))])])
    formal = _build_formal_footprints_from_candidates([good, bad])
    assert formal['available'] is True
    assert formal['complete'] is False
    assert formal['partial_success'] is True
    assert formal['successful_caster_count'] == 1
    assert formal['failed_caster_count'] == 1
    assert formal['ready_for_shadow_projection_input'] is False
