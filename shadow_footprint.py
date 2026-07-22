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

def _orient(a, b, c):
    return (float(b["x"])-float(a["x"]))*(float(c["y"])-float(a["y"])) - (float(b["y"])-float(a["y"]))*(float(c["x"])-float(a["x"]))

def _segments_intersect(a, b, c, d, tol=1e-9):
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


def _dedupe_text(values):
    out = []
    seen = set()
    for value in values or []:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out

def _candidate_has_only_line_edges(candidate):
    if candidate.get("has_arc_or_non_line_curve") is True:
        return False, ["formal footprint generation currently supports Line edges only; Arc/Spline/non-Line curve detected."]
    curve_types = candidate.get("curve_types")
    if not curve_types:
        return False, ["formal footprint generation currently supports Line edges only; curve types were not verified."]
    non_line = [ct for ct in curve_types if not _is_line_curve_type_name(ct)]
    if non_line:
        return False, ["formal footprint generation currently supports Line edges only; Arc/Spline/non-Line curve detected."]
    return True, []

def _candidate_is_verified_horizontal(candidate):
    if candidate.get("horizontal_candidate") is not True:
        return False, ["formal footprint generation requires a verified horizontal edge loop."]
    return True, []

def _validate_formal_candidate_eligibility(candidate):
    reasons = []
    line_ok, line_reasons = _candidate_has_only_line_edges(candidate)
    horizontal_ok, horizontal_reasons = _candidate_is_verified_horizontal(candidate)
    reasons.extend(line_reasons)
    reasons.extend(horizontal_reasons)
    return line_ok and horizontal_ok, _dedupe_text(reasons)

def _distance_xy(a, b):
    return ((float(a["x"]) - float(b["x"])) ** 2 + (float(a["y"]) - float(b["y"])) ** 2) ** 0.5

def _point_key_xy(point, tol):
    return (round(float(point["x"]) / tol), round(float(point["y"]) / tol))

def _normalize_xy_point(point):
    if point is None or point.get("x") is None or point.get("y") is None:
        return None
    return {"x": float(point.get("x")), "y": float(point.get("y"))}

def _stitch_loop_segments(raw_points, tolerance_m):
    if len(raw_points) < 6 or len(raw_points) % 2 != 0:
        return None, ["candidate endpoint sequence is unavailable or incomplete; no formal loop generated."]
    segments = []
    degree = {}
    seen_edges = set()
    for i in range(0, len(raw_points), 2):
        a = _normalize_xy_point(raw_points[i]); b = _normalize_xy_point(raw_points[i + 1])
        if a is None or b is None:
            return None, ["loop contains an invalid point; no formal loop generated."]
        if _distance_xy(a, b) <= tolerance_m:
            return None, ["formal loop candidate contains an extremely short edge."]
        ka = _point_key_xy(a, tolerance_m); kb = _point_key_xy(b, tolerance_m)
        edge_key = tuple(sorted([ka, kb]))
        if edge_key in seen_edges:
            return None, ["segment graph contains a duplicate edge."]
        seen_edges.add(edge_key)
        segments.append({"a": a, "b": b, "ka": ka, "kb": kb, "used": False})
        degree[ka] = degree.get(ka, 0) + 1; degree[kb] = degree.get(kb, 0) + 1
    bad_degree = [k for k, v in degree.items() if v != 2]
    if bad_degree:
        if any(v > 2 for v in degree.values()):
            return None, ["segment graph contains a branch vertex."]
        return None, ["segment graph is open or disconnected; endpoints do not form one closed loop."]
    ordered = [segments[0]["a"], segments[0]["b"]]
    segments[0]["used"] = True
    current = segments[0]["kb"]
    start = segments[0]["ka"]
    for _ in range(len(segments) - 1):
        matches = [seg for seg in segments if not seg["used"] and (seg["ka"] == current or seg["kb"] == current)]
        if len(matches) != 1:
            return None, ["segment graph is ambiguous or disconnected; loop stitching failed."]
        seg = matches[0]; seg["used"] = True
        if seg["ka"] == current:
            ordered.append(seg["b"]); current = seg["kb"]
        else:
            ordered.append(seg["a"]); current = seg["ka"]
    if current != start:
        return None, ["segment graph is open; stitched loop does not close."]
    if len(ordered) > 1 and _point_xy_equal(ordered[0], ordered[-1], tolerance_m):
        ordered = ordered[:-1]
    return ordered, []

