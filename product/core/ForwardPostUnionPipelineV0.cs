using System;
using System.Collections.Generic;

namespace ShadowCore;

/// <summary>Host-neutral inputs for the post-union Forward calculation stage.</summary>
public sealed class ForwardPostUnionPipelineInputV0
{
    public ForwardUnifiedShadowSliceSnapshotV0? Snapshot { get; set; }
    public ForwardShadowDurationSettingsV0? DurationSettings { get; set; }
    public ForwardShadowDurationExecutionOptionsV0? DurationExecutionOptions { get; set; }
    public ForwardEqualTimeContourSettingsV0? ContourSettings { get; set; }
    public int? MaximumContourSegmentCount { get; set; }
}

/// <summary>Compact, Autodesk-free result of the post-union Forward stage.</summary>
public sealed class ForwardPostUnionPipelineResultV0
{
    public bool Available { get; set; }
    public bool Complete { get; set; }
    public ForwardShadowDurationResultV0 Duration { get; set; } = new();
    public ForwardEqualTimeContourResultV0 EqualTimeContours { get; set; } = new();
    public IReadOnlyList<string> Blockers { get; set; } = Array.Empty<string>();
    public IReadOnlyList<string> Warnings { get; set; } = Array.Empty<string>();
    public bool PermitReadyCertified => false;
}

/// <summary>Pipeline result paired with the compact row-major duration field.</summary>
public sealed class ForwardPostUnionPipelineBuildResultV0
{
    public ForwardPostUnionPipelineResultV0 Result { get; set; } = new();
    public ForwardShadowDurationFieldV0? DurationField { get; set; }
}

/// <summary>
/// Orchestrates established duration and contour implementations after native union.
/// It deliberately has no Revit or Dynamo host dependencies.
/// </summary>
public static class ForwardPostUnionPipelineV0
{
    public static ForwardPostUnionPipelineBuildResultV0 Build(ForwardPostUnionPipelineInputV0? input)
    {
        var durationBuild = ForwardShadowDurationV0.BuildWithField(
            input?.Snapshot, input?.DurationSettings,
            input?.DurationExecutionOptions ?? new ForwardShadowDurationExecutionOptionsV0());
        var duration = durationBuild.Result;
        if (!duration.Complete || durationBuild.Field is null)
            return Finish(duration, new ForwardEqualTimeContourResultV0(), durationBuild.Field);

        var contours = ForwardEqualTimeContourV0.Build(
            duration, input?.ContourSettings, input?.MaximumContourSegmentCount,
            durationField: durationBuild.Field);
        return Finish(duration, contours, durationBuild.Field);
    }

    private static ForwardPostUnionPipelineBuildResultV0 Finish(
        ForwardShadowDurationResultV0 duration, ForwardEqualTimeContourResultV0 contours,
        ForwardShadowDurationFieldV0? field)
    {
        var blockers = Distinct(duration.Blockers, contours.Blockers);
        var warnings = Distinct(duration.Warnings, contours.Warnings);
        return new ForwardPostUnionPipelineBuildResultV0 {
            DurationField = field,
            Result = new ForwardPostUnionPipelineResultV0 {
                Available = duration.Available,
                Complete = duration.Complete && contours.Complete && blockers.Count == 0,
                Duration = duration,
                EqualTimeContours = contours,
                Blockers = blockers,
                Warnings = warnings
            }
        };
    }

    private static IReadOnlyList<string> Distinct(
        IReadOnlyList<string>? first, IReadOnlyList<string>? second)
    {
        var result = new List<string>();
        Add(first, result); Add(second, result);
        return result;
    }

    private static void Add(IReadOnlyList<string>? values, List<string> result)
    {
        if (values is null) return;
        foreach (var value in values) if (!result.Contains(value)) result.Add(value);
    }
}
