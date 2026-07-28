import builtins
import importlib
import os
import sys
import types

import shadow_utils
import shadow_inputs
from shadow_settings import _normalize_settings
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
    def __init__(self, category_id=GENERIC_ID, id_obj=None, element_id_obj=None, geometry=None, fail=False):
        self.Id=element_id_obj or IdLegacy(101); self.Category=Category(id_obj or IdLegacy(category_id), 'Generic Models'); self._geometry=geometry or []; self.fail=fail
    def get_Geometry(self, options):
        if self.fail: raise RuntimeError('C:/Users/alice/secret/model.rvt failed')
        return self._geometry
class Wrapper:
    def __init__(self, native): self.InternalElement=native
class MisleadingWrapper:
    __module__ = 'Revit.Elements'
    def __init__(self, native=None, internal_id=None):
        self.Category=Category(IdLegacy(GENERIC_ID), 'Generic Models')
        self.Id=IdLegacy(999)
        if native is not None: self.InternalElement=native
        if internal_id is not None: self.InternalElementId=internal_id
    def get_Geometry(self, options): return []
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
class SymbolGeometryInstance:
    def __init__(self, geom): self.geom=geom
    def GetInstanceGeometry(self): return []
    def GetSymbolGeometry(self): return self.geom

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

def test_wrapper_category_and_id_do_not_make_native_element():
    wrapper = MisleadingWrapper()
    assert shadow_utils._is_native_revit_element_like(wrapper) is False
    assert _diagnose_shadow_casters([wrapper])['rejected_count'] == 1

def test_unwrap_returning_wrapper_then_internal_element(monkeypatch):
    native = NativeFamilyInstance()
    wrapper = MisleadingWrapper(native=native)
    monkeypatch.setattr(builtins, 'UnwrapElement', lambda value: wrapper, raising=False)
    diagnostics = _diagnose_shadow_casters([object()])
    assert diagnostics['accepted_count'] == 1
    assert diagnostics['items'][0]['unwrap_strategy'] == 'UnwrapElement.InternalElement'

def test_internal_element_id_document_fallback(monkeypatch):
    native = NativeFamilyInstance()
    wrapper = MisleadingWrapper(internal_id=Id2024(101))
    monkeypatch.setattr(shadow_utils, '_try_document_get_element', lambda element_id: native)
    diagnostics = _diagnose_shadow_casters([wrapper])
    assert diagnostics['accepted_count'] == 1
    assert diagnostics['items'][0]['unwrap_strategy'] == 'InternalElementId.CurrentDBDocument.GetElement'

def test_category_id_value_and_integer_value():
    modern = _diagnose_shadow_casters([NativeFamilyInstance(id_obj=Id2024(GENERIC_ID))])
    legacy = _diagnose_shadow_casters([NativeFamilyInstance(id_obj=IdLegacy(GENERIC_ID))])
    assert modern['accepted_count']==1 and modern['items'][0]['category_id_raw_type'] == 'Id2024'
    assert legacy['accepted_count']==1 and legacy['items'][0]['category_id_raw_type'] == 'IdLegacy'

def test_element_id_value_and_integer_value_read_methods():
    modern = _diagnose_shadow_casters([NativeFamilyInstance(element_id_obj=Id2024(2024))])['items'][0]
    legacy = _diagnose_shadow_casters([NativeFamilyInstance(element_id_obj=IdLegacy(2023))])['items'][0]
    assert modern['element_id'] == 2024 and modern['element_id_read_method'] == 'Value'
    assert legacy['element_id'] == 2023 and legacy['element_id_read_method'] == 'IntegerValue'

def test_true_solar_time_aliases_fill_missing_canonical_keys():
    result = _normalize_settings({'true_solar_start_time':'08:00', 'true_solar_end_time':'16:00'})
    assert result['normalized']['analysis_start_time'] == '08:00'
    assert result['normalized']['analysis_end_time'] == '16:00'
    assert len([line for line in result['info'] if 'compatibility alias' in line]) == 2

def test_canonical_times_take_precedence_over_aliases():
    result = _normalize_settings({'analysis_start_time':'09:00', 'analysis_end_time':'15:00', 'true_solar_start_time':'08:00', 'true_solar_end_time':'16:00'})
    assert result['normalized']['analysis_start_time'] == '09:00'
    assert result['normalized']['analysis_end_time'] == '15:00'
    assert not [line for line in result['info'] if 'compatibility alias' in line]

