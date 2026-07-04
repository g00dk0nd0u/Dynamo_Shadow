# script.py
# Revit / Dynamo external script
# Filled Region内のFurnitureを集計し、固定ファイル名でDownloadsへ上書き出力する

OUT = {
    "success": False,
    "status": "script.py started but did not finish",
    "script_path": __file__ if "__file__" in globals() else ""
}

import clr
import os
import csv
import re
import traceback
from datetime import datetime
from collections import defaultdict

clr.AddReference("RevitServices")
from RevitServices.Persistence import DocumentManager

clr.AddReference("RevitAPI")
from Autodesk.Revit.DB import (
    FilteredElementCollector,
    BuiltInCategory,
    BuiltInParameter,
    FilledRegion,
    View,
    LocationPoint,
    LocationCurve,
    XYZ
)

from System import Environment

doc = DocumentManager.Instance.CurrentDBDocument
uidoc = DocumentManager.Instance.CurrentUIApplication.ActiveUIDocument

# ------------------------------------------------------------
# Inputs
# ------------------------------------------------------------
# IN[0] = 対象View / Viewリスト / 空ならActive View
# IN[1] = Filled Region Type名フィルタ / 空なら全Type
# IN[2] = ファイル名prefix / 空なら revit_filledregion_furniture_count
# IN[3] = 未割当家具も出す True/False / 空なら True
# IN[4] = 家具判定点をBBox中心にする True/False / 空なら False

def get_in(index, default=None):
    try:
        if len(IN) > index and IN[index] is not None:
            return IN[index]
    except:
        pass
    return default

try:
    unwrap = UnwrapElement
except:
    unwrap = lambda x: x

try:
    string_types = (basestring,)
except:
    string_types = (str,)

def to_list(x):
    if x is None:
        return []
    if isinstance(x, string_types):
        return [x]
    try:
        return list(x)
    except:
        return [x]

def to_bool(x, default=True):
    if x is None:
        return default
    if isinstance(x, bool):
        return x
    s = str(x).strip().lower()
    if s in ["true", "1", "yes", "y"]:
        return True
    if s in ["false", "0", "no", "n"]:
        return False
    return default

input_views_raw = [unwrap(x) for x in to_list(get_in(0, None))]
region_type_filter = get_in(1, None)
file_prefix = get_in(2, "FunitureDashBoard")
include_unassigned = to_bool(get_in(3, True), True)
use_bbox_center = to_bool(get_in(4, False), False)

region_type_filter = str(region_type_filter).strip() if region_type_filter else None
file_prefix = re.sub(r'[\\/:*?"<>|]+', "_", str(file_prefix or "revit_filledregion_furniture_count"))

generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ------------------------------------------------------------
# Columns
# ------------------------------------------------------------

GFLZ_PARAM_NAMES = [
    "gFLZ_DEPARTMENT",
    "gFLZ_FUNCTION OF SPACE",
    "gFLZ_OCCUPANCY CLASSIFICATION",
    "gFLZ_SPACE NAME",
    "gFLZ_SPACE TYPE"
]

CSV_FIELDNAMES = [
    "Level",
    "Region ElementId",
    "Region Type",
    "gFLZ_DEPARTMENT",
    "gFLZ_FUNCTION OF SPACE",
    "gFLZ_OCCUPANCY CLASSIFICATION",
    "gFLZ_SPACE NAME",
    "gFLZ_SPACE TYPE",
    "Furniture Family",
    "Furniture Type",
    "Count"
]

# ------------------------------------------------------------
# Logs
# ------------------------------------------------------------

warnings = []
errors = []
log_lines = []
unassigned_samples = []

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_lines.append("[{}] {}".format(ts, msg))

def add_warning(msg):
    msg = str(msg)
    warnings.append(msg)
    log("WARNING: " + msg)

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def eid_int(eid):
    if eid is None:
        return -1
    try:
        return int(eid.IntegerValue)
    except:
        try:
            return int(eid.Value)
        except:
            return -1

