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
            candidates.append({"candidate_index":len(candidates),"source":"bottom_face_candidate_edge_loop","source_face_index":idx,"source_face_type":fs.get("type"),"source_face_area_raw":fs.get("area_raw"),"source_face_origin_raw":fs.get("origin_raw"),"source_face_normal_raw":fs.get("normal_raw"),"loop_index":loop.get("loop_index"),"edge_count":loop.get("edge_count"),"curve_count":loop.get("curve_count"),"closed_candidate":loop.get("closed_candidate"),"horizontal_candidate":loop.get("horizontal_candidate"),"z_min_raw":loop.get("z_min_raw"),"z_max_raw":loop.get("z_max_raw"),"z_min_m":loop.get("z_min_m"),"z_max_m":loop.get("z_max_m"),"z_variation_raw":loop.get("z_variation_raw"),"total_length_raw":loop.get("total_length_raw"),"total_length_m":loop.get("total_length_m"),"curve_types":loop.get("curve_types"),"endpoints_raw_sample":loop.get("endpoints_raw_sample"),"endpoints_m_sample":loop.get("endpoints_m_sample"),"formal_footprint_polygon_generated":False,"units":"revit_raw_internal_units","relation_to_measurement_plane":{"measurement_plane_available":(measurement_plane or {}).get("available") is True,"diagnostic_only":True,"meter_comparison_available": (measurement_plane or {}).get("available") is True and loop.get("z_min_m") is not None,"meter_relation_candidate": "diagnostic_candidate_only","unit_conversion_status":"diagnostic_conversion_available","used_for_legal_judgement":False,"used_for_shadow_geometry":False,"formal_intersection_test_performed":False},"warnings":loop.get("warnings") or []})
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
    return {"policy": FOOTPRINT_EXTRACTION_POLICY, "provided": accepted>0, "diagnostic_only": True, "formal_footprint_polygon_generated": False, "count": len(items), "accepted_caster_count": accepted, "candidate_count": len(candidates), "loop_candidate_count": (shadow_caster_geometry or {}).get("footprint_loop_candidate_count", len(candidates)), "closed_loop_candidate_count": closed, "casters_with_candidates": with_c, "casters_without_candidates": without, "best_candidates": best, "readiness": {"footprint_diagnostics_ready": True, "ready_for_future_footprint_polygon_generation": ready_poly, "ready_for_future_shadow_projection": ready_poly and mp_ready and settings_ready, "ready_for_future_legal_judgement_masks": False, "blockers_for_future_footprint_polygon_generation": blockers_poly, "blockers_for_future_shadow_projection": blockers_proj, "blockers_for_future_legal_judgement_masks": blockers_legal}, "warnings": warnings, "info": ["Footprint candidates are Revit raw_internal_units diagnostics with meter-converted fields; no formal footprint polygon or CurveLoop is generated.", "site_boundary is not required for footprint diagnostics, but is required later for legal judgement masks.", "Same-site multiple buildings awareness is retained for future duration accumulation; no caster union is performed in this PR."]}