def test_unwrap_is_found_in_exec_script_globals():
    native = NativeFamilyInstance()
    script_globals = {'UnwrapElement': lambda value: native, 'value': object()}
    exec('result = _try_unwrap_with_diagnostics(value)', dict(shadow_utils.__dict__, **script_globals), script_globals)
    assert script_globals['result'][0] is native
    assert script_globals['result'][1]['unwrap_strategy'] == 'UnwrapElement'

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

def test_symbol_geometry_fallback_and_non_positive_solid_exclusion():
    positive = Solid(2, faces=[Face(-1)])
    zero = Solid(0, faces=[Face(-1)])
    native = NativeFamilyInstance(geometry=[SymbolGeometryInstance([positive, zero])])
    casters = _diagnose_shadow_casters([native])
    geometry = _diagnose_shadow_caster_geometry([native], casters, {'normalized':{}}, {})
    assert geometry['solid_count'] == 1
    assert geometry['positive_solid_count'] == 1
    assert geometry['bottom_face_candidate_count'] == 1

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


def _load_loader_definitions():
    """Load the real loader helpers without invoking its Dynamo OUT assignment."""
    loader_path = os.path.join(os.path.dirname(__file__), 'dynamo_loader.py')
    namespace = {
        '__file__': loader_path,
        '__name__': '__loader_test__',
        'IN': [],
    }
    fake_clr = types.ModuleType('clr')
    fake_clr.AddReference = lambda name: None
    previous = sys.modules.get('clr')
    sys.modules['clr'] = fake_clr
    try:
        with open(loader_path, 'r', encoding='utf-8') as stream:
            code = stream.read().rsplit('\nOUT = run_script()', 1)[0]
        exec(compile(code, loader_path, 'exec'), namespace)
    finally:
        if previous is None:
            sys.modules.pop('clr', None)
        else:
            sys.modules['clr'] = previous
    return namespace


def _write_loader_workspace(path, marker):
    (path / 'shadow_settings.py').write_text(
        'MARKER = {!r}\n'.format(marker), encoding='utf-8'
    )
    (path / 'script.py').write_text(
        'import shadow_settings\n'
        'OUT = {"success": True, "marker": shadow_settings.MARKER, '
        '"bootstrap": RUNTIME_IMPORT_BOOTSTRAP}\n',
        encoding='utf-8',
    )


def test_loader_removes_stale_cache_forces_workspace_first_and_preserves_external(tmp_path):
    loader = _load_loader_definitions()
    workspace = tmp_path / 'workspace'
    stale = tmp_path / 'stale'
    workspace.mkdir()
    stale.mkdir()
    _write_loader_workspace(workspace, 'fresh-workspace')
    stale_module = types.ModuleType('shadow_settings')
    stale_module.MARKER = 'stale-cache'
    unrelated = types.ModuleType('shadow_external_not_in_workspace')
    old_path = list(sys.path)
    old_settings = sys.modules.get('shadow_settings')
    sys.modules['shadow_settings'] = stale_module
    sys.modules['shadow_external_not_in_workspace'] = unrelated
    sys.path[:] = [str(stale), 'unchanged', str(workspace), str(workspace)] + old_path
    loader['resolve_workspace'] = lambda: ('Shadow.dyn', str(workspace), 'dynamo_loader.py')
    try:
        result = loader['run_script']()
        assert result['marker'] == 'fresh-workspace'
        assert sys.path[0] == loader['_normalized_path'](str(workspace))
        assert sum(loader['_normalized_path'](entry) == sys.path[0] for entry in sys.path if entry) == 1
        assert result['bootstrap']['removed_cached_modules'] == ['shadow_settings']
        assert sys.modules['shadow_external_not_in_workspace'] is unrelated
    finally:
        sys.path[:] = old_path
        sys.modules.pop('shadow_external_not_in_workspace', None)
        if old_settings is None:
            sys.modules.pop('shadow_settings', None)
        else:
            sys.modules['shadow_settings'] = old_settings


def test_loader_consecutive_exec_reads_updated_workspace_module(tmp_path):
    loader = _load_loader_definitions()
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    loader['resolve_workspace'] = lambda: ('Shadow.dyn', str(workspace), 'dynamo_loader.py')
    old_path = list(sys.path)
    old_settings = sys.modules.get('shadow_settings')
    try:
        _write_loader_workspace(workspace, 'first-version')
        assert loader['run_script']()['marker'] == 'first-version'
        _write_loader_workspace(workspace, 'second-version-longer')
        assert loader['run_script']()['marker'] == 'second-version-longer'
    finally:
        sys.path[:] = old_path
        if old_settings is None:
            sys.modules.pop('shadow_settings', None)
        else:
            sys.modules['shadow_settings'] = old_settings


