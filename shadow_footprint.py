# Footprint candidate diagnostics only; no formal polygon generation.
from shadow_policies import FOOTPRINT_EXTRACTION_POLICY
from shadow_utils import *
from shadow_units import _candidate_raw_to_meters, _internal_area_to_m2, _point_raw_to_meters


def _safe_count(value):
    try:
        return len(value)
    except Exception:
        try:
            return sum(1 for _ in value)
        except Exception:
            return 0

def _edge_to_curve(edge):
    if edge is None:
        return None
    if _is_edge_like(edge):
        curve, err = _safe_call(edge, "AsCurve")
        return None if err else curve
    return edge if _is_curve_like(edge) else None

def _safe_curve_endpoints(curve_or_edge):
    curve = _edge_to_curve(curve_or_edge)
    if curve is None:
        return None, None, "curve unavailable"
    p0, e0 = _safe_call(curve, "GetEndPoint", 0)
    p1, e1 = _safe_call(curve, "GetEndPoint", 1)
    if e0 or e1 or p0 is None or p1 is None:
        return None, None, e0 or e1 or "endpoints unavailable"
    return p0, p1, None

def _safe_curve_length(curve_or_edge):
    curve = _edge_to_curve(curve_or_edge)
    return _safe_float_attr(curve, "Length") if curve is not None else None

def _safe_curve_type(value):
    curve = _edge_to_curve(value)
    return _type_name(curve if curve is not None else value)

def _curve_endpoint_raw_dicts(curve):
    p0, p1, err = _safe_curve_endpoints(curve)
    if err:
        return [], err
    return [_xyz_to_raw_dict(p0), _xyz_to_raw_dict(p1)], None

def _points_close_raw(p0, p1, tolerance=None):
    if p0 is None or p1 is None:
        return None
    tol = 1e-6 if tolerance is None else tolerance
    try:
        return all(abs(float(p0.get(k)) - float(p1.get(k))) <= tol for k in ("x", "y", "z"))
    except Exception:
        return None

def _raw_z_values_from_points(points):
    values = []
    for p in points or []:
        try:
            if p is not None and p.get("z") is not None:
                values.append(float(p.get("z")))
        except Exception:
            pass
    return values

def _raw_xy_key(point, precision=6):
    try:
        return (round(float(point.get("x")), precision), round(float(point.get("y")), precision))
    except Exception:
        return None

def _dedupe_raw_points(points):
    seen = set(); out = []
    for point in points or []:
        key = None
        try:
            key = (round(float(point.get("x")), 6), round(float(point.get("y")), 6), round(float(point.get("z")), 6))
        except Exception:
            key = _safe_text(point)
        if key not in seen:
            seen.add(key); out.append(point)
    return out

def _is_line_curve_type_name(curve_type):
    if not curve_type:
        return False
    try:
        normalized = str(curve_type).strip().lower()
    except Exception:
        return False
    normalized = normalized.replace(" ", "")
    leaf = normalized.split(".")[-1]
    return leaf == "line"

def _summarize_curve_for_footprint(value):
    warnings = []
    curve = _edge_to_curve(value)
    if curve is None:
        warnings.append("curve unavailable")
    endpoints, err = _curve_endpoint_raw_dicts(curve) if curve is not None else ([], "curve unavailable")
    if err:
        warnings.append(err)
    tess_count = None
    if curve is not None:
        tess, terr = _safe_call(curve, "Tessellate")
        if not terr and tess is not None:
            tess_count = min(_safe_count(_safe_iter(tess)), 20)
    z = _raw_z_values_from_points(endpoints)
    summary = {"input_type": _type_name(value), "curve_type": _safe_curve_type(value), "length_raw": _safe_curve_length(value), "endpoints_raw": endpoints, "endpoint_count": len(endpoints), "z_min_raw": min(z) if z else None, "z_max_raw": max(z) if z else None, "tessellation_sample_point_count": tess_count, "formal_discretization_generated": False, "warnings": warnings}
    converted, cw = _candidate_raw_to_meters({"total_length_raw": summary.get("length_raw"), "z_min_raw": summary.get("z_min_raw"), "z_max_raw": summary.get("z_max_raw"), "endpoints_raw_sample": endpoints})
    summary["length_m"] = converted.get("total_length_m")
    summary["endpoints_m"] = converted.get("endpoints_m_sample")
    summary["z_min_m"] = converted.get("z_min_m")
    summary["z_max_m"] = converted.get("z_max_m")
    if cw: summary["unit_conversion_warnings"] = cw
    return summary

