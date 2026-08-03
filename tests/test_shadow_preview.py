import json
import math
import types
import pytest
import shadow_preview as preview


def polygon(points, role="outer"):
    return {"generation_method": preview.GENERATION_METHOD, "closed": True, "role": role,
        "points_m": [{"x":x,"y":y} for x,y in points], "point_count":len(points), "area_m2":1}


def unified(times=("12:00:00",)):
    return {"available":True, "slices":[{"slice_index":i, "true_solar_time":time, "complete":True,
        "polygons":[polygon([(0,0),(2,0),(2,1),(0,1)])],
        "physical_shadow_ray_model":{"x":0,"y":1,"z":-1}} for i,time in enumerate(times)]}


def test_profile_selects_exact_nine_of_seventeen():
    times = tuple("%02d:%02d:00" % (8+i//2, 30*(i%2)) for i in range(17))
    config=preview.normalize_preview_settings({"preview_mode":"replace","profile":"standard_8_16"})
    groups, matched=preview._selected_groups(unified(times),config["requested_true_solar_times"],[])
    assert matched == ["%02d:00:00" % hour for hour in range(8,17)]
    assert len(groups)==9


class XYZ:
    def __init__(self,x,y,z): self.X,self.Y,self.Z=x,y,z
    def DistanceTo(self,o): return math.dist((self.X,self.Y,self.Z),(o.X,o.Y,o.Z))
class Line:
    @staticmethod
    def CreateBound(a,b): return types.SimpleNamespace(start=a,end=b,kind="Curve")


def test_curves_only_and_same_measurement_z(monkeypatch):
    monkeypatch.setattr(preview,"XYZ",XYZ); monkeypatch.setattr(preview,"Line",Line)
    curves=preview._curves([polygon([(0,0),(1,0),(1,1)]),polygon([(.2,.2),(.2,.4),(.4,.4)],"inner")],4,0)
    assert len(curves)==6 and all(c.kind=="Curve" for c in curves)
    assert len({c.start.Z for c in curves}) == 1
    assert curves[0].start.Z == pytest.approx(4*3.280839895013123)
    assert "Solid" not in json.dumps([c.kind for c in curves])


class Id:
    def __init__(self,v): self.IntegerValue=v
class Shape:
    def __init__(self,v,app=""): self.Id=Id(v); self.ApplicationId=app; self.calls=[]
    def SetShape(self,*args): self.calls.append(args)
    def GetType(self): return types.SimpleNamespace(FullName="Autodesk.Revit.DB.DirectShape")
class Direct:
    @staticmethod
    def CreateElement(doc,category):
        shape=Shape(doc.next_id); doc.next_id+=1; doc.shapes.append(shape); return shape
class Collector:
    def __init__(self,doc): self.doc=doc
    def OfClass(self,cls): return self
    def OfCategory(self,category): return self
    def WhereElementIsNotElementType(self): return self
    def ToElements(self): return list(self.doc.shapes)
class Sub:
    def __init__(self,doc): self.doc=doc
    def Start(self): self.snapshot=list(self.doc.shapes)
    def Commit(self): pass
    def RollBack(self): self.doc.shapes=list(self.snapshot)
class TM:
    def __init__(self): self.open=self.close=0
    def EnsureInTransaction(self,doc): self.open+=1
    def TransactionTaskDone(self): self.close+=1
class Doc:
    def __init__(self):
        self.shapes=[Shape(1,preview.APPLICATION_ID),Shape(2,"other")]; self.next_id=3
        self.Application=types.SimpleNamespace(ShortCurveTolerance=0)
        self.ActiveView=types.SimpleNamespace(Id=Id(7),ViewType="FloorPlan",UpDirection=XYZ(0,1,0),SetElementOverrides=lambda *x:None)
    def Delete(self,ident): self.shapes=[s for s in self.shapes if s.Id.IntegerValue != ident.IntegerValue]


def install(monkeypatch,doc):
    monkeypatch.setattr(preview,"XYZ",XYZ); monkeypatch.setattr(preview,"Line",Line)
    monkeypatch.setattr(preview,"DirectShape",Direct); monkeypatch.setattr(preview,"FilteredElementCollector",Collector)
    monkeypatch.setattr(preview,"BuiltInCategory",types.SimpleNamespace(OST_GenericModel=1)); monkeypatch.setattr(preview,"ElementId",lambda x:x)
    monkeypatch.setattr(preview,"SubTransaction",Sub); monkeypatch.setattr(preview,"DirectShapeTargetViewType",None)
    monkeypatch.setattr(preview,"OverrideGraphicSettings",None)
    tm=TM(); monkeypatch.setattr(preview,"DocumentManager",types.SimpleNamespace(Instance=types.SimpleNamespace(CurrentDBDocument=doc)))
    monkeypatch.setattr(preview,"TransactionManager",types.SimpleNamespace(Instance=tm)); return tm


def test_replace_is_nine_element_idempotent_curve_only(monkeypatch):
    doc=Doc(); tm=install(monkeypatch,doc); times=tuple("%02d:00:00"%h for h in range(8,17))
    settings={"preview_mode":"replace","profile":"standard_8_16"}
    first=preview.build_shadow_preview(unified(times),{"elevation_m":4},settings)
    second=preview.build_shadow_preview(unified(times),{"elevation_m":4},settings)
    owned=[s for s in doc.shapes if s.ApplicationId==preview.APPLICATION_ID]
    assert first["created_element_count"]==second["created_element_count"]==len(owned)==9
    assert all(len(s.calls)==1 and all(getattr(c,"kind",None)=="Curve" for c in s.calls[0][0]) for s in owned)
    assert owned[0].Name=="Dynamo_Shadow_TimeLine_0800"
    assert "output_kind=time_shadow_line" in owned[0].ApplicationDataId
    assert tm.open==tm.close==2 and json.dumps(second)


def test_all_creation_failure_rolls_back_old_preview(monkeypatch):
    doc=Doc(); install(monkeypatch,doc)
    class Fail:
        @staticmethod
        def CreateElement(*args): raise RuntimeError("failed")
    monkeypatch.setattr(preview,"DirectShape",Fail)
    result=preview.build_shadow_preview(unified(),{"elevation_m":4},{"preview_mode":"replace","preview_true_solar_times":["12:00"]})
    assert [s.Id.IntegerValue for s in doc.shapes]==[1,2]
    assert result["created_element_count"]==result["deleted_element_count"]==0


def test_preview_rejects_per_caster_formal_contract():
    formal={"available":True,"slices":[{"true_solar_time":"12:00:00","casters":[{"polygons":[polygon([(0,0),(1,0),(0,1)])]}]}]}
    groups,matched=preview._selected_groups(formal,["12:00:00"],[])
    assert groups==[] and matched==[]