def test_script_reports_local_module_source_mismatch(tmp_path):
    script_path = os.path.join(os.path.dirname(__file__), 'script.py')
    previous = sys.modules.get('shadow_settings')
    outside_module = types.ModuleType('shadow_settings')
    outside_module.__dict__.update(previous.__dict__)
    outside_module.__file__ = str(tmp_path / 'outside' / 'shadow_settings.py')
    sys.modules['shadow_settings'] = outside_module
    namespace = {
        '__file__': script_path,
        '__name__': '__script_source_mismatch_test__',
        'INPUTS': {},
        'RUNTIME_IMPORT_BOOTSTRAP': {
            'loader_build_id': 'test-loader',
            'workspace_resolved': True,
            'workspace_inserted_at_sys_path_zero': True,
            'import_caches_invalidated': True,
            'local_module_names': ['shadow_settings'],
            'removed_cached_modules': [],
            'cached_module_count_removed': 0,
        },
    }
    try:
        with open(script_path, 'r', encoding='utf-8') as stream:
            exec(compile(stream.read(), script_path, 'exec'), namespace)
        assert namespace['OUT']['success'] is False
        assert namespace['OUT']['error_code'] == 'local_module_source_mismatch'
        module = namespace['OUT']['runtime_code_diagnostics']['modules'][0]
        assert module == {
            'module_name': 'shadow_settings',
            'module_filename': 'shadow_settings.py',
            'loaded_from_workspace': False,
            'module_file_available': True,
        }
    finally:
        if previous is None:
            sys.modules.pop('shadow_settings', None)
        else:
            sys.modules['shadow_settings'] = previous


def test_runtime_code_diagnostics_debug_summary_is_allowlisted_and_private_path_free():
    payload = {
        'success': True,
        'runtime_code_diagnostics': {
            'code_build_id': '2026-07-28-module-isolation-v1',
            'all_local_modules_from_workspace': True,
            'workspace_path': r'C:\Users\alice\private\Shadow.dyn',
            'modules': [{
                'module_name': 'shadow_utils',
                'module_filename': 'shadow_utils.py',
                'loaded_from_workspace': True,
                'module_file_available': True,
                'absolute_path': r'C:\Users\alice\private\shadow_utils.py',
            }],
        },
    }
    debug = _build_debug_log_payload(payload)
    runtime = debug['runtime_code_diagnostics']
    assert runtime['code_build_id'] == '2026-07-28-module-isolation-v1'
    assert runtime['all_local_modules_from_workspace'] is True
    assert runtime['modules'][0]['loaded_from_workspace'] is True
    text = str(debug)
    assert 'C:' not in text and 'alice' not in text and 'absolute_path' not in text

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

class CallableId:
    def __init__(self, value, modern=True):
        if modern: self.Value = value
        else: self.IntegerValue = value
    def __call__(self):
        raise AssertionError('property value must not be called')

class CallableCategory(Category):
    def __call__(self):
        raise AssertionError('property value must not be called')


def test_callable_clr_property_values_are_not_invoked():
    element = NativeFamilyInstance(element_id_obj=CallableId(321))
    element.Category = CallableCategory(CallableId(GENERIC_ID), 'Generic Models')
    value, prop = shadow_utils._safe_property(element, 'Id')
    assert value is element.Id and prop['direct_value_callable'] is True
    assert prop['read_method'] == 'direct_getattr' and prop['reflection_attempted'] is False
    item = _diagnose_shadow_casters([element])['items'][0]
    assert item['element_id'] == 321 and item['category_id'] == GENERIC_ID
    assert item['category_name_read_method'] == 'direct_getattr'