def _extract_edge_loop_candidates_from_face(face, face_summary=None):
    warnings=[]; loops_out=[]
    loops = _safe_iter(_safe_attr(face, "EdgeLoops"))
    
    if face_summary is None:
        from shadow_geometry import _summarize_face
    fs = face_summary or _summarize_face(face)
    for li, loop in enumerate(loops):
        endpoints=[]; curve_types=[]; total=0.0; total_known=True; curve_count=0; lw=[]
        for edge in _safe_iter(loop):
            cs = _summarize_curve_for_footprint(edge); curve_count += 1
            curve_types.append(cs.get("curve_type")); endpoints.extend(cs.get("endpoints_raw") or [])
            if cs.get("length_raw") is None: total_known=False
            else: total += cs.get("length_raw")
            lw.extend(cs.get("warnings") or [])
        zvals=_raw_z_values_from_points(endpoints); unique=_dedupe_raw_points(endpoints)
        if endpoints:
            closed=_points_close_raw(endpoints[0], endpoints[-1]); method="raw_endpoint_comparison"
        else:
            closed=None; method="assumed_by_revit_edge_loop_but_not_verified" if loop is not None else "unavailable"
        if zvals:
            horiz=(max(zvals)-min(zvals)) <= 1e-6
        else:
            horiz=None
        non_line=any(ct is not None and not _is_line_curve_type_name(ct) for ct in curve_types)
        loop_summary={"loop_index":li,"edge_count":_safe_count(_safe_iter(loop)),"curve_count":curve_count,"endpoint_count":len(endpoints),"unique_endpoint_count":len(unique),"endpoints_raw_sample":endpoints[:12],"z_min_raw":min(zvals) if zvals else None,"z_max_raw":max(zvals) if zvals else None,"z_variation_raw":(max(zvals)-min(zvals)) if zvals else None,"closed_candidate":closed,"closure_method":method,"horizontal_candidate":horiz,"curve_types":sorted(set([c for c in curve_types if c])),"total_length_raw":total if total_known else None,"has_arc_or_non_line_curve":non_line,"formal_polygon_generated":False,"self_intersection_checked":False,"warnings":lw}
        converted, cw = _candidate_raw_to_meters(loop_summary)
        loop_summary["endpoints_m"] = [_point_raw_to_meters(pt)[0] for pt in endpoints]
        loop_summary["endpoints_m_sample"] = converted.get("endpoints_m_sample")
        loop_summary["total_length_m"] = converted.get("total_length_m")
        loop_summary["z_min_m"] = converted.get("z_min_m")
        loop_summary["z_max_m"] = converted.get("z_max_m")
        if cw: loop_summary["unit_conversion_warnings"] = cw
        loops_out.append(loop_summary)
    if not loops:
        warnings.append("face EdgeLoops unavailable or empty; no footprint edge loop candidate was read.")
    return {"available": bool(loops_out), "source_face_type": fs.get("type") or _type_name(face), "source_face_role_candidate": fs.get("height_role_candidate"), "source_face_orientation_candidate": fs.get("orientation_candidate"), "face_area_raw": fs.get("area_raw"), "face_area_m2": fs.get("area_m2") or _internal_area_to_m2(fs.get("area_raw"))[0], "face_origin_raw": fs.get("origin_raw"), "face_origin_m": fs.get("origin_m") or _point_raw_to_meters(fs.get("origin_raw"))[0], "face_normal_raw": fs.get("normal_raw"), "edge_loop_count": len(loops_out), "loops": loops_out, "warnings": warnings}

