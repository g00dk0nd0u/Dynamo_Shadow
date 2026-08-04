import json
import math
import types

import pytest

import shadow_contour_preview as preview
import shadow_debug
import shadow_preview


def contour(level=60, points=((0, 0), (2, 0), (2, 1)), closed=True):
    return {"level_minutes": level, "closed": closed,
            "points_m": [{"x": x, "y": y} for x, y in points]}


def source(*contours):
    return {"available": True, "complete": True, "contours": list(contours)}


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
    def SetShape(self, *args): self.calls.append(args)
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
        self.shapes = [Shape(1, preview.APPLICATION_ID),
                       Shape(2, shadow_preview.APPLICATION_ID)]
        self.next_id = 3
        self.Application = types.SimpleNamespace(ShortCurveTolerance=0)
        self.ActiveView = types.SimpleNamespace(SetElementOverrides=lambda *args: None)
    def Delete(self, ident):
        self.shapes = [shape for shape in self.shapes if shape.Id.IntegerValue != ident.IntegerValue]


def install(monkeypatch, doc):
    monkeypatch.setattr(preview, "XYZ", XYZ); monkeypatch.setattr(preview, "Line", Line)
    monkeypatch.setattr(preview, "DirectShape", Direct); monkeypatch.setattr(preview, "FilteredElementCollector", Collector)
    monkeypatch.setattr(shadow_preview, "FilteredElementCollector", Collector)
    monkeypatch.setattr(shadow_preview, "DirectShape", Direct)
    monkeypatch.setattr(preview, "BuiltInCategory", types.SimpleNamespace(OST_GenericModel=1))
    monkeypatch.setattr(preview, "ElementId", lambda value: value)
    monkeypatch.setattr(preview, "SubTransaction", Sub)
    monkeypatch.setattr(preview, "OverrideGraphicSettings", None)
    monkeypatch.setattr(preview, "DocumentManager", types.SimpleNamespace(Instance=types.SimpleNamespace(CurrentDBDocument=doc)))
    monkeypatch.setattr(preview, "TransactionManager", types.SimpleNamespace(Instance=TM()))


def test_off_does_not_access_revit(monkeypatch):
    monkeypatch.setattr(preview, "DocumentManager", None)
    result = preview.build_equal_time_contour_preview(source(contour()), {"elevation_m": 4}, {})
    assert result["mode"] == "off" and result["attempted"] is False


def test_incomplete_source_and_missing_plane_block_before_revit():
    assert preview.build_equal_time_contour_preview(
        {"complete": False}, {"elevation_m": 4}, {"equal_time_contour_preview_mode": "replace"})["blockers"][0]["failure_code"] == "contour_preview_source_incomplete"
    assert preview.build_equal_time_contour_preview(
        source(contour()), {}, {"equal_time_contour_preview_mode": "replace"})["blockers"][0]["failure_code"] == "contour_preview_measurement_plane_missing"


def test_closed_segments_include_closure_and_skip_zero_length():
    segments = preview._segments([contour(points=((0, 0), (1, 0), (1, 0), (1, 1)))])
    assert len(segments) == 3
    assert segments[-1] == ((1.0, 1.0), (0.0, 0.0))


def test_non_finite_coordinate_blocks():
    result = preview.build_equal_time_contour_preview(
        source(contour(points=((0, 0), (float("nan"), 1)))), {"elevation_m": 4},
        {"equal_time_contour_preview_mode": "replace"})
    assert result["blockers"][0]["failure_code"] == "contour_preview_non_finite_coordinate"


def test_replace_deletes_only_contour_preview_and_names_per_level(monkeypatch):
    doc = Doc(); install(monkeypatch, doc)
    result = preview.build_equal_time_contour_preview(
        source(contour(120), contour(60)), {"elevation_m": 4},
        {"equal_time_contour_preview_mode": "replace"})
    owned = [shape for shape in doc.shapes if shape.ApplicationId == preview.APPLICATION_ID]
    assert result["complete"] and result["deleted_element_count"] == 1
    assert [shape.Name for shape in owned] == ["Dynamo_Shadow_EqualTime_0060min", "Dynamo_Shadow_EqualTime_0120min"]
    assert any(shape.ApplicationId == shadow_preview.APPLICATION_ID for shape in doc.shapes)


def test_clear_deletes_only_without_source_or_plane(monkeypatch):
    doc = Doc(); install(monkeypatch, doc)
    result = preview.build_equal_time_contour_preview(None, None,
        {"equal_time_contour_preview_mode": "clear"})
    assert result["complete"] and result["deleted_element_count"] == 1
    assert len(doc.shapes) == 1 and doc.shapes[0].ApplicationId == shadow_preview.APPLICATION_ID


def test_debug_summary_omits_coordinates_and_uses_readiness_pending():
    payload = {"equal_time_contour_preview": {"mode": "replace", "complete": True,
        "created_element_count": 1, "deleted_element_count": 1,
        "groups": [{"level_minutes": 60, "contour_count": 1, "curve_count": 4,
                    "points_m": [{"x": 99, "y": 99}]}], "warnings": [], "blockers": []},
        "pipeline_readiness": {"next_implementation_steps": ["site boundary"]},
        "planned_pipeline": ["equal-time contour generation", "pipeline readiness diagnostics",
                             "formal technical solar specification v1"],
        "footprint_extraction_policy": {"not_implemented_in_this_pr": []}}
    summary = shadow_debug._summarize_out_for_debug(payload)
    assert "points_m" not in json.dumps(summary["equal_time_contour_preview"])
    assert summary["not_implemented_summary"]["planned_pipeline_pending"] == ["site boundary"]


def test_plan_validate_overload_failure_uses_addcurve_and_keeps_plan(monkeypatch):
    calls = []
    class Builder:
        def __init__(self, target): pass
        @staticmethod
        def ValidateCurve(curve, target): raise TypeError("overload")
        def AddCurve(self, curve): calls.append(curve)
        def Build(self): return calls
        def Dispose(self): pass
    class ShapeWithPlan:
        def SetShape(self, *args): calls.append(args)
    monkeypatch.setattr(shadow_preview, "ViewShapeBuilder", Builder)
    monkeypatch.setattr(shadow_preview, "DirectShapeTargetViewType", types.SimpleNamespace(Plan="Plan"))
    diag = {"warnings": []}
    shadow_preview._set_plan_curve_representation(ShapeWithPlan(), ["curve"], diag)
    assert diag["plan_representation_set"] is True and not diag["warnings"]


def test_preview_exception_contract_is_nonfatal_in_script_source():
    text = open("script.py", encoding="utf-8").read()
    assert "Contour preview failed non-fatally; equal-time contour output remains available." in text
    assert '"success": True' in text
