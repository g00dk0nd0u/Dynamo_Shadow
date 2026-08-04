import math

import pytest

import shadow_footprint as footprint


class FakeXYZ:
    BasisZ = None

    def __init__(self, x, y, z=0.0):
        self.X, self.Y, self.Z = x, y, z


FakeXYZ.BasisZ = FakeXYZ(0, 0, 1)


class FakeLine:
    def __init__(self, a, b):
        self.points = [a, b]
        self.Length = math.sqrt(sum((getattr(a, key) - getattr(b, key)) ** 2 for key in ("X", "Y", "Z")))

    def GetEndPoint(self, index):
        return self.points[index]


class FakeArc(FakeLine):
    pass


class FakePlane:
    def __init__(self, normal=None):
        self.Origin = FakeXYZ(0, 0, 0)
        self.Normal = normal or FakeXYZ(0, 0, 1)


class FakeCurveLoop:
    def __init__(self, curves, open_=False, planar=True, ccw=True, normal=None,
                 inspect_error=False):
        self.curves = list(curves)
        self.open = open_
        self.planar = planar
        self.ccw = ccw
        self.plane = FakePlane(normal)
        self.disposed = False
        self.inspect_error = inspect_error
        self.flips = 0

    def IsOpen(self):
        if self.inspect_error:
            raise RuntimeError("inspection failed")
        return self.open

    def HasPlane(self): return self.planar
    def GetPlane(self): return self.plane
    def NumberOfCurves(self): return len(self.curves)
    def GetExactLength(self): return sum(c.Length for c in self.curves)
    def IsCounterclockwise(self, direction): return self.ccw

    def Flip(self):
        self.curves = [FakeLine(c.points[1], c.points[0]) for c in reversed(self.curves)]
        self.ccw = not self.ccw
        self.flips += 1

    def Dispose(self): self.disposed = True
    def __iter__(self): return iter(self.curves)


class FakeFace:
    def __init__(self, loops=None, edge_loops=None, error=None, forbid_edges=False):
        self.loops = loops
        self._edge_loops = edge_loops or []
        self.error = error
        self.forbid_edges = forbid_edges

    def GetEdgesAsCurveLoops(self):
        if self.error:
            raise self.error
        return self.loops

    @property
    def EdgeLoops(self):
        if self.forbid_edges:
            raise AssertionError("fallback EdgeLoops was accessed")
        return self._edge_loops


def loop_from_points(points, cls=FakeLine, **kwargs):
    xyz = [FakeXYZ(*point) for point in points]
    return FakeCurveLoop([cls(xyz[i], xyz[(i + 1) % len(xyz)]) for i in range(len(xyz))], **kwargs)


def extract(loop, **face_kwargs):
    return footprint._extract_edge_loop_candidates_from_face(
        FakeFace([loop], **face_kwargs), {"type": "PlanarFace"}
    )


@pytest.fixture(autouse=True)
def native_orientation_api(monkeypatch):
    monkeypatch.setattr(footprint, "XYZ", FakeXYZ)


def test_native_rectangle_uses_order_without_stitch_and_disposes(monkeypatch):
    loop = loop_from_points([(0, 0, 0), (10, 0, 0), (10, 5, 0), (0, 5, 0)])
    monkeypatch.setattr(footprint, "_stitch_loop_segments", lambda *a: (_ for _ in ()).throw(AssertionError("stitch called")))
    result = extract(loop, forbid_edges=True)
    candidate = dict(result["loops"][0], candidate_index=0, caster_index=0, source_face_index=0)
    formal, warnings = footprint._formal_loop_from_candidate(candidate)
    assert not warnings
    assert result["generation_method"] == "native_curve_loop"
    assert result["fallback_used"] is False
    assert formal["generation_method"] == "native_curve_loop_line_exact"
    assert formal["point_count"] == 4
    assert loop.disposed