def _point_in_polygon(point, polygon):
    x = float(point["x"]); y = float(point["y"]); inside = False
    n = len(polygon)
    for i in range(n):
        a = polygon[i]; b = polygon[(i + 1) % n]
        yi = float(a["y"]); yj = float(b["y"])
        if (yi > y) != (yj > y):
            x_cross = (float(b["x"]) - float(a["x"])) * (y - yi) / (yj - yi) + float(a["x"])
            if x < x_cross:
                inside = not inside
    return inside

def _normalize_loop_winding(loop, role):
    points = list(loop.get("points_m") or [])
    area = _signed_area_2d(points)
    want_ccw = role == "outer"
    if (area > 0) != want_ccw:
        points = list(reversed(points)); area = _signed_area_2d(points)
    loop["points_m"] = points
    loop["area_m2_signed"] = area
    loop["area_m2"] = abs(area)
    loop["orientation"] = "ccw" if area > 0 else "cw"
    loop["role"] = role
    return loop

def _classify_and_normalize_caster_loops(polygons):
    warnings = []
    by_caster = {}
    for poly in polygons:
        by_caster.setdefault(poly.get("source_caster_index"), []).append(poly)
    for caster_polygons in by_caster.values():
        for poly in caster_polygons:
            probe = (poly.get("points_m") or [None])[0]
            if probe is None:
                poly["role"] = "unknown"; warnings.append("unknown outer/inner role")
                continue
            depth = sum(1 for other in caster_polygons if other is not poly and _point_in_polygon(probe, other.get("points_m") or []))
            poly["containment_depth"] = depth
            _normalize_loop_winding(poly, "outer" if depth % 2 == 0 else "inner")
    return warnings

def _formal_loop_from_candidate(candidate, tolerance_m=0.001):
    warnings = []
    eligible, reasons = _validate_formal_candidate_eligibility(candidate)
    if not eligible:
        return None, reasons
    raw = list(candidate.get("endpoints_m") or candidate.get("endpoints_m_sample") or [])
    clean, stitch_warnings = _stitch_loop_segments(raw, tolerance_m)
    if clean is None:
        return None, stitch_warnings
    if len(clean) < 3:
        warnings.append("formal loop candidate has fewer than 3 unique XY points.")
        return None, warnings
    if _has_self_intersection(clean):
        warnings.append("formal loop candidate is self-intersecting.")
        return None, warnings
    area = _signed_area_2d(clean)
    if abs(area) <= tolerance_m * tolerance_m:
        warnings.append("formal loop candidate has near-zero area.")
        return None, warnings
    return {"points_m": clean, "closed": True, "area_m2_signed": area, "area_m2": abs(area), "orientation": "ccw" if area > 0 else "cw", "role": "unknown", "source_candidate_index": candidate.get("candidate_index"), "source_caster_index": candidate.get("caster_index"), "source_face_index": candidate.get("source_face_index"), "source_loop_index": candidate.get("loop_index"), "point_count": len(clean), "units": "meter"}, warnings