def _extract_footprint_candidates_from_faces(face_summaries, face_objects, measurement_plane=None):
    candidates=[]; warnings=[]; info=[]; bi=0
    for idx, fs in enumerate(face_summaries or []):
        if fs.get("height_role_candidate") != "bottom_face_candidate":
            continue
        face = face_objects[idx] if idx < len(face_objects or []) else None
        loops = _extract_edge_loop_candidates_from_face(face, fs) if face is not None else {"available":False,"loops":[],"warnings":["bottom face object unavailable; summary only."]}
        warnings.extend(loops.get("warnings") or [])
        for loop in loops.get("loops") or []:
            candidates.append({"candidate_index":len(candidates),"source":"bottom_face_candidate_edge_loop","source_face_index":idx,"source_face_type":fs.get("type"),"source_face_area_raw":fs.get("area_raw"),"source_face_origin_raw":fs.get("origin_raw"),"source_face_normal_raw":fs.get("normal_raw"),"loop_index":loop.get("loop_index"),"edge_count":loop.get("edge_count"),"curve_count":loop.get("curve_count"),"closed_candidate":loop.get("closed_candidate"),"horizontal_candidate":loop.get("horizontal_candidate"),"z_min_raw":loop.get("z_min_raw"),"z_max_raw":loop.get("z_max_raw"),"z_min_m":loop.get("z_min_m"),"z_max_m":loop.get("z_max_m"),"z_variation_raw":loop.get("z_variation_raw"),"total_length_raw":loop.get("total_length_raw"),"total_length_m":loop.get("total_length_m"),"curve_types":loop.get("curve_types"),"endpoints_raw_sample":loop.get("endpoints_raw_sample"),"endpoints_m":loop.get("endpoints_m"),"endpoints_m_sample":loop.get("endpoints_m_sample"),"formal_footprint_polygon_generated":False,"units":"revit_raw_internal_units","relation_to_measurement_plane":{"measurement_plane_available":(measurement_plane or {}).get("available") is True,"diagnostic_only":True,"meter_comparison_available": (measurement_plane or {}).get("available") is True and loop.get("z_min_m") is not None,"meter_relation_candidate": "diagnostic_candidate_only","unit_conversion_status":"diagnostic_conversion_available","used_for_legal_judgement":False,"used_for_shadow_geometry":False,"formal_intersection_test_performed":False},"warnings":loop.get("warnings") or []})
    def score(c):
        return (1 if c.get("closed_candidate") is True else 0, 1 if c.get("horizontal_candidate") is True else 0, c.get("edge_count") or 0, c.get("source_face_area_raw") or 0)
    best = sorted(candidates, key=score, reverse=True)[0] if candidates else None
    bottom=sum(1 for f in face_summaries or [] if f.get("height_role_candidate")=="bottom_face_candidate")
    closed=sum(1 for c in candidates if c.get("closed_candidate") is True); horiz=sum(1 for c in candidates if c.get("horizontal_candidate") is True)
    blockers=[]
    if bottom<=0: blockers.append("No bottom face candidate was found.")
    if not candidates: blockers.append("No edge loop candidate was found from bottom face candidates.")
    if closed<=0: blockers.append("No closed loop candidate was verified by raw endpoint comparison.")
    return {"available": bool(candidates), "bottom_face_candidate_count": bottom, "loop_candidate_count": len(candidates), "closed_loop_candidate_count": closed, "horizontal_loop_candidate_count": horiz, "best_candidate": best, "candidates": candidates, "readiness": {"ready_for_future_footprint_polygon_generation": bool(closed>0), "blockers": blockers}, "warnings": warnings, "info": info}



def _signed_area_2d(points):
    area = 0.0
    for i in range(len(points)):
        j = (i + 1) % len(points)
        area += float(points[i]["x"]) * float(points[j]["y"]) - float(points[j]["x"]) * float(points[i]["y"])
    return area / 2.0

def _point_xy_equal(a, b, tol=1e-7):
    try:
        return abs(float(a.get("x")) - float(b.get("x"))) <= tol and abs(float(a.get("y")) - float(b.get("y"))) <= tol
    except Exception:
        return False

