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
class Collector:
    def __init__(self, doc): self.doc=doc
    def OfClass(self, cls): return self.doc.patterns if cls is FakeFill else self.doc.shapes
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
    def EnsureInTransaction(self, doc): self.opened+=1
    def TransactionTaskDone(self): self.closed+=1
class Document:
    def __init__(self):
        self.shapes=[Shape(1,preview.APPLICATION_ID),Shape(2,"other")]; self.patterns=[]; self.next_id=3
        self.Application=types.SimpleNamespace(ShortCurveTolerance=0); self.ActiveView=types.SimpleNamespace(Id=Id(9),ViewType="3D")
    def Delete(self, ids):
        values={i.IntegerValue for i in ids}; self.shapes=[s for s in self.shapes if s.Id.IntegerValue not in values]


def install_runtime(monkeypatch, document):
    install_geometry(monkeypatch); Geometry.calls=[]
    monkeypatch.setattr(preview,"GeometryCreationUtilities",Geometry); monkeypatch.setattr(preview,"DirectShape",Direct)
    monkeypatch.setattr(preview,"FilteredElementCollector",Collector); monkeypatch.setattr(preview,"FillPatternElement",FakeFill)
    monkeypatch.setattr(preview,"BuiltInCategory",types.SimpleNamespace(OST_GenericModel=42)); monkeypatch.setattr(preview,"ElementId",lambda x:x)
    tm=TM(); monkeypatch.setattr(preview,"DocumentManager",types.SimpleNamespace(Instance=types.SimpleNamespace(CurrentDBDocument=document)))
    monkeypatch.setattr(preview,"TransactionManager",types.SimpleNamespace(Instance=tm)); return tm


def test_clear_deletes_only_owned_directshape(monkeypatch):
    doc=Document(); tm=install_runtime(monkeypatch,doc)
    result=preview.build_shadow_preview(formal(),{"elevation_m":4},{"preview_mode":"clear"})
    assert result["deleted_element_count"]==1 and result["created_element_count"]==0
    assert [s.ApplicationId for s in doc.shapes]==["other"] and tm.opened==tm.closed==1


def test_replace_is_idempotent_and_serializes_no_native_objects(monkeypatch):
    doc=Document(); tm=install_runtime(monkeypatch,doc)
    settings={"preview_mode":"replace","preview_true_solar_times":["12:00"]}
    first=preview.build_shadow_preview(formal(),{"elevation_m":4},settings)
    second=preview.build_shadow_preview(formal(),{"elevation_m":4},settings)
    owned=[s for s in doc.shapes if s.ApplicationId==preview.APPLICATION_ID]
    assert first["created_element_count"]==second["created_element_count"]==len(owned)==1
    assert owned[0].ApplicationDataId=="slice=4;caster=2;solid=0" and owned[0].shapes
    assert Geometry.calls[-1][1] is XYZ.BasisZ and Geometry.calls[-1][2] > 0
    assert tm.opened==tm.closed==2 and json.dumps(second)
