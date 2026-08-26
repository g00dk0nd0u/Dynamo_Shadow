using System;
using System.Collections.Generic;

namespace ShadowCore;

public sealed class ForwardUnifiedShadowPolygonSnapshotV0
{
    public int PolygonIndex { get; set; }
    public int ComponentIndex { get; set; }
    public string Role { get; set; } = "";
    public string Orientation { get; set; } = "";
    public bool Closed { get; set; }
    public int PointCount { get; set; }
    public double AreaM2 { get; set; }
    public IReadOnlyList<Point2M> PointsM { get; set; } = Array.Empty<Point2M>();
    public string GenerationMethod { get; set; } = "";
}

public sealed class ForwardUnifiedShadowComponentSnapshotV0
{
    public bool Complete { get; set; }
    public IReadOnlyList<ForwardUnifiedShadowPolygonSnapshotV0> Polygons { get; set; } = Array.Empty<ForwardUnifiedShadowPolygonSnapshotV0>();
    public IReadOnlyList<string> Blockers { get; set; } = Array.Empty<string>();
}

public sealed class ForwardUnifiedShadowTimeSliceSnapshotV0
{
    public int SliceIndex { get; set; }
    public int SampleIndex { get; set; }
    public double TrueSolarMinutes { get; set; }
    public bool Complete { get; set; }
    public IReadOnlyList<ForwardUnifiedShadowPolygonSnapshotV0> Polygons { get; set; } = Array.Empty<ForwardUnifiedShadowPolygonSnapshotV0>();
    public IReadOnlyList<string> Blockers { get; set; } = Array.Empty<string>();
}

public sealed class ForwardUnifiedShadowSliceSnapshotV0
{
    public bool Available { get; set; }
    public bool Complete { get; set; }
    public bool ReadyForDurationAccumulation { get; set; }
    public IReadOnlyList<ForwardUnifiedShadowTimeSliceSnapshotV0> Slices { get; set; } = Array.Empty<ForwardUnifiedShadowTimeSliceSnapshotV0>();
    public IReadOnlyList<string> Blockers { get; set; } = Array.Empty<string>();
    public IReadOnlyList<string> Warnings { get; set; } = Array.Empty<string>();
    public bool PermitReadyCertified => false;

    public static ForwardUnifiedShadowSliceSnapshotV0 Create(
        IReadOnlyList<ForwardUnifiedShadowTimeSliceSnapshotV0>? slices,
        IEnumerable<string>? blockers = null, IEnumerable<string>? warnings = null)
    {
        var sliceValues = slices ?? Array.Empty<ForwardUnifiedShadowTimeSliceSnapshotV0>();
        var blockerValues = blockers is null ? new List<string>() : new List<string>(blockers);
        foreach (var slice in sliceValues) if (!slice.Complete) blockerValues.AddRange(slice.Blockers);
        var complete = sliceValues.Count > 0 && blockerValues.Count == 0;
        if (complete) foreach (var slice in sliceValues) if (!slice.Complete) { complete = false; break; }
        return new ForwardUnifiedShadowSliceSnapshotV0 {
            Available = sliceValues.Count > 0, Complete = complete,
            ReadyForDurationAccumulation = complete, Slices = sliceValues,
            Blockers = blockerValues,
            Warnings = warnings is null ? Array.Empty<string>() : new List<string>(warnings)
        };
    }
}

/// <summary>Autodesk-free port of runtime/shadow_union.py::_serialize_component.</summary>
public static class ForwardUnifiedShadowComponentClassifierV0
{
    public const string GenerationMethod = "revit_boolean_union_curve_loop_line_exact";

    public static ForwardUnifiedShadowComponentSnapshotV0 Classify(
        IReadOnlyList<IReadOnlyList<Point2M>>? loops, int componentIndex)
    {
        var polygons = new List<ForwardUnifiedShadowPolygonSnapshotV0>();
        if (loops is null || loops.Count == 0) return Failed("union_output_has_no_loops");
        var copied = new List<List<Point2M>>(); var signed = new List<double>();
        foreach (var loop in loops)
        {
            if (loop is null) return Failed("union_output_loop_invalid");
            var points = new List<Point2M>(); var unique = new HashSet<(double, double)>();
            foreach (var point in loop)
            {
                if (point is null || !ForwardGeometryV0.Finite(point.X) || !ForwardGeometryV0.Finite(point.Y))
                    return Failed("numeric_conversion_failed");
                points.Add(new Point2M(point.X, point.Y)); unique.Add((point.X, point.Y));
            }
            if (unique.Count < 3) return Failed("union_output_loop_invalid");
            var area = ForwardGeometryV0.SignedArea(points);
            if (!ForwardGeometryV0.Finite(area) || area == 0.0) return Failed("union_output_loop_invalid");
            copied.Add(points); signed.Add(area);
        }
        var largest = 0;
        for (var index = 1; index < signed.Count; index++)
            if (Math.Abs(signed[index]) > Math.Abs(signed[largest])) largest = index;
        for (var index = 0; index < copied.Count; index++)
        {
            var role = index == largest || !ForwardGeometryV0.Contains(copied[largest], copied[index][0].X, copied[index][0].Y) ? "outer" : "inner";
            var desired = role == "outer" ? 1.0 : -1.0;
            if (signed[index] * desired < 0) { copied[index].Reverse(); signed[index] *= -1; }
            polygons.Add(new ForwardUnifiedShadowPolygonSnapshotV0 {
                PolygonIndex = index, ComponentIndex = componentIndex, Role = role,
                Orientation = role == "outer" ? "ccw" : "cw", Closed = true,
                PointCount = copied[index].Count, AreaM2 = Math.Abs(signed[index]),
                PointsM = copied[index], GenerationMethod = GenerationMethod
            });
        }
        return new ForwardUnifiedShadowComponentSnapshotV0 { Complete = true, Polygons = polygons };
    }

    private static ForwardUnifiedShadowComponentSnapshotV0 Failed(string blocker) => new() {
        Blockers = new[] { blocker }
    };
}
