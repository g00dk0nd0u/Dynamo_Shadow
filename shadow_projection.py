# Diagnostic-only shadow projection point-cloud output.
# No formal shadow polygons, contours, legal masks, clipping, or Revit elements.

from shadow_policies import SHADOW_PROJECTION_POLICY


def _safe_float(value):
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _round(value, digits=6):
    number = _safe_float(value)
    if number is None:
        return None
    return round(number, digits)


def _point_key(point):
    try:
        return (
            round(float(point.get("x")), 6),
            round(float(point.get("y")), 6),
            round(float(point.get("z")), 6),
            str(point.get("source")),
        )
    except Exception:
        return None


def _append_point(points, seen, point, source, caster_index):
    if not isinstance(point, dict):
        return
    x = _safe_float(point.get("x"))
    y = _safe_float(point.get("y"))
    z = _safe_float(point.get("z"))
    if x is None or y is None or z is None:
        return
    candidate = {
        "x_m": _round(x),
        "y_m": _round(y),
        "z_m": _round(z),
        "source": source,
        "caster_index": caster_index,
    }
    key = _point_key({"x": x, "y": y, "z": z, "source": source})
    if key in seen:
        return
    seen.add(key)
    points.append(candidate)


def _collect_diagnostic_geometry_points(shadow_caster_geometry):
    points = []
    seen = set()
    used_preferred = False
    used_fallback = False
    skipped_symbol_fallback_count = 0
    for item in (shadow_caster_geometry or {}).get("items") or []:
        if item.get("accepted_shadow_caster") is not True:
            continue
        caster_index = item.get("index")
        source_points = item.get("diagnostic_source_points_m") or []
        if source_points:
            used_preferred = True
            for point_index, point in enumerate(source_points):
                source = point.get("source") or "diagnostic_source_points_m:{0}".format(point_index)
                _append_point(points, seen, point, source, caster_index)
            continue
        if item.get("legacy_projection_fallback_allowed") is False:
            skipped_symbol_fallback_count += 1
            continue
        used_fallback = True
        for face_index, face in enumerate(item.get("faces_summary") or []):
            _append_point(points, seen, face.get("origin_m"), "face_origin_m:{0}".format(face_index), caster_index)
        for edge_index, edge in enumerate(item.get("edges_summary_sample") or []):
            _append_point(points, seen, edge.get("endpoint0_m"), "edge_endpoint0_m:{0}".format(edge_index), caster_index)
            _append_point(points, seen, edge.get("endpoint1_m"), "edge_endpoint1_m:{0}".format(edge_index), caster_index)
        footprint = item.get("footprint_extraction") or {}
        for candidate_index, candidate in enumerate(footprint.get("candidates") or []):
            for point_index, point in enumerate(candidate.get("endpoints_m_sample") or []):
                _append_point(points, seen, point, "footprint_endpoint_m:{0}:{1}".format(candidate_index, point_index), caster_index)
    if skipped_symbol_fallback_count and not used_preferred and not used_fallback:
        strategy = "symbol_geometry_only_casters_skipped"
    elif skipped_symbol_fallback_count and used_preferred and not used_fallback:
        strategy = "diagnostic_source_points_m_with_symbol_geometry_only_casters_skipped"
    elif skipped_symbol_fallback_count and used_fallback:
        strategy = "diagnostic_source_points_m_or_legacy_fallback_with_symbol_geometry_only_casters_skipped"
    else:
        strategy = "diagnostic_source_points_m" if used_preferred and not used_fallback else "diagnostic_source_points_m_with_legacy_fallback" if used_preferred else "legacy_faces_edges_footprint_fallback"
    return points, strategy, skipped_symbol_fallback_count


def _projected_output_cap(shadow_caster_geometry):
    try:
        value = ((shadow_caster_geometry or {}).get("settings_caps") or {}).get("max_projected_points_output_per_slice")
        return max(1, int(value or 300))
    except Exception:
        return 300


def _extent_from_points(points):
    if not points:
        return None
    xs = [p.get("x_m") for p in points if p.get("x_m") is not None]
    ys = [p.get("y_m") for p in points if p.get("y_m") is not None]
    zs = [p.get("z_m") for p in points if p.get("z_m") is not None]
    if not xs or not ys:
        return None
    return {
        "min_x_m": _round(min(xs)),
        "max_x_m": _round(max(xs)),
        "min_y_m": _round(min(ys)),
        "max_y_m": _round(max(ys)),
        "min_z_m": _round(min(zs)) if zs else None,
        "max_z_m": _round(max(zs)) if zs else None,
    }


def _vertical_delta_to_measurement_plane(point, measurement_plane_elevation_m):
    z = _safe_float(point.get("z_m"))
    plane_z = _safe_float(measurement_plane_elevation_m)
    if z is None or plane_z is None:
        return None
    return z - plane_z


