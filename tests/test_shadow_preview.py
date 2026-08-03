import json
import math
import types

import pytest
import shadow_preview as preview


def polygon(points, role="outer"):
    return {"generation_method": preview.GENERATION_METHOD, "closed": True,
        "point_count": len(points), "points_m": [{"x": x, "y": y} for x, y in points],
        "area_m2": 1.0, "role": role, "source_loop_index": 0,
        "source_solid_index": 0, "split_solid_index": 0}


def formal(polygons=None, time="12:00:00"):
    return {"available": True, "slices": [{"slice_index": 4, "true_solar_time": time,
        "casters": [{"caster_index": 2, "polygons": polygons or [polygon([(0,0),(2,0),(1,1),(0,2)])]}]}]}


def test_preview_defaults_off_and_invalid_settings_disable_nonfatally():
    config = preview.normalize_preview_settings({})
    assert config["mode"] == "off"
    result = preview.build_shadow_preview(formal(), {"elevation_m": 4.0}, {})
    assert result["enabled"] is result["attempted"] is False
    assert result["created_element_count"] == result["deleted_element_count"] == 0
    invalid = preview.normalize_preview_settings({"preview_mode":"write", "preview_thickness_mm":0,
        "preview_vertical_separation_mm":-1, "preview_transparency":True})
    assert invalid["valid"] is False and invalid["mode"] == "off" and invalid["warnings"]


def test_time_matching_is_exact_canonical_and_deduplicated():
    config = preview.normalize_preview_settings({"preview_mode":"replace",
        "preview_true_solar_times":["12:00", "12:00:00", "12:30"]})
    warnings = []
    groups, matched = preview._selected_groups(formal(), config["requested_true_solar_times"], warnings)
    assert config["requested_true_solar_times"] == ["12:00:00", "12:30:00"]
    assert matched == ["12:00:00"] and len(groups) == 1
    assert "nearest" in warnings[0]


class XYZ:
    BasisZ = object()
    def __init__(self, x, y, z): self.X, self.Y, self.Z = x, y, z
    def DistanceTo(self, other): return math.dist((self.X,self.Y,self.Z),(other.X,other.Y,other.Z))
class Line:
    @staticmethod
    def CreateBound(a,b): return (a,b)
class Loop:
    def __init__(self): self.lines=[]; self.disposed=False
    def Append(self,line): self.lines.append(line)
    def Dispose(self): self.disposed=True


def install_geometry(monkeypatch):
    monkeypatch.setattr(preview, "XYZ", XYZ); monkeypatch.setattr(preview, "Line", Line)
    monkeypatch.setattr(preview, "CurveLoop", Loop)


def test_curve_loop_preserves_concave_order_hole_conversion_and_z(monkeypatch):
    install_geometry(monkeypatch)
    outer = [(0,0),(2,0),(1,1),(2,2),(0,2)]
    inner = [(.2,.2),(.2,.4),(.4,.4),(.4,.2)]
    loops = preview._curve_loops([polygon(inner,"inner"), polygon(outer)], 4.0, 20.0, 0)
    assert len(loops) == 2 and [line[0].X for line in loops[0].lines] == pytest.approx([0, 6.56167979, 3.280839895, 6.56167979, 0])
    assert loops[0].lines[0][0].Z == pytest.approx(4.02 * 3.280839895013123)
    assert len(loops[0].lines) == len(outer) and loops[0].lines[-1][1] is loops[0].lines[0][0]


@pytest.mark.parametrize("change,reason", [
    ({"closed":False}, "preview_polygon_validation_failed"),
    ({"points_m":[{"x":0,"y":0},{"x":float('nan'),"y":0},{"x":0,"y":1}],"point_count":3}, "preview_non_finite_coordinate"),
])
def test_invalid_polygon_is_rejected(monkeypatch, change, reason):
    install_geometry(monkeypatch); item = polygon([(0,0),(1,0),(0,1)]); item.update(change)
    with pytest.raises(ValueError, match=reason): preview._curve_loops([item], 0, 0, 0)


def test_short_segment_is_rejected(monkeypatch):
    install_geometry(monkeypatch)
    with pytest.raises(ValueError, match="preview_short_segment"):
        preview._curve_loops([polygon([(0,0),(.001,0),(0,1)])], 0, 0, .01)


class Id:
    def __init__(self, value): self.IntegerValue=value
class Shape:
    def __init__(self, value, app=""): self.Id=Id(value); self.ApplicationId=app; self.shapes=[]
    def SetShape(self, shapes): self.shapes=shapes
    def GetType(self): return types.SimpleNamespace(FullName="Autodesk.Revit.DB.DirectShape")
class Collector:
    def __init__(self, doc): self.doc=doc; self.items=[]
    def OfClass(self, cls): self.items=self.doc.patterns if cls is FakeFill else self.doc.shapes; return self
    def OfCategory(self, category): self.items=self.doc.shapes; return self
    def WhereElementIsNotElementType(self): return self
    def ToElements(self): self.doc.events.append("collect"); return list(self.items)
    def __iter__(self): return iter(self.items)