def _cluster_or_match_xy_points(points, tolerance_m=0.001):
    clusters = []
    assignments = []
    warnings = []
    for point in points or []:
        if point is None or point.get("x") is None or point.get("y") is None:
            assignments.append(None)
            warnings.append("invalid XY endpoint encountered.")
            continue
        xy = {"x": float(point.get("x")), "y": float(point.get("y"))}
        matched = None
        for index, cluster in enumerate(clusters):
            if _point_xy_equal(xy, cluster, tolerance_m):
                matched = index
                break
        if matched is None:
            matched = len(clusters)
            clusters.append(xy)
        assignments.append(matched)
    return clusters, assignments, warnings

def _segment_length_xy(a, b):
    return ((float(a["x"]) - float(b["x"])) ** 2 + (float(a["y"]) - float(b["y"])) ** 2) ** 0.5

def _validate_segment_graph(segments, tolerance_m=0.001):
    warnings = []
    flat = []
    for segment in segments or []:
        flat.append(segment.get("start")); flat.append(segment.get("end"))
    clusters, assignments, cluster_warnings = _cluster_or_match_xy_points(flat, tolerance_m)
    warnings.extend(cluster_warnings)
    if cluster_warnings:
        return {"valid": False, "clusters": clusters, "edges": [], "warnings": warnings}
    edges = []
    seen_edges = set()
    degree = {}
    for index, segment in enumerate(segments or []):
        a_id = assignments[index * 2]
        b_id = assignments[index * 2 + 1]
        if a_id is None or b_id is None:
            warnings.append("segment has invalid endpoint(s).")
            continue
        if a_id == b_id or _segment_length_xy(clusters[a_id], clusters[b_id]) <= tolerance_m:
            warnings.append("segment {0} is shorter than or equal to tolerance.".format(index))
            continue
        edge_key = tuple(sorted((a_id, b_id)))
        if edge_key in seen_edges:
            warnings.append("duplicate edge detected between clustered endpoints {0} and {1}.".format(edge_key[0], edge_key[1]))
            continue
        seen_edges.add(edge_key)
        edges.append({"index": index, "a": a_id, "b": b_id})
        degree[a_id] = degree.get(a_id, 0) + 1
        degree[b_id] = degree.get(b_id, 0) + 1
    if len(edges) != len(segments or []):
        warnings.append("not all input edges are valid unique segments.")
    if len(edges) < 3:
        warnings.append("fewer than 3 valid segments are available.")
    for node_id, count in sorted(degree.items()):
        if count > 2:
            warnings.append("branch detected at clustered endpoint {0}; degree is {1}.".format(node_id, count))
        elif count < 2:
            warnings.append("open or isolated endpoint detected at clustered endpoint {0}; degree is {1}.".format(node_id, count))
    valid = (len(warnings) == 0 and len(edges) == len(segments or []) and len(edges) >= 3 and all(count == 2 for count in degree.values()) and len(degree) == len(edges))
    return {"valid": valid, "clusters": clusters, "edges": edges, "warnings": warnings}

def _build_ordered_loop_from_segments(segments, tolerance_m=0.001):
    graph = _validate_segment_graph(segments, tolerance_m)
    if not graph.get("valid"):
        return None, graph.get("warnings") or ["segment graph is invalid."]
    clusters = graph.get("clusters") or []
    edges = graph.get("edges") or []
    adjacency = {}
    for edge_pos, edge in enumerate(edges):
        adjacency.setdefault(edge["a"], []).append((edge["b"], edge_pos))
        adjacency.setdefault(edge["b"], []).append((edge["a"], edge_pos))
    start = edges[0]["a"]
    current = start
    previous = None
    used = set()
    ordered_ids = [start]
    while True:
        next_choice = None
        for neighbor, edge_pos in adjacency.get(current, []):
            if edge_pos in used:
                continue
            if previous is not None and neighbor == previous and len(adjacency.get(current, [])) > 1:
                continue
            next_choice = (neighbor, edge_pos)
            break
        if next_choice is None:
            return None, ["closed ordered loop could not consume all edges."]
        neighbor, edge_pos = next_choice
        used.add(edge_pos)
        previous = current
        current = neighbor
        if current == start:
            if len(used) == len(edges):
                break
            return None, ["loop closed before all edges were used; unused edge(s) remain."]
        ordered_ids.append(current)
        if len(ordered_ids) > len(edges):
            return None, ["loop traversal exceeded edge count; graph is ambiguous."]
    if len(used) != len(edges):
        return None, ["not all edges were used exactly once."]
    points = [{"x": clusters[node_id]["x"], "y": clusters[node_id]["y"]} for node_id in ordered_ids]
    if len(points) < 3:
        return None, ["ordered loop has fewer than 3 points."]
    return points, []

