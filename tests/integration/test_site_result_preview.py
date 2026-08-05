import json
import math
import types

import shadow_contour_preview
import shadow_preview
import shadow_site_result_preview as preview
from shadow_site_masks import build_measurement_masks


def contour(distance=5.0, points=((0, 0), (1, 0), (1, 1)), closed=True):
    return {"distance_m": distance, "closed": closed,
            "points_m": [{"x": x, "y": y} for x, y in points]}


def distance_source(*items):
    return {"available": True, "complete": True, "contours": list(items)}


def masks():
    return {"available": True, "complete": True,
        "near": {"available": True, "point": {"x_m": 2.0, "y_m": 3.0, "distance_from_site_boundary_m": 7.0}, "maximum_shadow_duration_minutes": 225.0},
        "far": {"available": True, "point": {"x_m": 5.0, "y_m": 7.0, "distance_from_site_boundary_m": 12.0}, "maximum_shadow_duration_minutes": 180.0}}


class XYZ:
    def __init__(self, x, y, z): self.X, self.Y, self.Z = x, y, z
    def DistanceTo(self, other): return math.dist((self.X, self.Y, self.Z), (other.X, other.Y, other.Z))


class Line:
    @staticmethod
    def CreateBound(a, b): return types.SimpleNamespace(start=a, end=b)


class Id:
    def __init__(self, value): self.IntegerValue = value


class Shape:
    def __init__(self, value, app=""):
        self.Id, self.ApplicationId, self.calls = Id(value), app, []
    def SetShape(self, curves): self.calls.append(curves)
    def GetType(self): return types.SimpleNamespace(FullName="Autodesk.Revit.DB.DirectShape")


class Direct:
    @staticmethod
    def CreateElement(doc, category):
        shape = Shape(doc.next_id); doc.next_id += 1; doc.shapes.append(shape); return shape


class Collector:
    def __init__(self, doc): self.doc = doc
    def OfClass(self, cls): return self
    def OfCategory(self, category): return self
    def WhereElementIsNotElementType(self): return self
    def ToElements(self): return list(self.doc.shapes)


class Sub:
    def __init__(self, doc): self.doc = doc
    def Start(self): self.snapshot = list(self.doc.shapes)
    def Commit(self): pass
    def RollBack(self): self.doc.shapes = list(self.snapshot)


class TM:
    def EnsureInTransaction(self, doc): pass
    def TransactionTaskDone(self): pass


class Doc:
    def __init__(self):
        self.shapes = [Shape(1, preview.APPLICATION_ID), Shape(2, "Dynamo_Shadow.EqualTimeContourPreview"), Shape(3, shadow_preview.APPLICATION_ID), Shape(4, "Other")]
        self.next_id = 5
        self.Application = types.SimpleNamespace(ShortCurveTolerance=0)
        self.ActiveView = types.SimpleNamespace(SetElementOverrides=lambda *args: None)
    def Delete(self, ident):
        self.shapes = [shape for shape in self.shapes if shape.Id.IntegerValue != ident.IntegerValue]


def install(monkeypatch, doc):
    monkeypatch.setattr(preview, "XYZ", XYZ); monkeypatch.setattr(preview, "Line", Line)
    monkeypatch.setattr(shadow_contour_preview, "XYZ", XYZ); monkeypatch.setattr(shadow_contour_preview, "Line", Line)
    monkeypatch.setattr(preview, "DirectShape", Direct); monkeypatch.setattr(preview, "FilteredElementCollector", Collector)
    monkeypatch.setattr(shadow_preview, "FilteredElementCollector", Collector); monkeypatch.setattr(shadow_preview, "DirectShape", Direct)
    monkeypatch.setattr(preview, "BuiltInCategory", types.SimpleNamespace(OST_GenericModel=1)); monkeypatch.setattr(preview, "ElementId", lambda value: value)
    monkeypatch.setattr(preview, "SubTransaction", Sub); monkeypatch.setattr(preview, "OverrideGraphicSettings", None)
    monkeypatch.setattr(preview, "DocumentManager", types.SimpleNamespace(Instance=types.SimpleNamespace(CurrentDBDocument=doc)))
    monkeypatch.setattr(preview, "TransactionManager", types.SimpleNamespace(Instance=TM()))


def test_off_does_not_access_revit(monkeypatch):
    monkeypatch.setattr(preview, "DocumentManager", None)
    result = preview.build_site_result_preview(distance_source(contour()), masks(), {}, {"elevation_m": 4}, {})
    assert result["mode"] == "off" and result["attempted"] is False


def test_clear_deletes_only_own_preview_without_sources_or_plane(monkeypatch):
    doc = Doc(); install(monkeypatch, doc)
    result = preview.build_site_result_preview(None, None, None, None, {"equal_time_contour_preview_mode": "clear"})
    assert result["complete"] and result["deleted_element_count"] == 1
    assert {shape.ApplicationId for shape in doc.shapes} == {"Dynamo_Shadow.EqualTimeContourPreview", shadow_preview.APPLICATION_ID, "Other"}


