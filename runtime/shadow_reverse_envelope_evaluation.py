"""Shared pure-Python evaluation of a prism against a Reverse height mesh."""
import math

from shadow_forward_equivalent_validator import point_in_polygon


def interpolate_reverse_height(reverse_result, x, y, tolerance=1e-9):
    points = ((reverse_result or {}).get("height_field") or {}).get("grid_points") or []
    triangles = ((reverse_result or {}).get("top_surface_mesh") or {}).get("triangles") or []
    for triangle in triangles:
        vertices = [points[index] for index in triangle["vertex_grid_indices"]]
        ax, ay = vertices[0]["x_m"], vertices[0]["y_m"]
        bx, by = vertices[1]["x_m"], vertices[1]["y_m"]
        cx, cy = vertices[2]["x_m"], vertices[2]["y_m"]
        denominator = (by-cy)*(ax-cx)+(cx-bx)*(ay-cy)
        if abs(denominator) <= tolerance: continue
        wa = ((by-cy)*(x-cx)+(cx-bx)*(y-cy))/denominator
        wb = ((cy-ay)*(x-cx)+(ax-cx)*(y-cy))/denominator
        wc = 1.0-wa-wb
        if min(wa, wb, wc) >= -tolerance:
            heights = [vertex.get("height_limit_m") for vertex in vertices]
            if any(value is None or not math.isfinite(float(value)) for value in heights): return None
            return wa*heights[0]+wb*heights[1]+wc*heights[2]
    return None


def _sample_polygon(polygon, spacing):
    points = set()
    for index, start in enumerate(polygon):
        end = polygon[(index+1)%len(polygon)]
        count = max(1, int(math.ceil(math.hypot(end[0]-start[0], end[1]-start[1])/spacing)))
        for step in range(count+1):
            fraction = float(step)/count
            points.add((round(start[0]+fraction*(end[0]-start[0]), 9),
                        round(start[1]+fraction*(end[1]-start[1]), 9)))
    min_x,max_x=min(p[0] for p in polygon),max(p[0] for p in polygon)
    min_y,max_y=min(p[1] for p in polygon),max(p[1] for p in polygon)
    for iy in range(math.ceil(min_y/spacing), math.floor(max_y/spacing)+1):
        for ix in range(math.ceil(min_x/spacing), math.floor(max_x/spacing)+1):
            point=(round(ix*spacing,9),round(iy*spacing,9))
            if point_in_polygon(point,polygon): points.add(point)
    return sorted(points,key=lambda value:(value[1],value[0]))


def evaluate_prism_against_reverse_envelope(footprint, candidate_height_m, reverse_result,
                                             validation_spacing_m=0.5):
    polygon=[(float(p[0]),float(p[1])) for p in footprint]
    samples=_sample_polygon(polygon,validation_spacing_m); evaluated=[]
    for x,y in samples:
        limit=interpolate_reverse_height(reverse_result,x,y)
        excess=None if limit is None else float(candidate_height_m)-limit
        evaluated.append({"x_m":x,"y_m":y,"height_limit_m":limit,"height_excess_m":excess})
    bounded=[item for item in evaluated if item["height_limit_m"] is not None]
    exceeded=[item for item in bounded if item["height_excess_m"]>1e-9]
    unbounded=[item for item in evaluated if item["height_limit_m"] is None]
    worst=max(evaluated,key=lambda item:(float("inf") if item["height_excess_m"] is None else item["height_excess_m"],-item["y_m"],-item["x_m"])) if evaluated else None
    margins=[item["height_limit_m"]-float(candidate_height_m) for item in bounded]
    return {"fully_inside":bool(evaluated) and not exceeded and not unbounded,
        "validation_spacing_m":validation_spacing_m,"validation_point_count":len(evaluated),
        "inside_point_count":len(bounded)-len(exceeded),"exceeded_point_count":len(exceeded),
        "unbounded_point_count":len(unbounded),
        "maximum_height_excess_m":max([item["height_excess_m"] for item in exceeded] or [0.0]),
        "minimum_height_margin_m":min(margins) if margins else None,"worst_point":worst}