def _orient(a, b, c):
    return (float(b["x"])-float(a["x"]))*(float(c["y"])-float(a["y"])) - (float(b["y"])-float(a["y"]))*(float(c["x"])-float(a["x"]))

def _on_segment_xy(a, b, p, tol=1e-9):
    if abs(_orient(a, b, p)) > tol:
        return False
    return (min(float(a["x"]), float(b["x"])) - tol <= float(p["x"]) <= max(float(a["x"]), float(b["x"])) + tol and
            min(float(a["y"]), float(b["y"])) - tol <= float(p["y"]) <= max(float(a["y"]), float(b["y"])) + tol)

def _segments_intersect(a, b, c, d, tol=1e-9):
    if _on_segment_xy(a, b, c, tol) or _on_segment_xy(a, b, d, tol) or _on_segment_xy(c, d, a, tol) or _on_segment_xy(c, d, b, tol):
        return True
    o1 = _orient(a, b, c); o2 = _orient(a, b, d); o3 = _orient(c, d, a); o4 = _orient(c, d, b)
    return (o1 * o2 < -tol) and (o3 * o4 < -tol)

def _has_self_intersection(points):
    n = len(points)
    for i in range(n):
        a = points[i]; b = points[(i + 1) % n]
        for j in range(i + 1, n):
            if abs(i - j) <= 1 or (i == 0 and j == n - 1):
                continue
            if _segments_intersect(a, b, points[j], points[(j + 1) % n]):
                return True
    return False

def _point_in_polygon(point, polygon, tolerance_m=0.001):
    x = float(point["x"]); y = float(point["y"])
    inside = False
    n = len(polygon or [])
    for i in range(n):
        a = polygon[i]; b = polygon[(i + 1) % n]
        if _on_segment_xy(a, b, point, tolerance_m):
            return "boundary"
        yi = float(a["y"]); yj = float(b["y"])
        xi = float(a["x"]); xj = float(b["x"])
        if (yi > y) != (yj > y):
            x_intersect = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x_intersect > x:
                inside = not inside
    return "inside" if inside else "outside"

def _representative_point(points):
    if not points:
        return None
    # Use an actual loop vertex rather than a centroid so an outer loop around a hole
    # is not accidentally tested at a point inside that hole. Boundary cases against
    # other loops are handled by _point_in_polygon returning "boundary".
    return {"x": float(points[0]["x"]), "y": float(points[0]["y"])}

def _normalize_loop_winding(points, role):
    area = _signed_area_2d(points)
    if (role == "outer" and area < 0) or (role == "inner" and area > 0):
        points = list(reversed(points))
        area = _signed_area_2d(points)
    return points, area

def _segments_from_candidate(candidate):
    raw = list(candidate.get("endpoints_m") or candidate.get("endpoints_m_sample") or [])
    segments = []
    if len(raw) < 6 or len(raw) % 2 != 0:
        return [], ["candidate endpoint pairs are unavailable or incomplete; no formal loop generated."]
    for index in range(0, len(raw), 2):
        segments.append({"start": raw[index], "end": raw[index + 1]})
    return segments, []

def _formal_loop_from_candidate(candidate, tolerance_m=0.001):
    warnings = []
    segments, segment_warnings = _segments_from_candidate(candidate)
    if segment_warnings:
        return None, segment_warnings
    points, loop_warnings = _build_ordered_loop_from_segments(segments, tolerance_m)
    if loop_warnings:
        return None, loop_warnings
    if _has_self_intersection(points):
        warnings.append("formal loop candidate is self-intersecting.")
        return None, warnings
    area = _signed_area_2d(points)
    if abs(area) <= tolerance_m * tolerance_m:
        warnings.append("formal loop candidate has near-zero area.")
        return None, warnings
    return {"points_m": points, "closed": True, "area_m2_signed_original": area, "area_m2": abs(area), "orientation_original": "ccw" if area > 0 else "cw", "role": "unknown", "source_candidate_index": candidate.get("candidate_index"), "source_caster_index": candidate.get("caster_index"), "source_face_index": candidate.get("source_face_index"), "source_loop_index": candidate.get("loop_index"), "point_count": len(points), "units": "meter"}, warnings

