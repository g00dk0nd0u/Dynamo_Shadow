"""Read a single placed Revit Area boundary through SpatialElement boundary API."""
from shadow_units import _internal_length_to_meters, _internal_area_to_m2
from shadow_utils import _try_unwrap_with_diagnostics, _to_list, _type_name, _safe_attr, _category_name
try:
    from shadow_revit_api import BuiltInCategory
except Exception:
    BuiltInCategory = None
try:
    from Autodesk.Revit.DB import SpatialElement, SpatialElementBoundaryOptions, Line
    try:
        from Autodesk.Revit.DB.Architecture import Area, Room
    except Exception:
        Area = Room = None
    try:
        from Autodesk.Revit.DB.Mechanical import Space
    except Exception:
        Space = None
except Exception:
    SpatialElement = SpatialElementBoundaryOptions = Line = Area = Room = Space = None

METHOD="revit_area_spatial_boundary_v1"

def _empty(provided=False, blocker=None):
    return {"provided":provided,"available":False,"complete":False,"method":METHOD,"source_type":None,"source_element_count":0,"loop_count":0,"loops":[],"level_id_available":False,"z_min_m":None,"z_max_m":None,"maximum_z_difference_m":None,"blockers":[] if blocker is None else [{"failure_code":blocker}],"warnings":[],"permit_ready_certified":False}

def _flatten(v):
    out=[]
    for x in _to_list(v):
        if isinstance(x,(list,tuple)):
            out.extend(_flatten(x))
        elif x is not None:
            out.append(x)
    return out

def _category_is_area(e):
    cat=_category_name(e) or ""; return "area" in cat.lower() or "エリア" in cat

def _is_area(e):
    if e is None: return False
    if Area is not None and isinstance(e, Area): return True
    if Room is not None and isinstance(e, Room): return False
    if Space is not None and isinstance(e, Space): return False
    if SpatialElement is not None and isinstance(e, SpatialElement) and _category_is_area(e): return True
    tn=_type_name(e).lower()
    if "room" in tn or "space" in tn or "tag" in tn or "filledregion" in tn: return False
    return tn.endswith("area") or ".area" in tn or _category_is_area(e)

def _point_m(xyz):
    x,w=_internal_length_to_meters(getattr(xyz,"X",None)); y,w2=_internal_length_to_meters(getattr(xyz,"Y",None)); z,w3=_internal_length_to_meters(getattr(xyz,"Z",None))
    return {"x_m":x,"y_m":y,"z_m":z}, w+w2+w3

def _curve_type(curve): return _type_name(curve).split('.')[-1]

def _is_line(curve):
    if Line is not None and isinstance(curve, Line): return True
    return _curve_type(curve).lower() == "line"

def extract_site_boundary_area(area_input):
    items=[]
    for raw in _flatten(area_input):
        unwrapped,_=_try_unwrap_with_diagnostics(raw)
        if unwrapped is not None: items.append(unwrapped)
    if not items: return _empty(False)
    if len(items)>1: return _empty(True,"multiple_site_boundary_areas_not_supported")
    area=items[0]
    res=_empty(True); res["source_element_count"]=1; res["source_type"]=_type_name(area).split('.')[-1]
    if not _is_area(area):
        res["blockers"].append({"failure_code":"site_boundary_input_is_not_area","input_type":res["source_type"]}); return res
    res["source_type"]="Area"
    if not hasattr(area,"GetBoundarySegments"):
        res["blockers"].append({"failure_code":"site_boundary_area_boundary_missing"}); return res
    try:
        area_raw=_safe_attr(area,"Area")
        if area_raw is not None:
            area_m2,w=_internal_area_to_m2(area_raw); res["area_api_m2"] = area_m2; res["warnings"].extend(w)
            if area_m2 is not None and area_m2 <= 0:
                res["blockers"].append({"failure_code":"site_boundary_area_unplaced_or_unbounded"}); return res
    except Exception: pass
    try:
        opts=SpatialElementBoundaryOptions() if SpatialElementBoundaryOptions is not None else None
        loops_raw=area.GetBoundarySegments(opts)
    except Exception:
        res["blockers"].append({"failure_code":"site_boundary_area_unplaced_or_unbounded"}); return res
    loops=list(loops_raw or [])
    if not loops:
        res["blockers"].append({"failure_code":"site_boundary_area_boundary_missing"}); return res
    res["loop_count"]=len(loops)
    if len(loops)>1:
        res["blockers"].append({"failure_code":"site_boundary_area_multiple_loops_unsupported","loop_count":len(loops)}); return res
    zs=[]
    for li,loop in enumerate(loops):
        segs=[]
        for si,bs in enumerate(list(loop or [])):
            try: curve=bs.GetCurve()
            except Exception:
                res["blockers"].append({"failure_code":"site_boundary_area_boundary_missing","segment_index":si}); return res
            ct=_curve_type(curve)
            if not _is_line(curve):
                res["blockers"].append({"failure_code":"unsupported_site_boundary_curve_type","curve_type":ct,"segment_index":si}); return res
            try:
                p0=curve.GetEndPoint(0); p1=curve.GetEndPoint(1)
                a,w=_point_m(p0); b,w2=_point_m(p1); res["warnings"].extend(w+w2); zs.extend([a["z_m"],b["z_m"]])
            except Exception:
                res["blockers"].append({"failure_code":"site_boundary_area_boundary_missing","segment_index":si}); return res
            segs.append({"curve_type":"Line","start":a,"end":b,"segment_index":si})
        res["loops"].append({"loop_index":li,"segment_count":len(segs),"segments":segs})
    zs=[z for z in zs if z is not None]
    res["z_min_m"]=min(zs) if zs else None; res["z_max_m"]=max(zs) if zs else None; res["maximum_z_difference_m"]=(res["z_max_m"]-res["z_min_m"]) if zs else None
    res["level_id_available"] = _safe_attr(area,"LevelId") is not None
    res["available"]=True; res["complete"]=not res["blockers"]
    return res