class FakeFill: pass
class Geometry:
    calls=[]
    @classmethod
    def CreateExtrusionGeometry(cls, loops, direction, thickness):
        cls.calls.append((loops,direction,thickness)); return types.SimpleNamespace(Volume=1)
class Direct:
    @staticmethod
    def CreateElement(doc, category):
        shape=Shape(doc.next_id); doc.next_id+=1; doc.shapes.append(shape); return shape
class TM:
    def __init__(self): self.opened=0; self.closed=0
    def EnsureInTransaction(self, doc): self.opened+=1; doc.events.append("transaction")
    def TransactionTaskDone(self): self.closed+=1
class FakeSubTransaction:
    def __init__(self, doc): self.doc=doc; self.snapshot=None
    def Start(self): self.snapshot=list(self.doc.shapes); self.doc.events.append("subtransaction")
    def Commit(self): self.snapshot=None; self.doc.events.append("subtransaction_commit")
    def RollBack(self):
        self.doc.shapes=list(self.snapshot); self.snapshot=None; self.doc.events.append("subtransaction_rollback")
class Document:
    def __init__(self):
        self.shapes=[Shape(1,preview.APPLICATION_ID),Shape(2,"other")]; self.patterns=[]; self.next_id=3
        self.events=[]
        self.Application=types.SimpleNamespace(ShortCurveTolerance=0); self.ActiveView=types.SimpleNamespace(Id=Id(9),ViewType="3D")
    def Delete(self, element_id):
        self.events.append(("delete", element_id.IntegerValue))
        self.shapes=[s for s in self.shapes if s.Id.IntegerValue != element_id.IntegerValue]


def install_runtime(monkeypatch, document):
    install_geometry(monkeypatch); Geometry.calls=[]
    monkeypatch.setattr(preview,"GeometryCreationUtilities",Geometry); monkeypatch.setattr(preview,"DirectShape",Direct)
    monkeypatch.setattr(preview,"FilteredElementCollector",Collector); monkeypatch.setattr(preview,"FillPatternElement",FakeFill)
    monkeypatch.setattr(preview,"BuiltInCategory",types.SimpleNamespace(OST_GenericModel=42)); monkeypatch.setattr(preview,"ElementId",lambda x:x)
    monkeypatch.setattr(preview,"SubTransaction",FakeSubTransaction)
    tm=TM(); monkeypatch.setattr(preview,"DocumentManager",types.SimpleNamespace(Instance=types.SimpleNamespace(CurrentDBDocument=document)))
    monkeypatch.setattr(preview,"TransactionManager",types.SimpleNamespace(Instance=tm)); return tm


def test_clear_deletes_only_owned_directshape(monkeypatch):
    doc=Document(); tm=install_runtime(monkeypatch,doc)
    result=preview.build_shadow_preview(formal(),{"elevation_m":4},{"preview_mode":"clear"})
    assert result["deleted_element_count"]==1 and result["created_element_count"]==0
    assert [s.ApplicationId for s in doc.shapes]==["other"] and tm.opened==tm.closed==1
    assert doc.events[:2] == ["collect", "transaction"]
    assert doc.events[2] == ("delete", 1)


def test_replace_is_idempotent_and_serializes_no_native_objects(monkeypatch):
    doc=Document(); tm=install_runtime(monkeypatch,doc)
    settings={"preview_mode":"replace","preview_true_solar_times":["12:00"]}
    first=preview.build_shadow_preview(formal(),{"elevation_m":4},settings)
    second=preview.build_shadow_preview(formal(),{"elevation_m":4},settings)
    owned=[s for s in doc.shapes if s.ApplicationId==preview.APPLICATION_ID]
    assert first["created_element_count"]==second["created_element_count"]==len(owned)==1
    assert owned[0].ApplicationDataId=="slice=4;caster=2;solid=0" and owned[0].shapes
    assert owned[0].Name == "Dynamo_Shadow_120000_s000"
    assert Geometry.calls[-1][1] is XYZ.BasisZ and Geometry.calls[-1][2] > 0
    assert tm.opened==tm.closed==2 and json.dumps(second)


class Proxy:
    def __init__(self, value): self.Id=Id(value); self.ApplicationId=preview.APPLICATION_ID
    def GetType(self): return types.SimpleNamespace(FullName="Autodesk.Revit.DB.FamilyInstance")


def test_owned_collector_materializes_and_filters_type_and_application(monkeypatch):
    doc=Document(); doc.shapes.append(Proxy(3)); install_runtime(monkeypatch,doc)
    found=preview._collect_owned_preview_ids(doc)
    assert found["succeeded"] is True and found["collector_method"] == "of_class_direct_shape"
    assert [item.IntegerValue for item in found["element_ids"]] == [1]
    assert found["direct_shape_candidate_count"] == 2 and doc.events == ["collect"]