def safe_name(elem):
    if elem is None:
        return ""
    try:
        return elem.Name or ""
    except:
        pass
    try:
        p = elem.get_Parameter(BuiltInParameter.SYMBOL_NAME_PARAM)
        if p and p.HasValue:
            return p.AsString() or p.AsValueString() or ""
    except:
        pass
    return ""

def get_bip(name):
    try:
        return getattr(BuiltInParameter, name)
    except:
        return None

def get_param_str(elem, bip_name):
    bip = get_bip(bip_name)
    if bip is None or elem is None:
        return ""
    try:
        p = elem.get_Parameter(bip)
        if p and p.HasValue:
            return p.AsString() or p.AsValueString() or ""
    except:
        pass
    return ""

def get_lookup_param_str(elem, param_name):
    try:
        p = elem.LookupParameter(param_name)
        if p and p.HasValue:
            return p.AsString() or p.AsValueString() or ""
    except:
        pass
    return ""

def get_gflz_values(elem):
    data = {}
    for name in GFLZ_PARAM_NAMES:
        data[name] = get_lookup_param_str(elem, name)
    return data

def get_level_name_from_view(view):
    try:
        if view.GenLevel:
            return view.GenLevel.Name
    except:
        pass

    try:
        p = view.get_Parameter(BuiltInParameter.PLAN_VIEW_LEVEL)
        if p and p.HasValue:
            lvl = doc.GetElement(p.AsElementId())
            if lvl:
                return safe_name(lvl)
    except:
        pass

    return ""

def get_family_and_type(fi):
    family_name = ""
    type_name = ""

    try:
        symbol = fi.Symbol
    except:
        symbol = None

    if symbol:
        try:
            family_name = symbol.FamilyName or ""
        except:
            pass
        type_name = get_param_str(symbol, "SYMBOL_NAME_PARAM") or safe_name(symbol)

    if not family_name:
        family_name = get_param_str(fi, "ELEM_FAMILY_PARAM")
    if not type_name:
        type_name = get_param_str(fi, "ELEM_TYPE_PARAM")

    return family_name, type_name

def get_region_type_name(fr):
    try:
        t = doc.GetElement(fr.GetTypeId())
        return safe_name(t)
    except:
        return ""

def is_valid_view(v):
    try:
        return isinstance(v, View) and not v.IsTemplate
    except:
        return False

def get_target_views():
    views = []

    for v in input_views_raw:
        if is_valid_view(v):
            views.append(v)

    if not views:
        try:
            av = uidoc.ActiveView
            if is_valid_view(av):
                views.append(av)
        except:
            pass

    result = []
    seen = set()

    for v in views:
        vid = eid_int(v.Id)
        if vid not in seen:
            seen.add(vid)
            result.append(v)

    return result

def html_escape(value):
    s = "" if value is None else str(value)
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
         .replace("'", "&#39;")
    )

# ------------------------------------------------------------
# Geometry
# ------------------------------------------------------------

TOL = 0.001  # feet, about 0.3mm

def dist2_xy(a, b):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2

def point_on_segment(px, py, ax, ay, bx, by, tol=TOL):
    vx = bx - ax
    vy = by - ay
    wx = px - ax
    wy = py - ay

    seg_len2 = vx * vx + vy * vy
    if seg_len2 < tol * tol:
        return False

    cross = abs(vx * wy - vy * wx)
    if cross > tol * (seg_len2 ** 0.5):
        return False

    dot = wx * vx + wy * vy
    return -tol <= dot <= seg_len2 + tol

def point_in_loop(px, py, loop):
    inside = False
    n = len(loop)
    if n < 3:
        return False

    for i in range(n):
        ax, ay = loop[i]
        bx, by = loop[(i + 1) % n]

        if point_on_segment(px, py, ax, ay, bx, by):
            return True

        if (ay > py) != (by > py):
            x_int = (bx - ax) * (py - ay) / ((by - ay) if abs(by - ay) > 1e-12 else 1e-12) + ax
            if px < x_int:
                inside = not inside

    return inside