def _build_formal_footprints_from_candidates(items):
    polygons = []; invalid = []; warnings = []
    caster_count = 0
    successful_casters = set(); failed_casters = set(); accepted_casters = []
    for item in items or []:
        if not item.get("accepted_shadow_caster"):
            continue
        caster_index = item.get("index")
        caster_count += 1; accepted_casters.append(caster_index)
        caster_polygons_before = len(polygons)
        caster_invalid_before = len(invalid)
        candidates = ((item.get("footprint_extraction") or {}).get("candidates") or [])
        if not candidates:
            invalid.append({"caster_index": caster_index, "candidate_index": None, "source_face_index": None, "source_loop_index": None, "reasons": ["accepted caster has no valid formal footprint"]})
        for candidate in candidates:
            c = dict(candidate); c["caster_index"] = caster_index
            loop, lw = _formal_loop_from_candidate(c)
            if loop is None:
                invalid.append({"caster_index": caster_index, "candidate_index": candidate.get("candidate_index"), "source_face_index": candidate.get("source_face_index"), "source_loop_index": candidate.get("loop_index"), "reasons": lw})
            else:
                loop["polygon_index"] = len(polygons); polygons.append(loop)
            warnings.extend(lw)
        if len(polygons) > caster_polygons_before:
            successful_casters.add(caster_index)
        if len(invalid) > caster_invalid_before or len(polygons) == caster_polygons_before:
            failed_casters.add(caster_index)
    warnings.extend(_classify_and_normalize_caster_loops(polygons))
    unknown_roles = [p for p in polygons if p.get("role") == "unknown"]
    if unknown_roles:
        warnings.append("unknown outer/inner role")
    complete = bool(caster_count > 0 and polygons and not invalid and not unknown_roles and len(successful_casters) == caster_count)
    partial_success = bool(polygons and not complete)
    blocker_reasons = []
    for item in invalid:
        for reason in item.get("reasons") or []:
            if "Line edges only" in reason or "non-Line" in reason:
                blocker_reasons.append("non-Line edge loop is not supported")
            elif "horizontal" in reason:
                blocker_reasons.append("horizontal loop was not verified")
            elif "no valid formal footprint" in reason:
                blocker_reasons.append("accepted caster has no valid formal footprint")
            else:
                blocker_reasons.append("invalid or open segment graph")
    if unknown_roles:
        blocker_reasons.append("unknown outer/inner role")
    if partial_success:
        blocker_reasons.append("partial formal footprint generation only")
    for caster_index in accepted_casters:
        if caster_index not in successful_casters:
            blocker_reasons.append("accepted caster has no valid formal footprint")
    blocker_reasons = _dedupe_text(blocker_reasons)
    return {"available": bool(polygons), "complete": complete, "partial_success": partial_success, "caster_count": caster_count, "successful_caster_count": len(successful_casters), "failed_caster_count": len(failed_casters.union(set(accepted_casters) - successful_casters)), "polygon_count": len(polygons), "outer_loop_count": sum(1 for p in polygons if p.get("role") == "outer"), "inner_loop_count": sum(1 for p in polygons if p.get("role") == "inner"), "unknown_role_count": len(unknown_roles), "invalid_loop_count": len(invalid), "items": polygons, "invalid_loops": invalid, "blockers": blocker_reasons, "boolean_union_performed": False, "ready_for_shadow_projection_input": complete, "warnings": _dedupe_text(warnings)}

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
    blockers_poly.extend(formal_footprints.get("blockers") or [])
    if formal_footprints.get("partial_success"):
        blockers_poly.append("partial formal footprint generation only")
    blockers_poly = _dedupe_text(blockers_poly)
    blockers_proj = _dedupe_text(blockers_proj + blockers_poly)
    return {"policy": FOOTPRINT_EXTRACTION_POLICY, "provided": accepted>0, "diagnostic_only": formal_footprints.get("available") is not True, "formal_footprint_polygon_generated": formal_footprints.get("available") is True, "formal_footprints": formal_footprints, "count": len(items), "accepted_caster_count": accepted, "candidate_count": len(candidates), "loop_candidate_count": (shadow_caster_geometry or {}).get("footprint_loop_candidate_count", len(candidates)), "closed_loop_candidate_count": closed, "casters_with_candidates": with_c, "casters_without_candidates": without, "best_candidates": best, "readiness": {"footprint_diagnostics_ready": True, "ready_for_future_footprint_polygon_generation": formal_footprints.get("complete") is True, "ready_for_future_shadow_projection": formal_footprints.get("ready_for_shadow_projection_input") is True and mp_ready and settings_ready, "ready_for_future_legal_judgement_masks": False, "blockers_for_future_footprint_polygon_generation": blockers_poly, "blockers_for_future_shadow_projection": blockers_proj, "blockers_for_future_legal_judgement_masks": blockers_legal}, "warnings": _dedupe_text(warnings), "info": ["Formal footprint loops are generated from accepted Mass / Generic Model bottom-face Line edge-loop candidates only; Arc/Spline/non-Line and unverified-horizontal loops are rejected.", "Multiple caster loops are preserved separately for future logical union; no Revit elements, CurveLoops, offsets, booleans, shadow polygons, or legal judgement are created.", "site_boundary is not required for footprint generation, but is required later for legal judgement masks."]}