def test_safe_property_reflection_success_and_failure(monkeypatch):
    monkeypatch.setattr(shadow_utils, 'CLR_REFLECTION_ENABLED', True)
    class PropertyInfo:
        def GetValue(self, value, *args): return 42
    class ClrType:
        Namespace = 'Autodesk.Revit.DB'
        def GetProperty(self, name): return PropertyInfo() if name == 'Category' else None
    class Reflected:
        def __getattribute__(self, name):
            if name in ('Category', 'Name'): raise RuntimeError('direct access blocked')
            return object.__getattribute__(self, name)
        def GetType(self): return ClrType()
    value, diag = shadow_utils._safe_property(Reflected(), 'Category')
    assert value == 42 and diag['read_method'] == 'clr_reflection' and diag['reflection_succeeded']
    value, diag = shadow_utils._safe_property(Reflected(), 'Name')
    assert value is None and not diag['direct_getattr_succeeded']
    assert diag['reflection_attempted'] and not diag['reflection_succeeded'] and diag['error_type']


def test_invalid_native_candidate_continues_to_internal_element(monkeypatch):
    invalid = NativeFamilyInstance(); invalid.IsValidObject = False
    valid = NativeFamilyInstance(); valid.IsValidObject = True
    wrapper = MisleadingWrapper(native=valid)
    monkeypatch.setattr(builtins, 'UnwrapElement', lambda value: invalid, raising=False)
    result, diag = shadow_utils._try_unwrap_with_diagnostics(wrapper)
    assert result is valid and diag['unwrap_strategy'] == 'InternalElement'
    assert diag['candidate_probes'][1]['is_valid_object_status'] == 'false'


def test_symbol_and_type_element_category_fallback(monkeypatch):
    direct = NativeFamilyInstance(); direct.Symbol = object()
    category, diag = shadow_utils._read_element_category(direct)
    assert category is direct.Category and diag['category_source'] == 'element.Category'
    symbol_category = Category(IdLegacy(GENERIC_ID), 'Generic Models')
    class SymbolElement:
        Category = None
        Symbol = type('Symbol', (), {'Category': symbol_category})()
    category, diag = shadow_utils._read_element_category(SymbolElement())
    assert category is symbol_category and diag['category_source'] == 'element.Symbol.Category'
    type_category = Category(IdLegacy(GENERIC_ID), 'Generic Models')
    class TypeFallback:
        Category = None
        Symbol = None
        def GetTypeId(self): return IdLegacy(7)
    monkeypatch.setattr(shadow_utils, '_try_document_get_element', lambda value: type('T', (), {'Category': type_category})())
    category, diag = shadow_utils._read_element_category(TypeFallback())
    assert category is type_category and diag['category_source'] == 'type element Category'


def test_unknown_category_still_runs_read_only_geometry_probe():
    class UnknownCategoryNative(NativeFamilyInstance):
        @property
        def Category(self): raise RuntimeError('category unavailable')
        @Category.setter
        def Category(self, value): pass
    native = UnknownCategoryNative(geometry=[Solid(1)])
    casters = _diagnose_shadow_casters([native])
    geometry = _diagnose_shadow_caster_geometry([native], casters, {'normalized': {}}, {})
    assert casters['items'][0]['accepted'] is False
    assert casters['items'][0]['geometry_probe_attempted'] is True
    assert geometry['items'][0]['geometry_probe_attempted'] is True


def test_settings_string_summary_is_not_unwrapped():
    summary = shadow_inputs._summarize_input('{"profile":"standard_8_16"}')
    assert summary['sample_type'] == 'str'
    assert summary['sample'][0]['type'] == 'str'
    assert summary['sample'][0]['value'] is not None


def test_unusable_unwrapped_native_is_reacquired_from_wrapper_id(monkeypatch):
    class UnreadableNative:
        __module__ = 'Autodesk.Revit.DB'
        IsValidObject = True
        @property
        def Id(self): raise RuntimeError('Id unavailable')
        @property
        def Category(self): raise RuntimeError('Category unavailable')
        @property
        def Symbol(self): raise RuntimeError('Symbol unavailable')
        def get_Geometry(self, options): return []
    good = NativeFamilyInstance()
    wrapper = MisleadingWrapper(internal_id=Id2024(101))
    monkeypatch.setattr(builtins, 'UnwrapElement', lambda value: UnreadableNative(), raising=False)
    monkeypatch.setattr(shadow_utils, '_try_document_get_element', lambda value: good)
    result, diag = shadow_utils._try_unwrap_with_diagnostics(wrapper)
    assert result is good
    assert diag['document_reacquire_succeeded'] is True
    assert diag['document_reacquire_strategy'] == 'wrapper.InternalElementId'
    unwrap_probe = next(p for p in diag['candidate_probes'] if p['strategy'] == 'UnwrapElement')
    assert unwrap_probe['candidate_usable'] is False