def point_in_region_loops(pt, loops):
    px = pt.X
    py = pt.Y

    inside = False
    for loop in loops:
        if point_in_loop(px, py, loop):
            inside = not inside

    return inside

def loop_area_abs(loop):
    if len(loop) < 3:
        return 0.0

    s = 0.0
    for i in range(len(loop)):
        x1, y1 = loop[i]
        x2, y2 = loop[(i + 1) % len(loop)]
        s += x1 * y2 - x2 * y1

    return abs(s) * 0.5

def get_filled_region_loops(fr):
    loops = []

    try:
        boundaries = fr.GetBoundaries()
    except Exception as ex:
        add_warning("Filled Region boundary error / RegionId {} / {}".format(eid_int(fr.Id), ex))
        return loops

    if boundaries is None:
        add_warning("Filled Region has no boundary / RegionId {}".format(eid_int(fr.Id)))
        return loops

    try:
        for curve_loop in boundaries:
            loop = []

            for curve in curve_loop:
                pts = list(curve.Tessellate())

                for p in pts:
                    xy = (p.X, p.Y)
                    if not loop or dist2_xy(loop[-1], xy) > TOL * TOL:
                        loop.append(xy)

            if len(loop) >= 3:
                if dist2_xy(loop[0], loop[-1]) <= TOL * TOL:
                    loop = loop[:-1]
                loops.append(loop)

    except Exception as ex:
        add_warning("Filled Region loop read error / RegionId {} / {}".format(eid_int(fr.Id), ex))

    return loops

def get_element_point(elem, view=None):
    try:
        if not use_bbox_center:
            loc = elem.Location

            if isinstance(loc, LocationPoint):
                return loc.Point

            if isinstance(loc, LocationCurve):
                return loc.Curve.Evaluate(0.5, True)
    except:
        pass

    try:
        bb = elem.get_BoundingBox(view)
        if bb:
            return XYZ(
                (bb.Min.X + bb.Max.X) * 0.5,
                (bb.Min.Y + bb.Max.Y) * 0.5,
                (bb.Min.Z + bb.Max.Z) * 0.5
            )
    except:
        pass

    try:
        bb = elem.get_BoundingBox(None)
        if bb:
            return XYZ(
                (bb.Min.X + bb.Max.X) * 0.5,
                (bb.Min.Y + bb.Max.Y) * 0.5,
                (bb.Min.Z + bb.Max.Z) * 0.5
            )
    except:
        pass

    return None

# ------------------------------------------------------------
# Output files
# ------------------------------------------------------------

def get_download_paths():
    # 実際にはDownloadsではなく、script.py = .dyn と同じフォルダへ出力する
    try:
        script_path = globals().get("__file__", None)

        if script_path and os.path.isfile(script_path):
            output_dir = os.path.dirname(os.path.abspath(script_path))
        else:
            raise Exception("__file__ is not available or invalid.")

    except Exception:
        # 最終フォールバック
        output_dir = r"C:\Users\22615\OneDrive - Gensler\_REVIT\Other\Other_Dynamo\Dynamo_FunitureDashBoard"

    if not os.path.isdir(output_dir):
        raise Exception("Output folder not found: {}".format(output_dir))

    csv_path = os.path.join(output_dir, "{}.csv".format(file_prefix))
    html_path = os.path.join(output_dir, "{}.html".format(file_prefix))
    log_path = os.path.join(output_dir, "{}_log.txt".format(file_prefix))
    
    return output_dir, csv_path, html_path, log_path