def test_replace_creates_two_distance_groups_and_two_markers(monkeypatch):
    doc = Doc(); install(monkeypatch, doc)
    comparison = {"complete": True, "near": {"status": "within_selected_limit", "selected_limit_minutes": 240.0, "excess_minutes": 0.0}}
    result = preview.build_site_result_preview(distance_source(contour(5), contour(5, points=((2,2),(3,2))), contour(10)), masks(), comparison, {"elevation_m": 4}, {"equal_time_contour_preview_mode": "replace"})
    assert result["complete"] and result["created_group_count"] == 4 and result["deleted_element_count"] == 1
    owned = [s for s in doc.shapes if s.ApplicationId == preview.APPLICATION_ID]
    assert [s.Name for s in owned] == ["Dynamo_Shadow_SiteDistance_05m", "Dynamo_Shadow_SiteDistance_10m", "Dynamo_Shadow_MaxPoint_Near", "Dynamo_Shadow_MaxPoint_Far"]
    assert owned[0].ApplicationDataId == "output_kind=site_distance_contour;distance_m=5"
    near = next(g for g in result["groups"] if g.get("zone") == "near_5_to_10m")
    assert near["selected_limit_status"] == "within_selected_limit" and near["curve_count"] == 2


def test_replace_requires_measurement_plane_and_sources_before_cleanup(monkeypatch):
    doc = Doc(); install(monkeypatch, doc)
    result = preview.build_site_result_preview(distance_source(contour()), masks(), {}, {}, {"equal_time_contour_preview_mode": "replace"})
    assert result["blockers"][0]["failure_code"] == "site_result_preview_measurement_plane_missing"
    assert len(doc.shapes) == 4
    result = preview.build_site_result_preview({}, {}, {}, {"elevation_m": 4}, {"equal_time_contour_preview_mode": "replace"})
    assert result["blockers"][0]["failure_code"] == "site_result_preview_sources_unavailable"



def test_point_xy_requires_formal_x_m_y_m_contract():
    assert preview._point_xy({"x_m": 2.0, "y_m": 3.0}) == (2.0, 3.0)
    try:
        preview._point_xy({"x": 2.0, "y": 3.0})
    except ValueError as exc:
        assert str(exc) == "site_result_preview_non_finite_coordinate"
    else:
        raise AssertionError("x/y-only point must not be accepted as the formal marker contract")


def test_build_measurement_masks_output_feeds_marker_preview_directly(monkeypatch):
    doc = Doc(); install(monkeypatch, doc)
    shadow_duration = {"complete": True, "boundary_evaluation_coverage_complete": True,
        "duration_grid": [
            {"x_m": -7.0, "y_m": 5.0, "shadow_duration_minutes": 210.0},
            {"x_m": -12.0, "y_m": 5.0, "shadow_duration_minutes": 180.0},
        ]}
    site_boundary_geometry = {"complete": True, "outer_loop": [
        {"x_m": 0.0, "y_m": 0.0}, {"x_m": 10.0, "y_m": 0.0},
        {"x_m": 10.0, "y_m": 10.0}, {"x_m": 0.0, "y_m": 10.0},
    ]}
    production_masks = build_measurement_masks(shadow_duration, site_boundary_geometry)
    assert production_masks["near"]["point"] == {"x_m": -7.0, "y_m": 5.0, "distance_from_site_boundary_m": 7.0}
    result = preview.build_site_result_preview(None, production_masks, {}, {"elevation_m": 4}, {"equal_time_contour_preview_mode": "replace"})
    assert result["complete"] is False and result["partial_success"] is True
    assert [group.get("zone") for group in result["groups"]] == ["near_5_to_10m", "far_over_10m"]
    assert result["created_group_count"] == 2


def test_partial_source_semantics_for_distance_only(monkeypatch):
    doc = Doc(); install(monkeypatch, doc)
    result = preview.build_site_result_preview(distance_source(contour(5), contour(10)), None, {}, {"elevation_m": 4}, {"equal_time_contour_preview_mode": "replace"})
    assert result["created_group_count"] == 2
    assert result["complete"] is False and result["partial_success"] is True
    assert any("Measurement mask" in warning for warning in result["warnings"])


def test_missing_far_marker_is_partial_success(monkeypatch):
    doc = Doc(); install(monkeypatch, doc)
    partial_masks = masks(); partial_masks["far"] = {"available": False}
    result = preview.build_site_result_preview(distance_source(contour(5), contour(10)), partial_masks, {}, {"elevation_m": 4}, {"equal_time_contour_preview_mode": "replace"})
    assert result["created_group_count"] == 3
    assert result["complete"] is False and result["partial_success"] is True
    assert any("far_over_10m" in warning for warning in result["warnings"])

def test_debug_summary_omits_coordinates():
    import shadow_debug
    payload = {"site_result_preview": {"enabled": True, "mode": "replace", "attempted": True, "complete": True,
        "groups": [{"output_kind": "maximum_shadow_duration_marker", "zone": "near_5_to_10m", "created": True, "point": {"x_m": 1, "y_m": 2}, "curves": [1]}]}}
    summary = shadow_debug._summarize_out_for_debug(payload)
    assert "point" not in json.dumps(summary["site_result_preview"])
    assert "curves" not in json.dumps(summary["site_result_preview"])
