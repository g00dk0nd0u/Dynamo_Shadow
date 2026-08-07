"""Deterministic resampling of approximate reverse-shadow measurement lines."""
import math


def _area(points):
    return 0.5 * sum(points[i][0] * points[(i+1) % len(points)][1] -
                     points[(i+1) % len(points)][0] * points[i][1] for i in range(len(points)))


def _normalise(contour):
    raw = contour.get("points_m") or []
    points = [(float(p.get("x", p.get("x_m"))), float(p.get("y", p.get("y_m")))) for p in raw]
    if len(points) > 1 and math.hypot(points[0][0]-points[-1][0], points[0][1]-points[-1][1]) <= 1e-8:
        points.pop()
    if _area(points) < 0:
        points.reverse()
    start = min(range(len(points)), key=lambda i: points[i])
    return points[start:] + points[:start]


def _resample(points, spacing):
    lengths = [math.hypot(points[(i+1)%len(points)][0]-p[0], points[(i+1)%len(points)][1]-p[1])
               for i, p in enumerate(points)]
    perimeter = sum(lengths)
    targets = [i * spacing for i in range(max(1, int(math.floor((perimeter - 1e-9) / spacing)) + 1))]
    output, edge, base = [], 0, 0.0
    for target in targets:
        while edge < len(lengths)-1 and target > base + lengths[edge] + 1e-10:
            base += lengths[edge]; edge += 1
        t = 0.0 if lengths[edge] == 0 else (target-base)/lengths[edge]
        a, b = points[edge], points[(edge+1)%len(points)]
        output.append((a[0]+t*(b[0]-a[0]), a[1]+t*(b[1]-a[1]), target))
    return output, perimeter


def build_reverse_shadow_measurement_points(site_distance_contours, spacing_m):
    base = {"available": False, "complete": False, "method": "grid_distance_contour_resampling_v1",
            "spacing_m": spacing_m, "near": {"distance_m": 5.0, "contour_count": 0, "point_count": 0, "points": []},
            "far": {"distance_m": 10.0, "contour_count": 0, "point_count": 0, "points": []},
            "total_point_count": 0, "blockers": [], "warnings": [],
            "legal_judgement_generated": False, "ordinance_selection_certified": False,
            "permit_ready_certified": False}
    try: spacing = float(spacing_m)
    except Exception: spacing = 0.0
    if not math.isfinite(spacing) or spacing < 1.0:
        base["blockers"].append({"failure_code": "invalid_reverse_shadow_measurement_spacing"}); return base
    if not (site_distance_contours or {}).get("complete"):
        base["blockers"].append({"failure_code": "complete_site_distance_contours_required"}); return base
    prepared = []
    for contour in site_distance_contours.get("contours") or []:
        if not contour.get("closed") or contour.get("distance_m") not in (5.0, 10.0): continue
        try: points = _normalise(contour)
        except Exception: continue
        if len(points) >= 3:
            prepared.append((float(contour["distance_m"]), -abs(_area(points)), min(p[0] for p in points),
                             min(p[1] for p in points), int(contour.get("contour_index", 0)), points))
    prepared.sort(key=lambda x: x[:5])
    global_index = 0
    seen_by_zone = {"near": set(), "far": set()}
    duplicate_tolerance = 1e-8
    for distance, _, _, _, contour_index, points in prepared:
        zone_name = "near" if distance == 5.0 else "far"
        zone = base[zone_name]
        zone["contour_count"] += 1
        samples, perimeter = _resample(points, spacing)
        for x, y, along in samples:
            key = (round(x / duplicate_tolerance), round(y / duplicate_tolerance))
            if key in seen_by_zone[zone_name]:
                continue
            seen_by_zone[zone_name].add(key)
            item = {"measurement_point_index": global_index, "contour_index": contour_index,
                    "distance_along_contour_m": along, "x_m": x, "y_m": y}
            zone["points"].append(item); global_index += 1
        zone["point_count"] = len(zone["points"])
    base["total_point_count"] = global_index
    if not base["near"]["point_count"] or not base["far"]["point_count"]:
        base["blockers"].append({"failure_code": "reverse_shadow_measurement_points_missing"}); return base
    base.update({"available": True, "complete": True})
    return base
