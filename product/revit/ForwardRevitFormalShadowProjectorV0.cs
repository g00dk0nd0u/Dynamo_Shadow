#if REVIT_API
using System;
using System.Collections.Generic;
using Autodesk.Revit.DB;

namespace RevitShadow;

/// <summary>
/// Read-only Revit-native single-time-slice formal projection boundary.
/// Mirrors runtime/shadow_formal_projection.py; it has no geometric fallback.
/// </summary>
public static class ForwardRevitFormalShadowProjectorV0
{
    public static ForwardRevitFormalShadowResultV0 Project(
        IReadOnlyList<Solid>? solids,
        double measurementPlaneElevationInternal,
        double shadowDirectionModelX,
        double shadowDirectionModelY,
        double shadowLengthFactor,
        double validationToleranceInternal = 1e-6,
        double maximumShadowLengthFactor = 100.0)
    {
        var direction = ForwardFormalShadowDirectionV0.Create(
            shadowDirectionModelX, shadowDirectionModelY, shadowLengthFactor,
            maximumShadowLengthFactor);
        var output = new List<ForwardRevitFormalShadowComponentV0>();
        var blockers = new List<string>();
        var warnings = new List<string>();
        var clippedCount = 0;
        var extentAttempted = false;
        var extentPassed = true;
        var runtimeDirectionPassed = true;

        if (!direction.Valid || !double.IsFinite(measurementPlaneElevationInternal)
            || !double.IsFinite(validationToleranceInternal) || validationToleranceInternal < 0.0)
        {
            if (!double.IsFinite(measurementPlaneElevationInternal))
                blockers.Add("measurement_plane_elevation_unavailable");
            if (!double.IsFinite(validationToleranceInternal) || validationToleranceInternal < 0.0)
                blockers.Add("numeric_conversion_failed");
            return Result(solids?.Count ?? 0, clippedCount, output, direction, false,
                extentAttempted, false, blockers, warnings);
        }

        var plane = Plane.CreateByNormalAndOrigin(
            XYZ.BasisZ, new XYZ(0.0, 0.0, measurementPlaneElevationInternal));
        for (var sourceIndex = 0; sourceIndex < (solids?.Count ?? 0); sourceIndex++)
        {
            IList<Solid> split;
            try { split = SolidUtils.SplitVolumes(solids![sourceIndex]); }
            catch (Exception) { blockers.Add("solid_split_exception"); continue; }

            for (var splitIndex = 0; splitIndex < split.Count; splitIndex++)
            {
                var splitSolid = split[splitIndex];
                if (!(splitSolid.Volume > 0.0))
                {
                    blockers.Add("split_solid_zero_or_unknown_volume");
                    DisposeIfOwned(splitSolid, solids![sourceIndex]);
                    continue;
                }

                Solid? clipped = null;
                try
                {
                    // Clip failure is a blocker. The uncut Solid is never analyzed.
                    clipped = BooleanOperationsUtils.CutWithHalfSpace(splitSolid, plane);
                    if (clipped is null) throw new InvalidOperationException();
                    if (!(clipped.Volume > 0.0)) continue;

                    var components = SolidUtils.SplitVolumes(clipped);
                    for (var componentIndex = 0; componentIndex < components.Count; componentIndex++)
                    {
                        var component = components[componentIndex];
                        if (!(component.Volume > 0.0)) { DisposeIfOwned(component, clipped); continue; }
                        clippedCount++;
                        try
                        {
                            ProjectComponent(component, plane, direction, sourceIndex, splitIndex,
                                componentIndex, measurementPlaneElevationInternal,
                                validationToleranceInternal, output, blockers,
                                ref runtimeDirectionPassed, ref extentAttempted, ref extentPassed);
                        }
                        finally { DisposeIfOwned(component, clipped); }
                    }
                }
                catch (Exception) { blockers.Add("half_space_clip_failed"); }
                finally
                {
                    clipped?.Dispose();
                    DisposeIfOwned(splitSolid, solids![sourceIndex]);
                }
            }
        }

        return Result(solids?.Count ?? 0, clippedCount, output, direction,
            runtimeDirectionPassed, extentAttempted, extentPassed, blockers, warnings);
    }

    private static void ProjectComponent(Solid component, Plane plane,
        ForwardFormalShadowDirectionV0 direction, int sourceIndex, int splitIndex,
        int componentIndex, double planeZ, double tolerance,
        List<ForwardRevitFormalShadowComponentV0> output, List<string> blockers,
        ref bool runtimeDirectionPassed, ref bool extentAttempted, ref bool extentPassed)
    {
        ExtrusionAnalyzer? analyzer = null;
        try
        {
            // Physical-ray sign reversal occurs only here, at the Revit API boundary.
            var analyzerDirection = new XYZ(direction.AnalyzerX, direction.AnalyzerY, direction.AnalyzerZ);
            analyzer = ExtrusionAnalyzer.Create(component, plane, analyzerDirection);
            var face = analyzer.GetExtrusionBase();
            if (face is null) { blockers.Add("get_extrusion_base_failure"); return; }
            var loops = new List<CurveLoop>(face.GetEdgesAsCurveLoops());
            if (!ValidateLoops(loops, planeZ, tolerance))
            {
                DisposeLoops(loops);
                blockers.Add("native_curve_loop_acquisition_failure");
                return;
            }

            var axisLength = Math.Sqrt(direction.PhysicalX * direction.PhysicalX
                + direction.PhysicalY * direction.PhysicalY);
            if (!(axisLength > 0.0))
            {
                DisposeLoops(loops);
                runtimeDirectionPassed = false;
                blockers.Add("runtime_projection_validation_unverified");
                return;
            }
            var ax = direction.PhysicalX / axisLength;
            var ay = direction.PhysicalY / axisLength;
            var source = EdgePoints(component);
            var actual = LoopPoints(loops);
            var section = MeasurementSectionPoints(component, planeZ, tolerance);
            extentAttempted = source.Count > 0 && actual.Count > 0;
            var componentExtentPassed = extentAttempted && ExtentsAgree(
                source, actual, ax, ay, planeZ, direction.ShadowLengthFactor, tolerance);
            extentPassed &= componentExtentPassed;
            var componentDirectionPassed = DirectionAgrees(section, actual, ax, ay, tolerance);
            runtimeDirectionPassed &= componentDirectionPassed;

            output.Add(new ForwardRevitFormalShadowComponentV0(
                sourceIndex, splitIndex, componentIndex, loops));
        }
        catch (Exception) { blockers.Add("extrusion_analyzer_exception"); }
        finally { analyzer?.Dispose(); }
    }