def write_log_file(success, csv_path=None, html_path=None, log_path=None):
    try:
        if not log_path:
            _, _, _, log_path = get_download_paths()

        lines = []
        lines.append("Revit Filled Region Furniture Count Log")
        lines.append("=" * 70)
        lines.append("Success: {}".format(success))
        lines.append("CSV Path: {}".format(csv_path or ""))
        lines.append("HTML Path: {}".format(html_path or ""))
        lines.append("Log Path: {}".format(log_path or ""))
        lines.append("Generated At: {}".format(generated_at))
        lines.append("Overwrite Fixed Files: True")
        lines.append("Revit Title: {}".format(doc.Title if doc else ""))

        try:
            lines.append("Revit Path: {}".format(doc.PathName))
        except:
            lines.append("Revit Path: ")

        lines.append("Region Type Filter: {}".format(region_type_filter or "ALL"))
        lines.append("Include Unassigned: {}".format(include_unassigned))
        lines.append("Use BBox Center: {}".format(use_bbox_center))
        lines.append("")

        lines.append("Execution Log")
        lines.append("-" * 70)
        lines.extend(log_lines)
        lines.append("")

        lines.append("Unassigned Furniture Samples")
        lines.append("-" * 70)
        lines.extend(unassigned_samples[:100] if unassigned_samples else ["None"])
        lines.append("")

        lines.append("Warnings")
        lines.append("-" * 70)
        lines.extend(warnings if warnings else ["None"])
        lines.append("")

        lines.append("Errors")
        lines.append("-" * 70)
        lines.extend(errors if errors else ["None"])

        with open(log_path, "w", encoding="utf-8-sig") as f:
            f.write("\n".join(lines))

        return log_path

    except Exception as ex:
        return "Log write failed: {}".format(ex)

