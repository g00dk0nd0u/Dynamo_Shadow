import shadow_inputs


class Point:
    def __init__(self, x, y, z=0.0):
        self.X, self.Y, self.Z = x, y, z


class Curve:
    def __init__(self, start, end):
        self._points = (Point(*start), Point(*end))

    def GetEndPoint(self, index):
        return self._points[index]


class Location:
    def __init__(self, curve):
        self.Curve = curve


class ModelLine:
    IsValidObject = True
    Id = 1
    Category = type("Category", (), {"Id": 1, "Name": "Model Lines"})()
    ViewSpecific = False
    OwnerViewId = -1

    def __init__(self, start, end):
        self.Location = Location(Curve(start, end))
        self.geometry_call_count = 0

    def get_Geometry(self, _options):
        self.geometry_call_count += 1
        raise BaseException("unsafe external component call")


def test_model_line_terminates_after_usable_location_curve(monkeypatch):
    checkpoints = []
    monkeypatch.setattr(shadow_inputs, "_runtime_checkpoint", lambda stage, detail=None: checkpoints.append(stage))
    line = ModelLine((0, 0), (1, 0))

    result = shadow_inputs._diagnose_curve_access(line)

    assert result["curve_access_method"] == "location_curve"
    assert result["location_curve_available"] is True
    assert result["endpoint_read_succeeded"] is True
    assert result["endpoint_count"] == 2
    assert line.geometry_call_count == 0
    assert "SITE_CURVE_GEOMETRY_FALLBACK_BEFORE" not in checkpoints


def test_missing_location_curve_geometry_failure_is_contained(monkeypatch):
    class GeometryElement:
        Location = None

        def get_Geometry(self, _options):
            raise BaseException("geometry failed")

    class FakeOptions:
        pass

    monkeypatch.setattr(shadow_inputs, "Options", FakeOptions)
    result = shadow_inputs._diagnose_curve_access(GeometryElement())

    assert result["geometry_fallback_attempted"] is True
    assert result["curve_access_method"] == "unavailable"
    assert "geometry failed" in result["error"]


def test_seven_model_lines_form_closed_site_boundary():
    points = [(0, 0), (4, 0), (6, 2), (6, 5), (3, 7), (0, 5), (-1, 2)]
    lines = [ModelLine(points[index], points[(index + 1) % len(points)]) for index in range(7)]

    result = shadow_inputs._diagnose_site_boundary(lines)

    assert result["accepted_count"] == 0
    assert result["loop_diagnostics"]["attempted"] is False
    assert sum(item["curve_access"]["endpoint_count"] for item in result["items"]) == 14
    assert result["boundary_dependent_steps_available"] is False
    assert all(line.geometry_call_count == 0 for line in lines)


def test_malformed_item_does_not_abort_remaining_model_lines():
    lines = [
        ModelLine((0, 0), (1, 0)),
        object(),
        ModelLine((1, 0), (1, 1)),
        ModelLine((1, 1), (0, 1)),
        ModelLine((0, 1), (0, 0)),
    ]

    result = shadow_inputs._diagnose_site_boundary(lines)

    assert result["accepted_count"] == 0
    assert result["rejected_count"] == 5
    assert result["loop_diagnostics"]["attempted"] is False
    assert result["loop_diagnostics"]["attempted"] is False
    assert result["warnings"]