    private static bool ValidateLoops(IEnumerable<CurveLoop> loops, double planeZ, double tolerance)
    {
        var count = 0;
        foreach (var loop in loops)
        {
            count++;
            if (loop.IsOpen() || !loop.HasPlane()) return false;
            var curveCount = 0;
            foreach (var curve in loop)
            {
                curveCount++;
                if (curve is not Line || curve.Length <= 0.0) return false;
                if (Math.Abs(curve.GetEndPoint(0).Z - planeZ) > tolerance
                    || Math.Abs(curve.GetEndPoint(1).Z - planeZ) > tolerance) return false;
            }
            if (curveCount < 3) return false;
        }
        return count > 0;
    }

    private static List<XYZ> EdgePoints(Solid solid)
    {
        var result = new List<XYZ>();
        foreach (Edge edge in solid.Edges)
        {
            var curve = edge.AsCurve(); result.Add(curve.GetEndPoint(0)); result.Add(curve.GetEndPoint(1));
        }
        return result;
    }

    private static List<XYZ> LoopPoints(IEnumerable<CurveLoop> loops)
    {
        var result = new List<XYZ>();
        foreach (var loop in loops) foreach (var curve in loop) result.Add(curve.GetEndPoint(0));
        return result;
    }

    private static List<XYZ> MeasurementSectionPoints(Solid solid, double planeZ, double tolerance)
    {
        var result = new List<XYZ>();
        foreach (Face face in solid.Faces)
        {
            if (face is not PlanarFace planar || Math.Abs(Math.Abs(planar.FaceNormal.Z) - 1.0) > 1e-7
                || Math.Abs(planar.Origin.Z - planeZ) > tolerance) continue;
            var loops = new List<CurveLoop>(face.GetEdgesAsCurveLoops());
            try { result.AddRange(LoopPoints(loops)); } finally { DisposeLoops(loops); }
        }
        return result;
    }

    private static bool DirectionAgrees(List<XYZ> section, List<XYZ> shadow,
        double ax, double ay, double tolerance)
    {
        if (section.Count == 0 || shadow.Count == 0) return false;
        var sectionMin = MinAxis(section, ax, ay); var sectionMax = MaxAxis(section, ax, ay);
        var shadowMin = MinAxis(shadow, ax, ay); var shadowMax = MaxAxis(shadow, ax, ay);
        var sunwardOverflow = Math.Max(0.0, sectionMin - shadowMin);
        var downshadowExtension = Math.Max(0.0, shadowMax - sectionMax);
        return sunwardOverflow <= tolerance && downshadowExtension > tolerance;
    }

    private static bool ExtentsAgree(List<XYZ> source, List<XYZ> actual,
        double ax, double ay, double planeZ, double factor, double tolerance)
    {
        var expectedMin = double.PositiveInfinity; var expectedMax = double.NegativeInfinity;
        foreach (var p in source)
        {
            var value = p.X * ax + p.Y * ay + (p.Z - planeZ) * factor;
            expectedMin = Math.Min(expectedMin, value); expectedMax = Math.Max(expectedMax, value);
        }
        return Math.Abs(MinAxis(actual, ax, ay) - expectedMin) <= tolerance
            && Math.Abs(MaxAxis(actual, ax, ay) - expectedMax) <= tolerance;
    }

    private static double MinAxis(IEnumerable<XYZ> points, double ax, double ay)
    { var v = double.PositiveInfinity; foreach (var p in points) v = Math.Min(v, p.X * ax + p.Y * ay); return v; }
    private static double MaxAxis(IEnumerable<XYZ> points, double ax, double ay)
    { var v = double.NegativeInfinity; foreach (var p in points) v = Math.Max(v, p.X * ax + p.Y * ay); return v; }
    private static void DisposeLoops(IEnumerable<CurveLoop> loops) { foreach (var loop in loops) loop.Dispose(); }
    private static void DisposeIfOwned(Solid value, Solid owner) { if (!ReferenceEquals(value, owner)) value.Dispose(); }

    private static ForwardRevitFormalShadowResultV0 Result(int inputCount, int clippedCount,
        List<ForwardRevitFormalShadowComponentV0> output, ForwardFormalShadowDirectionV0 direction,
        bool directionPassed, bool extentAttempted, bool extentPassed,
        List<string> blockers, List<string> warnings)
    {
        var loopCount = 0; foreach (var item in output) loopCount += item.Loops.Count;
        var summary = ForwardRevitFormalShadowSummaryV0.Create(inputCount, clippedCount,
            output.Count, loopCount, direction, direction.Valid && directionPassed,
            extentAttempted, extentPassed, blockers, warnings);
        return new ForwardRevitFormalShadowResultV0(output, summary);
    }
}
#endif