def test_owned_collector_uses_category_fallback_with_native_type_filter(monkeypatch):
    doc=Document(); doc.shapes.append(Proxy(3)); install_runtime(monkeypatch,doc)
    class FallbackCollector(Collector):
        def OfClass(self, cls):
            if cls is not FakeFill: raise TypeError("OfClass unsupported")
            return super().OfClass(cls)
    monkeypatch.setattr(preview,"FilteredElementCollector",FallbackCollector)
    found=preview._collect_owned_preview_ids(doc)
    assert found["succeeded"] is True and found["fallback_used"] is True
    assert [item.IntegerValue for item in found["element_ids"]] == [1]
    assert len(found["attempts"]) == 2 and found["attempts"][0]["failure_type"] == "TypeError"


def test_both_cleanup_collectors_fail_before_transaction(monkeypatch):
    doc=Document(); tm=install_runtime(monkeypatch,doc)
    class BrokenCollector(Collector):
        def OfClass(self, cls): raise RuntimeError("C:/Users/private/model.rvt")
        def OfCategory(self, category): raise ValueError("category failed")
    monkeypatch.setattr(preview,"FilteredElementCollector",BrokenCollector)
    result=preview.build_shadow_preview(formal(),{"elevation_m":4},{"preview_mode":"replace","preview_true_solar_times":["12:00"]})
    assert result["failure_stage"] == "cleanup_collection"
    assert result["sanitized_failure_message"] == "category failed"
    assert tm.opened == 0 and doc.next_id == 3 and result["created_element_count"] == 0


def test_delete_failure_is_localized_and_stops_replacement(monkeypatch):
    doc=Document(); doc.shapes.insert(1,Shape(3,preview.APPLICATION_ID)); tm=install_runtime(monkeypatch,doc)
    original_delete=doc.Delete
    def delete(element_id):
        if element_id.IntegerValue == 3: raise RuntimeError("owned delete failed")
        original_delete(element_id)
    doc.Delete=delete
    result=preview.build_shadow_preview(formal(),{"elevation_m":4},{"preview_mode":"replace","preview_true_solar_times":["12:00"]})
    assert result["requested_delete_count"] == 2
    assert result["successful_delete_count"] == 0 and result["failed_delete_count"] == 1
    assert result["failure_stage"] == "cleanup_delete" and result["created_element_count"] == 0
    assert [s.Id.IntegerValue for s in doc.shapes] == [1,3,2] and tm.opened == tm.closed == 1


def test_element_name_sanitizes_time_and_all_prohibited_characters():
    group = {"true_solar_time":"08:00:00", "split_solid_index":0}
    assert preview._preview_element_name(group) == "Dynamo_Shadow_080000_s000"
    assert preview._sanitize_element_name("bad:name\nwith\ttabs?|~") == "bad_name_with_tabs___"


def test_all_creation_failures_roll_back_and_keep_existing_preview(monkeypatch):
    doc=Document(); tm=install_runtime(monkeypatch,doc)
    class FailingDirect:
        @staticmethod
        def CreateElement(document, category): raise RuntimeError("create failed")
    monkeypatch.setattr(preview,"DirectShape",FailingDirect)
    result=preview.build_shadow_preview(formal(),{"elevation_m":4},{"preview_mode":"replace","preview_true_solar_times":["12:00"]})
    assert [s.Id.IntegerValue for s in doc.shapes] == [1,2]
    assert result["created_element_count"] == result["deleted_element_count"] == 0
    assert result["failure_stage"] == "direct_shape_create"
    assert "subtransaction_rollback" in doc.events and tm.opened == tm.closed == 1


def test_default_preview_times_create_three_safe_names(monkeypatch):
    doc=Document(); install_runtime(monkeypatch,doc)
    slices=[]
    for index, time in enumerate(("08:00:00","12:00:00","16:00:00")):
        item=formal(time=time)["slices"][0]; item["slice_index"]=index; slices.append(item)
    result=preview.build_shadow_preview({"available":True,"slices":slices},{"elevation_m":4},{"preview_mode":"replace"})
    owned=[shape for shape in doc.shapes if shape.ApplicationId == preview.APPLICATION_ID]
    assert result["created_element_count"] == 3
    assert [shape.Name for shape in owned] == ["Dynamo_Shadow_080000_s000","Dynamo_Shadow_120000_s000","Dynamo_Shadow_160000_s000"]


def test_transaction_begin_and_close_failures_are_distinct(monkeypatch):
    doc=Document(); tm=install_runtime(monkeypatch,doc)
    def fail_begin(document): raise RuntimeError("begin failed")
    tm.EnsureInTransaction=fail_begin
    begin=preview.build_shadow_preview(formal(),{"elevation_m":4},{"preview_mode":"clear"})
    assert begin["failure_stage"] == "transaction_begin" and begin["transaction_close_attempted"] is False

    doc=Document(); tm=install_runtime(monkeypatch,doc)
    def fail_close(): tm.closed += 1; raise RuntimeError("close failed")
    tm.TransactionTaskDone=fail_close
    close=preview.build_shadow_preview(formal(),{"elevation_m":4},{"preview_mode":"clear"})
    assert close["failure_stage"] == "transaction_close"
    assert close["transaction_begin_succeeded"] is True and close["transaction_close_succeeded"] is False