def test_native_l_shape_preserves_concavity():
    loop = loop_from_points([(0, 0, 0), (4, 0, 0), (4, 1, 0), (1, 1, 0), (1, 4, 0), (0, 4, 0)])
    result = extract(loop, forbid_edges=True)
    candidate = dict(result["loops"][0], candidate_index=0, caster_index=0, source_face_index=0)
    formal, _ = footprint._formal_loop_from_candidate(candidate)
    assert formal["point_count"] == 6
    assert formal["area_m2"] == pytest.approx(7 * 0.3048 ** 2)


def test_native_outer_and_hole_use_native_orientation_and_flip_only_hole():
    outer = loop_from_points([(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)], ccw=True)
    hole = loop_from_points([(2, 2, 0), (4, 2, 0), (4, 4, 0), (2, 4, 0)], ccw=True)
    result = footprint._extract_edge_loop_candidates_from_face(FakeFace([outer, hole]), {"type": "PlanarFace"})
    assert result["loops"][0]["native_inspection"]["native_role"] == "outer"
    assert result["loops"][1]["native_inspection"]["native_role"] == "inner"
    assert outer.flips == 0 and hole.flips == 1
    assert outer.disposed and hole.disposed


@pytest.mark.parametrize("open_,planar,code", [
    (True, True, "native_curve_loop_is_open"),
    (False, False, "native_curve_loop_is_not_planar"),
])
def test_invalid_native_loop_never_falls_back(open_, planar, code):
    loop = loop_from_points([(0, 0, 0), (1, 0, 0), (0, 1, 0)], open_=open_, planar=planar)
    result = extract(loop, forbid_edges=True)
    inspected = result["loops"][0]["native_inspection"]
    assert code in inspected["blockers"]
    assert result["fallback_used"] is False
    assert loop.disposed


def test_discontinuous_native_sequence_is_invalid_without_reordering():
    curves = [FakeLine(FakeXYZ(0, 0), FakeXYZ(1, 0)),
              FakeLine(FakeXYZ(2, 0), FakeXYZ(0, 1)),
              FakeLine(FakeXYZ(0, 1), FakeXYZ(0, 0))]
    result = extract(FakeCurveLoop(curves), forbid_edges=True)
    assert "native_curve_sequence_discontinuous" in result["loops"][0]["native_inspection"]["blockers"]
    assert not result["fallback_used"]


def test_native_arc_is_recognized_but_not_adapted_or_fallen_back():
    loop = loop_from_points([(0, 0, 0), (1, 0, 0), (0, 1, 0)], cls=FakeArc)
    result = extract(loop, forbid_edges=True)
    inspected = result["loops"][0]["native_inspection"]
    assert inspected["valid_native_loop"] is True
    assert inspected["contains_non_line_curve"] is True
    assert inspected["formal_line_adapter_available"] is False
    assert "native_curve_loop_contains_non_line_curve" in inspected["blockers"]
    assert result["fallback_used"] is False


def test_native_exception_and_empty_results_fall_back_with_diagnostics():
    failure = footprint._extract_edge_loop_candidates_from_face(
        FakeFace(error=RuntimeError("x" * 300)), {"type": "PlanarFace"})
    assert failure["fallback_used"] is True
    assert failure["native_failure_code"] == "native_call_exception"
    assert failure["native_failure_type"] == "RuntimeError"
    assert len(failure["native_failure_message"]) == 200
    empty = footprint._extract_edge_loop_candidates_from_face(FakeFace([]), {"type": "PlanarFace"})
    assert empty["fallback_used"] is True
    assert empty["native_failure_code"] == "native_result_empty"


def test_short_curve_tolerance_is_only_applied_when_supplied():
    loop = loop_from_points([(0, 0, 0), (0.01, 0, 0), (0, 1, 0)])
    without = footprint._inspect_native_curve_loop(loop, 0, 0.001, None)
    with_tolerance = footprint._inspect_native_curve_loop(loop, 0, 0.001, 0.02)
    assert "native_curve_is_below_revit_short_curve_tolerance" not in without["blockers"]
    assert "native_curve_is_below_revit_short_curve_tolerance" in with_tolerance["blockers"]


def test_dispose_runs_when_inspection_raises():
    loop = loop_from_points([(0, 0, 0), (1, 0, 0), (0, 1, 0)], inspect_error=True)
    extract(loop)
    assert loop.disposed