def _assign_loop_roles_for_group(loops, tolerance_m=0.001):
    warnings = []
    for loop in loops:
        loop["role"] = "unknown"
        loop["containment_depth"] = None
    for index, loop in enumerate(loops):
        rep = _representative_point(loop.get("points_m") or [])
        if rep is None:
            warnings.append("loop {0} has no representative point; role is unknown.".format(index))
            continue
        depth = 0
        unknown = False
        for other_index, other in enumerate(loops):
            if other_index == index:
                continue
            relation = _point_in_polygon(rep, other.get("points_m") or [], tolerance_m)
            if relation == "boundary":
                unknown = True
                warnings.append("loop {0} representative point lies on loop {1} boundary; role is unknown.".format(index, other_index))
                break
            if relation == "inside":
                depth += 1
        if unknown:
            continue
        loop["containment_depth"] = depth
        loop["role"] = "outer" if depth % 2 == 0 else "inner"
        points, normalized_area = _normalize_loop_winding(loop.get("points_m") or [], loop["role"])
        loop["points_m"] = points
        loop["area_m2_signed"] = normalized_area
        loop["orientation"] = "ccw" if normalized_area > 0 else "cw"
    return warnings

def _build_formal_footprints_from_candidates(items, tolerance_m=0.001):
    polygons = []
    invalid = []
    warnings = []
    caster_count = 0
    successful_casters = set()
    failed_casters = set()
    accepted_caster_indexes = []
    groups = {}
    for item in items or []:
        if not item.get("accepted_shadow_caster"):
            continue
        caster_index = item.get("index")
        caster_count += 1
        accepted_caster_indexes.append(caster_index)
        item_success = False
        item_candidates = ((item.get("footprint_extraction") or {}).get("candidates") or [])
        if not item_candidates:
            failed_casters.add(caster_index)
            invalid.append({"caster_index": caster_index, "candidate_index": None, "reasons": ["accepted caster has no footprint candidate."]})
            continue
        for candidate in item_candidates:
            c = dict(candidate)
            c["caster_index"] = caster_index
            loop, lw = _formal_loop_from_candidate(c, tolerance_m)
            if loop is None:
                invalid.append({"caster_index": caster_index, "candidate_index": candidate.get("candidate_index"), "source_face_index": candidate.get("source_face_index"), "source_loop_index": candidate.get("loop_index"), "reasons": lw})
            else:
                group_key = (caster_index, candidate.get("source_face_index"))
                groups.setdefault(group_key, []).append(loop)
                item_success = True
            warnings.extend(lw)
        if item_success:
            successful_casters.add(caster_index)
        else:
            failed_casters.add(caster_index)
    for group_key in sorted(groups.keys(), key=lambda value: (str(value[0]), str(value[1]))):
        group_loops = groups[group_key]
        role_warnings = _assign_loop_roles_for_group(group_loops, tolerance_m)
        warnings.extend(role_warnings)
        for loop in group_loops:
            loop["polygon_index"] = len(polygons)
            polygons.append(loop)
    for caster_index in accepted_caster_indexes:
        if caster_index not in successful_casters:
            failed_casters.add(caster_index)
    complete = caster_count > 0 and len(successful_casters) == caster_count and len(invalid) == 0 and all(p.get("role") != "unknown" for p in polygons)
    partial_success = bool(polygons) and not complete
    return {"available": bool(polygons), "complete": complete, "partial_success": partial_success, "caster_count": caster_count, "successful_caster_count": len(successful_casters), "failed_caster_count": len(failed_casters), "polygon_count": len(polygons), "outer_loop_count": sum(1 for p in polygons if p.get("role") == "outer"), "inner_loop_count": sum(1 for p in polygons if p.get("role") == "inner"), "unknown_loop_count": sum(1 for p in polygons if p.get("role") == "unknown"), "invalid_loop_count": len(invalid), "items": polygons, "invalid_loops": invalid, "boolean_union_performed": False, "ready_for_shadow_projection_input": complete, "warnings": warnings}