def write_html_dashboard(html_path, rows, summary):
    total_count = sum([int(r.get("Count", 0)) for r in rows])

    by_level = defaultdict(int)
    by_region = defaultdict(int)
    by_furniture = defaultdict(int)

    for r in rows:
        c = int(r.get("Count", 0))
        by_level[r.get("Level", "")] += c

        region_label = (
            r.get("gFLZ_SPACE NAME", "") or
            r.get("gFLZ_SPACE TYPE", "") or
            r.get("gFLZ_FUNCTION OF SPACE", "") or
            r.get("Region Type", "")
        )
        by_region[region_label] += c

        furniture_label = "{} / {}".format(
            r.get("Furniture Family", ""),
            r.get("Furniture Type", "")
        )
        by_furniture[furniture_label] += c

    def simple_table(title, data_dict):
        items = sorted(data_dict.items(), key=lambda x: (-x[1], str(x[0])))
        html = []
        html.append("<h2>{}</h2>".format(html_escape(title)))
        html.append("<table>")
        html.append("<thead><tr><th>Name</th><th class='num'>Count</th></tr></thead>")
        html.append("<tbody>")
        for k, v in items:
            html.append("<tr><td>{}</td><td class='num'>{}</td></tr>".format(html_escape(k), v))
        html.append("</tbody></table>")
        return "\n".join(html)

    main_rows_html = []
    main_rows_html.append("<table>")
    main_rows_html.append("<thead><tr>")

    for fn in CSV_FIELDNAMES:
        cls = " class='num'" if fn == "Count" else ""
        main_rows_html.append("<th{}>{}</th>".format(cls, html_escape(fn)))

    main_rows_html.append("</tr></thead>")
    main_rows_html.append("<tbody>")

    for r in rows:
        main_rows_html.append("<tr>")
        for fn in CSV_FIELDNAMES:
            cls = " class='num'" if fn == "Count" else ""
            main_rows_html.append("<td{}>{}</td>".format(cls, html_escape(r.get(fn, ""))))
        main_rows_html.append("</tr>")

    main_rows_html.append("</tbody></table>")

    html = []
    html.append("<!doctype html>")
    html.append("<html>")
    html.append("<head>")
    html.append("<meta charset='utf-8'>")
    html.append("<title>Furniture Count Dashboard</title>")
    html.append("""
<style>
body {
  font-family: Arial, sans-serif;
  margin: 24px;
  background: #f7f7f5;
  color: #222;
}
h1 {
  margin: 0 0 4px 0;
  font-size: 24px;
}
h2 {
  margin-top: 28px;
  font-size: 18px;
}
.meta {
  color: #666;
  margin-bottom: 20px;
}
.cards {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin: 18px 0 24px 0;
}
.card {
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 10px;
  padding: 14px 18px;
  min-width: 180px;
}
.card .label {
  color: #777;
  font-size: 12px;
}
.card .value {
  font-size: 26px;
  font-weight: bold;
  margin-top: 6px;
}
table {
  border-collapse: collapse;
  width: 100%;
  background: #fff;
  margin-bottom: 22px;
}
th, td {
  border: 1px solid #ddd;
  padding: 7px 9px;
  font-size: 12px;
  vertical-align: top;
}
th {
  background: #ecebe7;
  text-align: left;
  position: sticky;
  top: 0;
}
.num {
  text-align: right;
}
.note {
  color: #777;
  font-size: 12px;
}
</style>
""")
    html.append("</head>")
    html.append("<body>")

    html.append("<h1>Furniture Count Dashboard</h1>")
    html.append("<div class='meta'>Generated: {} / Revit: {}</div>".format(
        html_escape(generated_at),
        html_escape(doc.Title if doc else "")
    ))

    html.append("<div class='cards'>")
    cards = [
        ("Rows", len(rows)),
        ("Total Furniture Count", total_count),
        ("Raw Filled Regions", summary.get("raw_filled_region_count", 0)),
        ("Valid Filled Regions", summary.get("valid_filled_region_count", 0)),
        ("Visible Furniture", summary.get("visible_furniture_count", 0)),
        ("Assigned Furniture", summary.get("assigned_furniture_count", 0)),
        ("Unassigned Furniture", summary.get("unassigned_furniture_count", 0)),
    ]

    for label, value in cards:
        html.append("<div class='card'><div class='label'>{}</div><div class='value'>{}</div></div>".format(
            html_escape(label),
            html_escape(value)
        ))

    html.append("</div>")

    html.append(simple_table("Count by Level", by_level))
    html.append(simple_table("Count by Region", by_region))
    html.append(simple_table("Count by Furniture Type", by_furniture))

    html.append("<h2>Detail Table</h2>")
    html.append("\n".join(main_rows_html))

    html.append("<div class='note'>Excluded columns: View, Region Display Name, Region Mark, Region Comments, gFLZ_OPENNESS, SPECIFICATION, Furniture ElementIds.</div>")
    html.append("</body>")
    html.append("</html>")

    with open(html_path, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(html))

# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