def _project_point(point, measurement_plane_elevation_m, direction, length_factor):
    z = _safe_float(point.get("z_m"))
    x = _safe_float(point.get("x_m"))
    y = _safe_float(point.get("y_m"))
    dx = _safe_float((direction or {}).get("x_east"))
    dy = _safe_float((direction or {}).get("y_north"))
    factor = _safe_float(length_factor)
    plane_z = _safe_float(measurement_plane_elevation_m)
    vertical_delta_m = _vertical_delta_to_measurement_plane(point, measurement_plane_elevation_m)
    if None in (z, x, y, dx, dy, factor, plane_z, vertical_delta_m):
        return None
    if vertical_delta_m <= 0.0:
        return None
    horizontal_offset_m = vertical_delta_m * factor
    return {
        "source_caster_index": point.get("caster_index"),
        "source": point.get("source"),
        "source_point_m": {"x_m": point.get("x_m"), "y_m": point.get("y_m"), "z_m": point.get("z_m")},
        "vertical_delta_to_measurement_plane_m": _round(vertical_delta_m),
        "projected_point_m": {
            "x_m": _round(x + dx * horizontal_offset_m),
            "y_m": _round(y + dy * horizontal_offset_m),
            "z_m": _round(plane_z),
        },
    }


def _build_shadow_projection_diagnostics(shadow_caster_geometry, measurement_plane, sun_time_slices):
    warnings = []
    plane_z = _safe_float((measurement_plane or {}).get("elevation_m"))
    if plane_z is None:
        warnings.append("measurement_plane.elevation_m is missing; diagnostic shadow projection point cloud is skipped non-fatally.")
    points, source_strategy, skipped_symbol_fallback_count = _collect_diagnostic_geometry_points(shadow_caster_geometry)
    projected_output_cap = _projected_output_cap(shadow_caster_geometry)
    if not points:
        warnings.append("No meter-based diagnostic geometry points are available; diagnostic shadow projection point cloud is skipped non-fatally.")
    slices = sun_time_slices or []
    if not slices:
        warnings.append("sun_time_slices is empty; diagnostic shadow projection point cloud is skipped non-fatally.")

    projectable_points = []
    skipped_point_count = 0
    if plane_z is not None:
        for point in points:
            vertical_delta_m = _vertical_delta_to_measurement_plane(point, plane_z)
            if vertical_delta_m is None:
                continue
            if vertical_delta_m <= 0.0:
                skipped_point_count += 1
            else:
                projectable_points.append(point)

    slice_outputs = []
    if plane_z is not None and points and slices:
        for index, sun_slice in enumerate(slices):
            direction = sun_slice.get("shadow_direction_vector") if isinstance(sun_slice, dict) else None
            factor = sun_slice.get("shadow_length_factor") if isinstance(sun_slice, dict) else None
            projected = []
            slice_warnings = []
            if not direction or factor is None:
                slice_warnings.append("shadow_direction_vector or shadow_length_factor is unavailable for this slice; projection skipped.")
            else:
                for point in projectable_points:
                    pp = _project_point(point, plane_z, direction, factor)
                    if pp is not None:
                        projected.append(pp)
            projected_points = [p.get("projected_point_m") for p in projected]
            projected_output = projected[:projected_output_cap]
            slice_outputs.append({
                "slice_index": index,
                "true_solar_time": sun_slice.get("true_solar_time"),
                "diagnostic_only": True,
                "shadow_direction_vector": direction,
                "shadow_length_factor": factor,
                "source_point_count": len(points),
                "skipped_point_count_below_or_on_measurement_plane": skipped_point_count,
                "projectable_source_point_count": len(projectable_points),
                "projected_point_count": len(projected),
                "projected_points": projected_output,
                "projected_points_truncated": len(projected) > len(projected_output),
                "max_projected_points_output_per_slice": projected_output_cap,
                "projected_extent_m": _extent_from_points(projected_points),
                "warnings": slice_warnings,
            })

    return {
        "available": bool(slice_outputs),
        "diagnostic_only": True,
        "formal_shadow_polygons_generated": False,
        "equal_time_contours_generated": False,
        "legal_masks_generated": False,
        "site_boundary_clipping_performed": False,
        "legal_judgement_generated": False,
        "revit_elements_created": False,
        "measurement_plane_elevation_m": _round(plane_z),
        "source_geometry_point_strategy": source_strategy,
        "geometry_instance_source_strategy": (shadow_caster_geometry or {}).get("geometry_instance_source_strategy"),
        "legacy_projection_fallback_skipped_due_to_symbol_geometry": skipped_symbol_fallback_count,
        "source_geometry_point_count": len(points),
        "skipped_point_count_below_or_on_measurement_plane": skipped_point_count,
        "projectable_source_point_count": len(projectable_points),
        "source_geometry_extent_m": _extent_from_points(points),
        "slice_count": len(slice_outputs),
        "slices": slice_outputs,
        "warnings": warnings,
    }, SHADOW_PROJECTION_POLICY
