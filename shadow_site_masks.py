"""Pure-Python 5m/10m point-distance masks for duration grids."""
import math
METHOD="point_to_area_boundary_distance_v1"
ZONES=["inside_site","on_site_boundary","outside_0_to_5m","near_5_to_10m","far_over_10m"]

def _empty(blocker=None):
    return {"available":False,"complete":False,"method":METHOD,"duration_grid_point_count":0,"zone_counts":{z:0 for z in ZONES},"near":{"available":False},"far":{"available":False},"boundary_dependent_ready":False,"legal_judgement_generated":False,"ordinance_selection_certified":False,"permit_ready_certified":False,"blockers":[] if blocker is None else [{"failure_code":blocker}],"warnings":[]}

def _dist_point_seg(p,a,b):
    vx,vy=b[0]-a[0],b[1]-a[1]; wx,wy=p[0]-a[0],p[1]-a[1]; den=vx*vx+vy*vy
    t=0 if den==0 else max(0,min(1,(wx*vx+wy*vy)/den)); q=(a[0]+t*vx,a[1]+t*vy)
    return math.hypot(p[0]-q[0],p[1]-q[1])

def _inside(p, poly, eps):
    x,y=p; inside=False
    for i,a in enumerate(poly):
        b=poly[(i+1)%len(poly)]
        if _dist_point_seg(p,a,b) <= eps: return None
        if (a[1]>y)!=(b[1]>y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]: inside=not inside
    return inside

def _classify(p, poly, eps):
    d=min(_dist_point_seg(p, poly[i], poly[(i+1)%len(poly)]) for i in range(len(poly)))
    inn=_inside(p,poly,eps)
    if inn is None: return "on_site_boundary", d
    if inn: return "inside_site", d
    if d <= 5.0 + eps: return "outside_0_to_5m", d
    if d <= 10.0 + eps: return "near_5_to_10m", d
    return "far_over_10m", d

def _best(best, point):
    if best is None: return point
    key=lambda q:(-q["maximum_shadow_duration_minutes"], q["point"]["x_m"], q["point"]["y_m"])
    return point if key(point) < key(best) else best

def build_measurement_masks(shadow_duration, site_boundary_geometry, distance_tolerance_m=1e-6):
    if not (site_boundary_geometry or {}).get("complete"): return _empty("site_boundary_geometry_required")
    if not (shadow_duration or {}).get("complete"): return _empty("complete_shadow_duration_required")
    poly=[(float(p["x_m"]),float(p["y_m"])) for p in site_boundary_geometry.get("outer_loop") or []]
    if len(poly)<3: return _empty("site_boundary_geometry_required")
    res=_empty(); res.update({"available":True,"complete":True,"boundary_dependent_ready":True,"distance_tolerance_m":distance_tolerance_m})
    near=far=None; grid=shadow_duration.get("duration_grid") or []
    res["duration_grid_point_count"]=len(grid)
    for g in grid:
        p=(float(g["x_m"]),float(g["y_m"])); zone,d=_classify(p,poly,distance_tolerance_m); res["zone_counts"][zone]+=1
        dur=float(g.get("shadow_duration_minutes") or 0.0)
        cand={"available":True,"maximum_shadow_duration_minutes":dur,"point":{"x_m":p[0],"y_m":p[1],"distance_from_site_boundary_m":d}}
        if zone=="near_5_to_10m": near=_best(near,cand)
        if zone=="far_over_10m": far=_best(far,cand)
    res["near"]=near or {"available":False}; res["far"]=far or {"available":False}
    return res
