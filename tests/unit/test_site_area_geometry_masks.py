import importlib

from shadow_site_geometry import build_site_boundary_geometry
from shadow_site_masks import build_measurement_masks
from shadow_duration import build_shadow_duration


def extraction_rect():
    pts=[(0,0,0),(20,0,0),(20,20,0),(0,20,0)]
    segs=[]
    for i,a in enumerate(pts):
        b=pts[(i+1)%len(pts)]
        segs.append({"curve_type":"Line","segment_index":i,"start":{"x_m":a[0],"y_m":a[1],"z_m":a[2]},"end":{"x_m":b[0],"y_m":b[1],"z_m":b[2]}})
    return {"complete":True,"loops":[{"segment_count":4,"segments":segs}],"maximum_z_difference_m":0.0,"blockers":[],"warnings":[]}


def test_adapter_import_without_revit():
    assert importlib.import_module("shadow_site_area_adapter")


def test_rectangle_normalized_ccw_start_area():
    g=build_site_boundary_geometry(extraction_rect())
    assert g["complete"] is True
    assert g["outer_loop"][0] == {"x_m":0.0,"y_m":0.0}
    assert g["vertex_count"] == 4
    assert g["orientation"] == "counter_clockwise"
    assert g["area_m2"] == 400.0


def test_clockwise_reversed_to_ccw():
    e=extraction_rect(); e["loops"][0]["segments"]=list(reversed([{"curve_type":"Line","segment_index":i,"start":s["end"],"end":s["start"]} for i,s in enumerate(e["loops"][0]["segments"])]))
    assert build_site_boundary_geometry(e)["orientation"] == "counter_clockwise"


def test_unsupported_curve_propagated():
    e=extraction_rect(); e["loops"][0]["segments"][1]["curve_type"]="Arc"
    r=build_site_boundary_geometry(e)
    assert r["complete"] is False
    assert r["blockers"][0]["failure_code"] == "unsupported_site_boundary_curve_type"


def test_disconnected_and_nonplanar_blockers():
    e=extraction_rect(); e["loops"][0]["segments"][1]["start"]["x_m"] += 1
    assert build_site_boundary_geometry(e)["blockers"][0]["failure_code"] == "site_boundary_disconnected_segments"
    e=extraction_rect(); e["maximum_z_difference_m"] = 0.01
    assert build_site_boundary_geometry(e)["blockers"][0]["failure_code"] == "site_boundary_area_nonplanar"


def test_masks_distance_thresholds_and_tie_break():
    g=build_site_boundary_geometry(extraction_rect())
    dur={"complete":True,"boundary_evaluation_coverage_complete":True,"duration_grid":[
        {"x_m":10,"y_m":10,"shadow_duration_minutes":1},
        {"x_m":0,"y_m":10,"shadow_duration_minutes":2},
        {"x_m":-4.99,"y_m":10,"shadow_duration_minutes":3},
        {"x_m":-5.0,"y_m":10,"shadow_duration_minutes":4},
        {"x_m":-5.01,"y_m":10,"shadow_duration_minutes":5},
        {"x_m":-10.0,"y_m":10,"shadow_duration_minutes":6},
        {"x_m":-10.01,"y_m":10,"shadow_duration_minutes":7},
        {"x_m":30.01,"y_m":10,"shadow_duration_minutes":7},
    ]}
    m=build_measurement_masks(dur,g)
    assert m["complete"] is True
    assert m["zone_counts"]["inside_site"] == 1
    assert m["zone_counts"]["on_site_boundary"] == 1
    assert m["zone_counts"]["outside_0_to_5m"] == 2
    assert m["zone_counts"]["near_5_to_10m"] == 2
    assert m["zone_counts"]["far_over_10m"] == 2
    assert m["near"]["maximum_shadow_duration_minutes"] == 6
    assert m["far"]["point"]["x_m"] == -10.01
    assert "points" not in m


