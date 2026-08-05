"""Pure-Python Area site-boundary loop validation and polygon normalization."""
import math

METHOD = "revit_area_single_outer_loop_v1"


def _empty(blocker=None):
    blockers = [] if blocker is None else ([blocker] if isinstance(blocker, dict) else [{"failure_code": blocker}])
    return {"available": False, "complete": False, "method": METHOD, "source": "revit_area",
            "outer_loop": [], "vertex_count": 0, "segment_count": 0, "orientation": None,
            "signed_area_m2": 0.0, "area_m2": 0.0, "perimeter_m": 0.0, "bounds_m": None,
            "join_tolerance_m": None, "planarity_tolerance_m": None, "blockers": blockers,
            "warnings": [], "legal_judgement_generated": False, "permit_ready_certified": False}


def _dist(a, b):
    return math.hypot(a["x_m"] - b["x_m"], a["y_m"] - b["y_m"])


def _area(pts):
    return 0.5 * sum(pts[i]["x_m"] * pts[(i + 1) % len(pts)]["y_m"] - pts[(i + 1) % len(pts)]["x_m"] * pts[i]["y_m"] for i in range(len(pts)))


def _seg_key(a, b, tol):
    qa = (round(a["x_m"] / tol), round(a["y_m"] / tol)); qb = (round(b["x_m"] / tol), round(b["y_m"] / tol))
    return (qa, qb)


def _orient(a,b,c): return (b["x_m"]-a["x_m"])*(c["y_m"]-a["y_m"])-(b["y_m"]-a["y_m"])*(c["x_m"]-a["x_m"])

def _intersect(a,b,c,d,tol):
    def on(p,q,r): return min(p["x_m"],r["x_m"])-tol <= q["x_m"] <= max(p["x_m"],r["x_m"])+tol and min(p["y_m"],r["y_m"])-tol <= q["y_m"] <= max(p["y_m"],r["y_m"])+tol and abs(_orient(p,q,r))<=tol
    o1,o2,o3,o4=_orient(a,b,c),_orient(a,b,d),_orient(c,d,a),_orient(c,d,b)
    if o1*o2 < -tol and o3*o4 < -tol: return True
    return any([on(a,c,b),on(a,d,b),on(c,a,d),on(c,b,d)])


def build_site_boundary_geometry(extracted_area_boundary, join_tolerance_m=0.005, planarity_tolerance_m=0.005):
    src = extracted_area_boundary or {}
    res = _empty(); res["join_tolerance_m"] = join_tolerance_m; res["planarity_tolerance_m"] = planarity_tolerance_m
    if src.get("complete") is not True:
        res["blockers"] = list(src.get("blockers") or [{"failure_code": "site_boundary_geometry_missing"}]); return res
    loops = src.get("loops") or []
    if len(loops) != 1:
        res["blockers"].append({"failure_code": "site_boundary_area_multiple_loops_unsupported", "loop_count": len(loops)}); return res
    if (src.get("maximum_z_difference_m") or 0.0) > planarity_tolerance_m:
        res["blockers"].append({"failure_code": "site_boundary_area_nonplanar", "maximum_z_difference_m": src.get("maximum_z_difference_m")}); return res
    segs = loops[0].get("segments") or []
    if len(segs) < 3:
        res["blockers"].append({"failure_code": "site_boundary_open_loop"}); return res
    pts=[]; seen=set(); seen_rev=set()
    for i,s in enumerate(segs):
        if s.get("curve_type") != "Line":
            res["blockers"].append({"failure_code":"unsupported_site_boundary_curve_type","curve_type":s.get("curve_type"),"segment_index":i}); return res
        a,b=s.get("start"),s.get("end")
        if not isinstance(a,dict) or not isinstance(b,dict): res["blockers"].append({"failure_code":"site_boundary_geometry_missing","segment_index":i}); return res
        if _dist(a,b) <= 1e-12: res["blockers"].append({"failure_code":"site_boundary_zero_length_segment","segment_index":i}); return res
        if _dist(a,b) < join_tolerance_m: res["blockers"].append({"failure_code":"site_boundary_short_segment","segment_index":i}); return res
        k=_seg_key(a,b,join_tolerance_m); rk=_seg_key(b,a,join_tolerance_m)
        if k in seen: res["blockers"].append({"failure_code":"site_boundary_duplicate_segment","segment_index":i}); return res
        if rk in seen: res["blockers"].append({"failure_code":"site_boundary_duplicate_segment","segment_index":i,"reverse":True}); return res
        seen.add(k); pts.append({"x_m":float(a["x_m"]),"y_m":float(a["y_m"])})
        if i < len(segs)-1 and _dist(b, segs[i+1].get("start") or {}) > join_tolerance_m:
            res["blockers"].append({"failure_code":"site_boundary_disconnected_segments","segment_index":i}); return res
    if _dist(segs[-1].get("end") or {}, segs[0].get("start") or {}) > join_tolerance_m:
        res["blockers"].append({"failure_code":"site_boundary_open_loop"}); return res
    keys=[]
    for i,p in enumerate(pts):
        k=(round(p["x_m"]/join_tolerance_m),round(p["y_m"]/join_tolerance_m))
        if k in keys: res["blockers"].append({"failure_code":"site_boundary_repeated_vertex","vertex_index":i}); return res
        keys.append(k)
    n=len(pts)
    for i in range(n):
        for j in range(i+1,n):
            if abs(i-j)<=1 or {i,j}=={0,n-1}: continue
            if _intersect(pts[i],pts[(i+1)%n],pts[j],pts[(j+1)%n],join_tolerance_m): res["blockers"].append({"failure_code":"site_boundary_self_intersection","segment_index":i,"other_segment_index":j}); return res
    signed=_area(pts)
    if abs(signed) <= 1e-12: res["blockers"].append({"failure_code":"site_boundary_zero_area"}); return res
    if signed < 0: pts=list(reversed(pts)); signed=-signed
    start=min(range(len(pts)), key=lambda i:(pts[i]["x_m"], pts[i]["y_m"])); pts=pts[start:]+pts[:start]
    per=sum(_dist(pts[i],pts[(i+1)%len(pts)]) for i in range(len(pts)))
    res.update({"available":True,"complete":True,"outer_loop":pts,"vertex_count":len(pts),"segment_count":len(pts),"orientation":"counter_clockwise","signed_area_m2":signed,"area_m2":signed,"perimeter_m":per,"bounds_m":{"min_x":min(p["x_m"] for p in pts),"min_y":min(p["y_m"] for p in pts),"max_x":max(p["x_m"] for p in pts),"max_y":max(p["y_m"] for p in pts)}})
    return res