try:
    log("Start script")
    log("Revit file: {}".format(doc.Title))
    log("Region Type filter: {}".format(region_type_filter or "ALL"))

    target_views = get_target_views()

    if not target_views:
        raise Exception("No valid target view. Connect Floor Plan View to IN[0], or run from active view.")

    log("Target view count: {}".format(len(target_views)))

    counts = {}
    total_regions_raw = 0
    total_regions_valid = 0
    total_furniture_visible = 0
    total_furniture_processed = 0
    assigned_count = 0
    unassigned_count = 0

    for view in target_views:
        view_name = safe_name(view)
        level_name = get_level_name_from_view(view)

        log("Target view: {} / Id {} / Type {} / Level {}".format(
            view_name,
            eid_int(view.Id),
            str(view.ViewType),
            level_name
        ))

        raw_regions = list(
            FilteredElementCollector(doc, view.Id)
            .OfClass(FilledRegion)
            .WhereElementIsNotElementType()
            .ToElements()
        )

        total_regions_raw += len(raw_regions)
        log("View '{}' / Raw Filled Regions found: {}".format(view_name, len(raw_regions)))

        region_infos = []

        for fr in raw_regions:
            try:
                region_type_name = get_region_type_name(fr)

                if region_type_filter and region_type_name != region_type_filter:
                    continue

                loops = get_filled_region_loops(fr)
                if not loops:
                    continue

                gflz = get_gflz_values(fr)

                region_infos.append({
                    "id": eid_int(fr.Id),
                    "type": region_type_name,
                    "gflz": gflz,
                    "loops": loops,
                    "area_value": sum(loop_area_abs(l) for l in loops)
                })

            except Exception:
                add_warning("Filled Region skipped / Id {} / {}".format(eid_int(fr.Id), traceback.format_exc()))

        total_regions_valid += len(region_infos)
        log("View '{}' / Valid Filled Regions with boundaries: {}".format(view_name, len(region_infos)))

        if len(raw_regions) == 0:
            add_warning("No Filled Regions found in view '{}'.".format(view_name))
        elif len(region_infos) == 0:
            add_warning("Filled Regions found but no valid boundaries in view '{}'.".format(view_name))

        furniture = list(
            FilteredElementCollector(doc, view.Id)
            .OfCategory(BuiltInCategory.OST_Furniture)
            .WhereElementIsNotElementType()
            .ToElements()
        )

        total_furniture_visible += len(furniture)
        log("View '{}' / Visible Furniture found: {}".format(view_name, len(furniture)))

        for fi in furniture:
            try:
                pt = get_element_point(fi, view)
                if pt is None:
                    add_warning("Furniture has no usable location / Id {}".format(eid_int(fi.Id)))
                    continue

                total_furniture_processed += 1

                family_name, type_name = get_family_and_type(fi)

                matches = []
                for ri in region_infos:
                    if point_in_region_loops(pt, ri["loops"]):
                        matches.append(ri)

                if len(matches) > 1:
                    matches = sorted(matches, key=lambda x: x["area_value"])
                    add_warning(
                        "Furniture is in multiple Filled Regions. Smallest region used / FurnitureId {} / RegionId {}".format(
                            eid_int(fi.Id),
                            matches[0]["id"]
                        )
                    )

                if matches:
                    ri = matches[0]
                    g = ri["gflz"]

                    key = (
                        level_name,
                        ri["id"],
                        ri["type"],
                        g.get("gFLZ_DEPARTMENT", ""),
                        g.get("gFLZ_FUNCTION OF SPACE", ""),
                        g.get("gFLZ_OCCUPANCY CLASSIFICATION", ""),
                        g.get("gFLZ_SPACE NAME", ""),
                        g.get("gFLZ_SPACE TYPE", ""),
                        family_name,
                        type_name
                    )

                    if key not in counts:
                        counts[key] = {
                            "Level": level_name,
                            "Region ElementId": ri["id"],
                            "Region Type": ri["type"],
                            "gFLZ_DEPARTMENT": g.get("gFLZ_DEPARTMENT", ""),
                            "gFLZ_FUNCTION OF SPACE": g.get("gFLZ_FUNCTION OF SPACE", ""),
                            "gFLZ_OCCUPANCY CLASSIFICATION": g.get("gFLZ_OCCUPANCY CLASSIFICATION", ""),
                            "gFLZ_SPACE NAME": g.get("gFLZ_SPACE NAME", ""),
                            "gFLZ_SPACE TYPE": g.get("gFLZ_SPACE TYPE", ""),
                            "Furniture Family": family_name,
                            "Furniture Type": type_name,
                            "Count": 0
                        }

                    counts[key]["Count"] += 1
                    assigned_count += 1

                else:
                    unassigned_count += 1

                    if len(unassigned_samples) < 100:
                        reason = "No Filled Region candidates" if not region_infos else "Outside Filled Regions"
                        unassigned_samples.append(
                            "View={}, FurnitureId={}, Level={}, Family={}, Type={}, Reason={}, X={:.3f}, Y={:.3f}".format(
                                view_name,
                                eid_int(fi.Id),
                                level_name,
                                family_name,
                                type_name,
                                reason,
                                pt.X,
                                pt.Y
                            )
                        )

                    if include_unassigned:
                        key = (
                            level_name,
                            "",
                            "UNASSIGNED",
                            "",
                            "",
                            "",
                            "",
                            "",
                            family_name,
                            type_name
                        )

                        if key not in counts:
                            counts[key] = {
                                "Level": level_name,
                                "Region ElementId": "",
                                "Region Type": "UNASSIGNED",
                                "gFLZ_DEPARTMENT": "",
                                "gFLZ_FUNCTION OF SPACE": "",
                                "gFLZ_OCCUPANCY CLASSIFICATION": "",
                                "gFLZ_SPACE NAME": "",
                                "gFLZ_SPACE TYPE": "",
                                "Furniture Family": family_name,
                                "Furniture Type": type_name,
                                "Count": 0
                            }

                        counts[key]["Count"] += 1

            except Exception:
                add_warning("Furniture skipped / Id {} / {}".format(eid_int(fi.Id), traceback.format_exc()))

    rows = []
    for r in counts.values():
        rows.append(dict(r))

    rows = sorted(
        rows,
        key=lambda r: (
            str(r["Level"]),
            str(r["gFLZ_DEPARTMENT"]),
            str(r["gFLZ_FUNCTION OF SPACE"]),
            str(r["gFLZ_SPACE NAME"]),
            str(r["gFLZ_SPACE TYPE"]),
            str(r["Furniture Family"]),
            str(r["Furniture Type"])
        )
    )

    downloads, csv_path, html_path, log_path = get_download_paths()

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    summary = {
        "raw_filled_region_count": total_regions_raw,
        "valid_filled_region_count": total_regions_valid,
        "visible_furniture_count": total_furniture_visible,
        "furniture_processed_count": total_furniture_processed,
        "assigned_furniture_count": assigned_count,
        "unassigned_furniture_count": unassigned_count,
        "row_count": len(rows)
    }

    write_html_dashboard(html_path, rows, summary)

    log("CSV written: {}".format(csv_path))
    log("HTML written: {}".format(html_path))
    log("Rows written: {}".format(len(rows)))
    log("Raw Filled Regions total: {}".format(total_regions_raw))
    log("Valid Filled Regions total: {}".format(total_regions_valid))
    log("Visible furniture total: {}".format(total_furniture_visible))
    log("Furniture processed total: {}".format(total_furniture_processed))
    log("Assigned furniture: {}".format(assigned_count))
    log("Unassigned furniture: {}".format(unassigned_count))

    if assigned_count == 0 and total_furniture_processed > 0:
        add_warning("All furniture is UNASSIGNED. Try IN[4] = True to use BBox center.")

    log_path = write_log_file(True, csv_path, html_path, log_path)

    OUT = {
        "success": True,
        "csv_path": csv_path,
        "html_path": html_path,
        "log_path": log_path,
        "target_view_count": len(target_views),
        "raw_filled_region_count": total_regions_raw,
        "valid_filled_region_count": total_regions_valid,
        "visible_furniture_count": total_furniture_visible,
        "furniture_processed_count": total_furniture_processed,
        "assigned_furniture_count": assigned_count,
        "unassigned_furniture_count": unassigned_count,
        "row_count": len(rows),
        "warnings": warnings,
        "errors": errors
    }

except Exception:
    err = traceback.format_exc()
    errors.append(err)
    log("Script failed")
    log(err)

    try:
        _, csv_path, html_path, log_path = get_download_paths()
        log_path = write_log_file(False, csv_path, html_path, log_path)
    except:
        log_path = None

    OUT = {
        "success": False,
        "csv_path": None,
        "html_path": None,
        "log_path": log_path,
        "warnings": warnings,
        "errors": errors
    }