def test_duration_includes_site_bounds_metadata():
    slices={"complete":True,"slices":[{"complete":True,"true_solar_time":"08:00","polygons":[{"role":"outer","points_m":[{"x":100,"y":100},{"x":101,"y":100},{"x":100,"y":101}]}]},{"complete":True,"true_solar_time":"08:30","polygons":[{"role":"outer","points_m":[{"x":100,"y":100},{"x":101,"y":100},{"x":100,"y":101}]}]}]}
    settings={"normalized":{"grid_resolution_m":10,"analysis_margin_m":0,"max_duration_grid_points":10000}}
    d=build_shadow_duration(slices, settings, site_boundary_geometry=build_site_boundary_geometry(extraction_rect()))
    assert d["site_boundary_bounds_included"] is True
    assert "site_boundary_area_expanded_10m" in d["bounds_sources"]
    assert d["bounds_m"]["min_x"] <= -10

import math
import shadow_site_area_adapter as adapter
from shadow_readiness import _build_pipeline_readiness

class Id:
    def __init__(self, v): self.IntegerValue = v
class Category:
    def __init__(self, v=None): self.Id = Id(v if v is not None else 999)
class XYZ:
    def __init__(self, x, y, z=0): self.X=x; self.Y=y; self.Z=z
class FakeLine:
    def __init__(self, a, b): self.a=XYZ(*a); self.b=XYZ(*b)
    def GetEndPoint(self, i): return self.a if i == 0 else self.b
class FakeArc(FakeLine): pass
class BoundarySegment:
    def __init__(self, curve): self.curve=curve
    def GetCurve(self): return self.curve
class FakeArea:
    __module__ = "Autodesk.Revit.DB"
    def __init__(self, area=100, loops=None):
        self.Id=Id(1); self.Category=Category(-2003200); self.Area=area; self.LevelId=Id(2); self._loops=loops
    def GetBoundarySegments(self, options): return self._loops
class FakeRoom(FakeArea): pass
class FakeSpace(FakeArea): pass
class AreaTag: pass
class AreaLoad: pass
class FilledRegion: pass
class Wrapper:
    def __init__(self, element): self.InternalElement = element

def area_loop(curve_cls=FakeLine, pts=((0,0,0),(10,0,0),(10,10,0),(0,10,0))):
    return [[BoundarySegment(curve_cls(pts[i], pts[(i+1)%len(pts)])) for i in range(len(pts))]]

def setup_adapter(monkeypatch):
    monkeypatch.setattr(adapter, "Area", FakeArea)
    monkeypatch.setattr(adapter, "Room", FakeRoom)
    monkeypatch.setattr(adapter, "Space", FakeSpace)
    monkeypatch.setattr(adapter, "Line", FakeLine)
    monkeypatch.setattr(adapter, "SpatialElementBoundaryOptions", lambda: object())

def test_adapter_accepts_db_area_and_contract_namespace(monkeypatch):
    setup_adapter(monkeypatch)
    assert "Autodesk.Revit.DB.Architecture import Area" not in open("shadow_site_area_adapter.py", encoding="utf-8").read()
    r=adapter.extract_site_boundary_area(FakeArea(100, area_loop()))
    assert r["complete"] is True
    assert r["loop_count"] == 1
    assert r["loops"][0]["segment_count"] == 4
    assert abs(r["loops"][0]["segments"][0]["end"]["x_m"] - 3.048) < 1e-9
    assert r["maximum_z_difference_m"] == 0.0

def test_adapter_rejects_non_area_types(monkeypatch):
    setup_adapter(monkeypatch)
    for item in [FakeRoom(100, area_loop()), FakeSpace(100, area_loop()), AreaTag(), AreaLoad(), FilledRegion(), object()]:
        r=adapter.extract_site_boundary_area(item)
        assert r["complete"] is False
        assert r["blockers"][0]["failure_code"] == "site_boundary_input_is_not_area"

