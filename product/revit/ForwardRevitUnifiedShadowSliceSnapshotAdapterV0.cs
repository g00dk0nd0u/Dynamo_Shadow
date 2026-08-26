#if REVIT_API
using System;
using System.Collections.Generic;
using Autodesk.Revit.DB;
using ShadowCore;

namespace RevitShadow;

/// <summary>Copies owned Revit union loops into independent, meter-based snapshot values.</summary>
public static class ForwardRevitUnifiedShadowSliceSnapshotAdapterV0
{
    public static ForwardUnifiedShadowSliceSnapshotV0 Create(ForwardRevitMultiTimeIntegrationResultV0? source)
    {
        if (source is null || source.Summary is null || !source.Summary.Available || !source.Summary.Complete)
            return Failed("complete_unified_shadow_slices_required");
        var summaries = source.Summary.Slices;
        var natives = source.SliceResults;
        if (summaries is null || natives is null || summaries.Count != natives.Count)
            return Failed("shadow_slice_count_mismatch");
        var slices = new List<ForwardUnifiedShadowTimeSliceSnapshotV0>();
        var warnings = new List<string>();
        foreach (var warning in source.Summary.Warnings) warnings.Add(warning.Code);
        for (var index = 0; index < summaries.Count; index++)
        {
            var summary = summaries[index]; var native = natives[index];
            if (summary is null || summary.SampleIndex != index)
                return Failed("shadow_slice_order_mismatch", warnings);
            if (!summary.Complete || native is null || !native.Summary.Complete ||
                native.UnionResult is null || !native.UnionResult.Summary.Complete)
                return Failed("complete_unified_shadow_slices_required", warnings);
            if (!double.IsFinite(summary.TrueSolarMinutes)) return Failed("numeric_conversion_failed", warnings);
            var polygons = new List<ForwardUnifiedShadowPolygonSnapshotV0>();
            var components = native.UnionResult.Components;
            if (components is null || components.Count == 0) return Failed("no_valid_native_union_curve_loop", warnings);
            for (var componentIndex = 0; componentIndex < components.Count; componentIndex++)
            {
                var component = components[componentIndex];
                if (component is null || component.Loops is null || component.Loops.Count == 0)
                    return Failed("no_valid_native_union_curve_loop", warnings);
                var loops = new List<IReadOnlyList<Point2M>>();
                foreach (var loop in component.Loops)
                {
                    if (loop is null) return Failed("union_output_loop_invalid", warnings);
                    var points = new List<Point2M>();
                    try {
                        foreach (var curve in loop) {
                            if (curve is not Line) return Failed("union_output_non_line_loop", warnings);
                            var point = curve.GetEndPoint(0);
                            var x = UnitUtils.ConvertFromInternalUnits(point.X, UnitTypeId.Meters);
                            var y = UnitUtils.ConvertFromInternalUnits(point.Y, UnitTypeId.Meters);
                            if (!double.IsFinite(x) || !double.IsFinite(y)) return Failed("numeric_conversion_failed", warnings);
                            points.Add(new Point2M(x, y));
                        }
                    } catch (Exception) { return Failed("unit_conversion_failed", warnings); }
                    loops.Add(points);
                }
                var classified = ForwardUnifiedShadowComponentClassifierV0.Classify(loops, componentIndex);
                if (!classified.Complete) return ForwardUnifiedShadowSliceSnapshotV0.Create(Array.Empty<ForwardUnifiedShadowTimeSliceSnapshotV0>(), classified.Blockers, warnings);
                polygons.AddRange(classified.Polygons);
            }
            slices.Add(new ForwardUnifiedShadowTimeSliceSnapshotV0 { SliceIndex = index,
                SampleIndex = summary.SampleIndex, TrueSolarMinutes = summary.TrueSolarMinutes,
                Complete = true, Polygons = polygons });
        }
        return ForwardUnifiedShadowSliceSnapshotV0.Create(slices, warnings: warnings);
    }

    private static ForwardUnifiedShadowSliceSnapshotV0 Failed(string blocker, IEnumerable<string>? warnings = null) =>
        ForwardUnifiedShadowSliceSnapshotV0.Create(Array.Empty<ForwardUnifiedShadowTimeSliceSnapshotV0>(), new[] { blocker }, warnings);
}
#endif