def _build_footprint_extraction_summary(shadow_caster_geometry, measurement_plane, settings_normalized, site_boundary):
    items = (shadow_caster_geometry or {}).get("items") or []
    accepted = (shadow_caster_geometry or {}).get("accepted_caster_count", 0)
    candidates=[]; best=[]; with_c=[]; without=[]; warnings=[]
    for item in items:
        fp=item.get("footprint_extraction") or {}
        if item.get("accepted_shadow_caster"):
            if fp.get("candidates"):
                with_c.append(item.get("index")); candidates.extend(fp.get("candidates") or [])
            else:
                without.append(item.get("index"))
            if fp.get("best_candidate"):
                best.append(fp.get("best_candidate"))
        warnings.extend(fp.get("warnings") or [])
    closed=sum(1 for c in candidates if c.get("closed_candidate") is True)
    settings_ready=((settings_normalized or {}).get("readiness") or {}).get("ready_for_equal_time_shadow_calculation") is True
    mp_ready=((measurement_plane or {}).get("readiness") or {}).get("measurement_plane_constructed") is True
    site_ready=(site_boundary or {}).get("boundary_dependent_steps_available") is True
    ready_poly=accepted>0 and closed>0
    blockers_poly=[]
    if accepted<=0: blockers_poly.append("No accepted shadow caster proxy elements are available.")
    if closed<=0: blockers_poly.append("No closed footprint loop candidate was verified by raw endpoint comparison.")
    blockers_proj=list(blockers_poly)
    if not mp_ready: blockers_proj.append("Measurement plane is not constructed; future shadow projection context is blocked.")
    if not settings_ready: blockers_proj.append("Settings are not ready for future equal-time shadow calculation.")
    blockers_legal=["site boundary loop extraction is not implemented", "own-site exclusion mask is not implemented", "target area mask is not implemented", "ordinance profile / beyond-5m legal range are not implemented"]
    if not site_ready: blockers_legal.append("site_boundary is missing or not usable; future legal judgement masks are blocked, but footprint diagnostics continue.")
    formal_footprints = _build_formal_footprints_from_candidates(items)
    warnings.extend(formal_footprints.get("warnings") or [])
    return {"policy": FOOTPRINT_EXTRACTION_POLICY, "provided": accepted>0, "diagnostic_only": not (formal_footprints.get("available") is True), "formal_footprint_polygon_generated": formal_footprints.get("available") is True, "formal_footprints": formal_footprints, "count": len(items), "accepted_caster_count": accepted, "candidate_count": len(candidates), "loop_candidate_count": (shadow_caster_geometry or {}).get("footprint_loop_candidate_count", len(candidates)), "closed_loop_candidate_count": closed, "casters_with_candidates": with_c, "casters_without_candidates": without, "best_candidates": best, "readiness": {"footprint_diagnostics_ready": True, "ready_for_future_footprint_polygon_generation": formal_footprints.get("available") is True and formal_footprints.get("complete") is True, "ready_for_future_shadow_projection": formal_footprints.get("ready_for_shadow_projection_input") is True and mp_ready and settings_ready, "ready_for_future_legal_judgement_masks": False, "blockers_for_future_footprint_polygon_generation": blockers_poly, "blockers_for_future_shadow_projection": blockers_proj, "blockers_for_future_legal_judgement_masks": blockers_legal}, "warnings": warnings, "info": ["Formal footprint loops are generated from accepted Mass / Generic Model bottom-face edge-loop candidates only; BoundingBox is not used as footprint geometry.", "Multiple caster loops are preserved separately for future logical union; no Revit elements, CurveLoops, offsets, booleans, shadow polygons, or legal judgement are created.", "site_boundary is not required for footprint generation, but is required later for legal judgement masks."]}