def test_adapter_wrapper_nested_multiple_and_area_value(monkeypatch):
    setup_adapter(monkeypatch)
    assert adapter.extract_site_boundary_area(Wrapper(FakeArea(100, area_loop())))["complete"] is True
    assert adapter.extract_site_boundary_area([[FakeArea(100, area_loop())]])["complete"] is True
    assert adapter.extract_site_boundary_area([FakeArea(100, area_loop()), FakeArea(100, area_loop())])["blockers"][0]["failure_code"] == "multiple_site_boundary_areas_not_supported"
    for value in [0, -1, float("nan")]:
        assert adapter.extract_site_boundary_area(FakeArea(value, area_loop()))["blockers"][0]["failure_code"] == "site_boundary_area_unplaced_or_unbounded"

def test_adapter_boundary_failures(monkeypatch):
    setup_adapter(monkeypatch)
    class NoBoundary(FakeArea):
        GetBoundarySegments = None
    assert adapter.extract_site_boundary_area(NoBoundary(100, area_loop()))["blockers"][0]["failure_code"] == "site_boundary_area_boundary_missing"
    class Raises(FakeArea):
        def GetBoundarySegments(self, options): raise RuntimeError("private model path")
    assert adapter.extract_site_boundary_area(Raises(100, area_loop()))["blockers"][0]["failure_code"] == "site_boundary_area_boundary_api_failure"
    assert adapter.extract_site_boundary_area(FakeArea(100, []))["blockers"][0]["failure_code"] == "site_boundary_area_boundary_missing"
    assert adapter.extract_site_boundary_area(FakeArea(100, [[], []]))["blockers"][0]["failure_code"] == "site_boundary_area_multiple_loops_unsupported"
    assert adapter.extract_site_boundary_area(FakeArea(100, [[]]))["blockers"][0]["failure_code"] == "site_boundary_area_boundary_missing"
    assert adapter.extract_site_boundary_area(FakeArea(100, area_loop(FakeArc)))["blockers"][0]["failure_code"] == "unsupported_site_boundary_curve_type"

def test_adapter_rejects_invalid_endpoint_and_no_raw_objects(monkeypatch):
    setup_adapter(monkeypatch)
    r=adapter.extract_site_boundary_area(FakeArea(100, area_loop(FakeLine, ((0,0,0),(math.nan,0,0),(1,1,0),(0,1,0)))))
    assert r["blockers"][0]["failure_code"] == "site_boundary_area_boundary_missing"
    good=adapter.extract_site_boundary_area(FakeArea(100, area_loop()))
    assert "FakeLine" not in str(good) and "BoundarySegment" not in str(good)

def test_geometry_l_shape_and_more_blockers():
    pts=[(0,0,0),(4,0,0),(4,2,0),(2,2,0),(2,4,0),(0,4,0)]
    assert build_site_boundary_geometry(extraction_from_points(pts))["complete"] is True
    e=extraction_from_points(pts); e["loops"][0]["segments"][1]["start"]["x_m"] += 0.001
    assert build_site_boundary_geometry(e)["complete"] is True
    cases=[]
    e=extraction_rect(); e["loops"][0]["segments"][-1]["end"]["x_m"] = 1; cases.append((e,"site_boundary_open_loop"))
    e=extraction_rect(); e["loops"][0]["segments"][0]["end"] = dict(e["loops"][0]["segments"][0]["start"]); cases.append((e,"site_boundary_zero_length_segment"))
    e=extraction_rect(); e["loops"][0]["segments"][0]["end"]["x_m"] = 0.001; cases.append((e,"site_boundary_short_segment"))
    e=extraction_rect(); e["loops"][0]["segments"][1] = {"curve_type":"Line","start":e["loops"][0]["segments"][0]["end"],"end":e["loops"][0]["segments"][0]["start"]}; cases.append((e,"site_boundary_duplicate_segment"))
    e=extraction_from_points([(0,0,0),(4,0,0),(4,4,0),(1,1,0),(0,4,0),(-1,1,0),(1,1,0)]); cases.append((e,"site_boundary_repeated_vertex"))
    e=extraction_from_points([(0,0,0),(2,2,0),(0,2,0),(2,0,0)]); cases.append((e,"site_boundary_self_intersection"))
    e=extraction_from_points([(0,0,0),(1,0,0),(2,0,0)]); cases.append((e,"site_boundary_zero_area"))
    e=extraction_rect(); del e["loops"][0]["segments"][0]["start"]["x_m"]; cases.append((e,"invalid_site_boundary_segment_coordinates"))
    e=extraction_rect(); e["loops"][0]["segments"][0]["start"]["x_m"] = math.nan; cases.append((e,"invalid_site_boundary_segment_coordinates"))
    e=extraction_rect(); e["loops"][0]["segments"][0]["start"]["x_m"] = math.inf; cases.append((e,"invalid_site_boundary_segment_coordinates"))
    e=extraction_rect(); e["loops"].append(e["loops"][0]); cases.append((e,"site_boundary_area_multiple_loops_unsupported"))
    for extraction, code in cases:
        assert build_site_boundary_geometry(extraction)["blockers"][0]["failure_code"] == code
    assert build_site_boundary_geometry(extraction_rect(), join_tolerance_m=0)["blockers"][0]["failure_code"] == "invalid_site_boundary_geometry_tolerance"

def extraction_from_points(pts):
    segs=[]
    for i,a in enumerate(pts):
        b=pts[(i+1)%len(pts)]
        segs.append({"curve_type":"Line","segment_index":i,"start":{"x_m":a[0],"y_m":a[1],"z_m":a[2]},"end":{"x_m":b[0],"y_m":b[1],"z_m":b[2]}})
    return {"complete":True,"loops":[{"segment_count":len(segs),"segments":segs}],"maximum_z_difference_m":0.0,"blockers":[],"warnings":[]}

def test_masks_l_shape_distances_invalid_empty_and_nan():
    g=build_site_boundary_geometry(extraction_from_points([(0,0,0),(4,0,0),(4,2,0),(2,2,0),(2,4,0),(0,4,0)]))
    dur={"complete":True,"boundary_evaluation_coverage_complete":True,"duration_grid":[
        {"x_m":1,"y_m":1,"shadow_duration_minutes":1},
        {"x_m":3,"y_m":3,"shadow_duration_minutes":2},
        {"x_m":5,"y_m":3,"shadow_duration_minutes":3},
        {"x_m":5,"y_m":5,"shadow_duration_minutes":3},
    ]}
    m=build_measurement_masks(dur,g)
    assert m["zone_counts"]["inside_site"] == 1
    assert m["zone_counts"]["outside_0_to_5m"] == 3
    assert build_measurement_masks({"complete":True,"boundary_evaluation_coverage_complete":True,"duration_grid":[]}, g)["blockers"][0]["failure_code"] == "shadow_duration_grid_missing"
    bad={"complete":True,"boundary_evaluation_coverage_complete":True,"duration_grid":[{"x_m":math.nan,"y_m":0,"shadow_duration_minutes":0}]}
    assert build_measurement_masks(bad,g)["blockers"][0]["failure_code"] == "invalid_shadow_duration_grid_point"
    assert build_measurement_masks(dur,g,distance_tolerance_m=-1)["blockers"][0]["failure_code"] == "invalid_measurement_mask_distance_tolerance"

def test_readiness_valid_area_no_legacy_boundary_blocker():
    r=_build_pipeline_readiness({}, {}, {}, shadow_duration={"complete":True,"boundary_evaluation_coverage_complete":True}, equal_time_contours={"complete":True}, site_boundary_area_extraction={"complete":True,"blockers":[]}, site_boundary_geometry={"complete":True,"blockers":[]}, measurement_masks={"complete":True,"blockers":[]})
    assert r["site_boundary_area_ready"] is True
    assert r["site_boundary_geometry_ready"] is True
    assert r["site_boundary_ready_for_boundary_dependent_steps"] is True
    assert r["measurement_masks_ready"] is True
    assert r["boundary_dependent_steps_ready"] is True
    assert r["blockers_for_boundary_dependent_steps"] == []
    assert "site_boundary is missing" not in str(r)
    assert r["blockers_for_legal_judgement"] == [{"failure_code":"ordinance_applicability_not_certified"}, {"failure_code":"local_ordinance_reference_missing"}, {"failure_code":"legal_profile_schema_not_implemented"}]
    assert r["legal_judgement_ready"] is False

def test_duration_boundary_grid_blocker_keeps_core_complete():
    slices={"complete":True,"slices":[{"complete":True,"true_solar_time":"08:00","polygons":[{"role":"outer","points_m":[{"x":100,"y":100},{"x":101,"y":100},{"x":100,"y":101}]}]},{"complete":True,"true_solar_time":"08:30","polygons":[{"role":"outer","points_m":[{"x":100,"y":100},{"x":101,"y":100},{"x":100,"y":101}]}]}]}
    settings={"normalized":{"grid_resolution_m":1,"analysis_margin_m":0,"max_duration_grid_points":10}}
    d=build_shadow_duration(slices, settings, site_boundary_geometry=build_site_boundary_geometry(extraction_rect()))
    assert d["complete"] is True
    assert d["blockers"] == []
    assert d["site_boundary_bounds_included"] is False
    assert d["boundary_evaluation_coverage_complete"] is False
    assert d["boundary_evaluation_blockers"][0]["failure_code"] == "site_boundary_evaluation_grid_points_exceeded"
    assert d["boundary_evaluation_blockers"][0]["automatic_accuracy_fallback_used"] is False
    assert d["core_bounds_preflight"]["within_point_limit"] is True
    assert d["boundary_bounds_preflight"]["within_point_limit"] is False
    assert build_measurement_masks(d, build_site_boundary_geometry(extraction_rect()))["complete"] is False

def test_core_grid_blocker_still_blocks_duration():
    slices={"complete":True,"slices":[{"complete":True,"true_solar_time":"08:00","polygons":[{"role":"outer","points_m":[{"x":0,"y":0},{"x":100,"y":0},{"x":0,"y":100}]}]},{"complete":True,"true_solar_time":"08:30","polygons":[{"role":"outer","points_m":[{"x":0,"y":0},{"x":100,"y":0},{"x":0,"y":100}]}]}]}
    settings={"normalized":{"grid_resolution_m":1,"analysis_margin_m":0,"max_duration_grid_points":10}}
    d=build_shadow_duration(slices, settings)
    assert d["complete"] is False
    assert d["blockers"][0]["failure_code"] == "max_duration_grid_points_exceeded"
    assert d["core_bounds_preflight"]["within_point_limit"] is False

def shadow_slices_near_origin():
    return {"complete": True, "slices": [
        {"complete": True, "true_solar_time": "08:00", "polygons": [{"role": "outer", "points_m": [{"x": 0, "y": 0}, {"x": 1, "y": 0}, {"x": 0, "y": 1}]}]},
        {"complete": True, "true_solar_time": "08:30", "polygons": [{"role": "outer", "points_m": [{"x": 0, "y": 0}, {"x": 1, "y": 0}, {"x": 0, "y": 1}]}]},
    ]}

def test_small_area_uses_boundary_bounds_and_masks_complete():
    d=build_shadow_duration(shadow_slices_near_origin(), {"normalized":{"grid_resolution_m":10,"analysis_margin_m":0,"max_duration_grid_points":1000}}, site_boundary_geometry=build_site_boundary_geometry(extraction_rect()))
    assert d["complete"] is True
    assert d["site_boundary_bounds_included"] is True
    assert d["boundary_evaluation_coverage_complete"] is True
    assert build_measurement_masks(d, build_site_boundary_geometry(extraction_rect()))["complete"] is True

def test_far_away_area_boundary_over_limit_core_success():
    far=build_site_boundary_geometry(extraction_from_points([(1000,1000,0),(1020,1000,0),(1020,1020,0),(1000,1020,0)]))
    d=build_shadow_duration(shadow_slices_near_origin(), {"normalized":{"grid_resolution_m":1,"analysis_margin_m":0,"max_duration_grid_points":100}}, site_boundary_geometry=far)
    assert d["complete"] is True
    assert d["core_bounds_preflight"]["within_point_limit"] is True
    assert d["boundary_bounds_preflight"]["within_point_limit"] is False
    assert d["boundary_evaluation_coverage_complete"] is False
