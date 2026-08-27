using System;
using System.Collections.Generic;
using ShadowCore;

namespace RevitShadow;

/// <summary>Host-neutral summary of the compiled Full Forward stage boundary.</summary>
public sealed class ForwardRevitFullForwardSummaryV0
{
    public bool Available { get; internal set; }
    public bool Complete { get; internal set; }
    public string FinalCompletedStage { get; internal set; } = "none";
    public string? BlockerStage { get; internal set; }
    public bool MultiTimeComplete { get; internal set; }
    public bool SnapshotComplete { get; internal set; }
    public bool DurationComplete { get; internal set; }
    public bool ContoursComplete { get; internal set; }
    public int DurationGridPointCount { get; internal set; }
    public int ContourCount { get; internal set; }
    public IReadOnlyList<string> Blockers { get; internal set; } = Array.Empty<string>();
    public IReadOnlyList<ForwardRevitStageWarningV0> Warnings { get; internal set; } =
        Array.Empty<ForwardRevitStageWarningV0>();
    public bool PermitReadyCertified => false;
}

/// <summary>
/// Autodesk-free early-stop coordinator. Each callback remains the owner of its existing algorithm.
/// </summary>
public static class ForwardRevitFullForwardOrchestratorV0
{
    public static ForwardRevitFullForwardSummaryV0 Run(
        Func<ForwardRevitMultiTimeSummaryV0> runMultiTime,
        Func<ForwardUnifiedShadowSliceSnapshotV0> createSnapshot,
        Func<ForwardShadowDurationResultV0> buildDuration,
        Func<ForwardEqualTimeContourResultV0> buildContours)
    {
        if (runMultiTime is null) throw new ArgumentNullException(nameof(runMultiTime));
        if (createSnapshot is null) throw new ArgumentNullException(nameof(createSnapshot));
        if (buildDuration is null) throw new ArgumentNullException(nameof(buildDuration));
        if (buildContours is null) throw new ArgumentNullException(nameof(buildContours));

        var warnings = new List<ForwardRevitStageWarningV0>();
        var multiTime = runMultiTime();
        warnings.AddRange(multiTime.Warnings);
        if (!multiTime.Complete)
            return Failed(multiTime.Available, "none", "multi_time_forward", multiTime.Blockers, warnings);

        var snapshot = createSnapshot();
        AddWarnings(warnings, "unified_snapshot", snapshot.Warnings);
        if (!snapshot.Complete)
            return Failed(multiTime.Available, "multi_time_forward", "unified_snapshot",
                snapshot.Blockers, warnings, multiTimeComplete: true);

        var duration = buildDuration();
        AddWarnings(warnings, "duration", duration.Warnings);
        if (!duration.Complete)
            return Failed(multiTime.Available, "unified_snapshot", "duration", duration.Blockers,
                warnings, true, true, durationGridPointCount: duration.GridPointCount);

        var contours = buildContours();
        AddWarnings(warnings, "equal_time_contours", contours.Warnings);
        if (!contours.Complete)
            return Failed(multiTime.Available, "duration", "equal_time_contours", contours.Blockers,
                warnings, true, true, true, duration.GridPointCount, contours.ContourCount);

        return new ForwardRevitFullForwardSummaryV0 {
            Available = true, Complete = true, FinalCompletedStage = "equal_time_contours",
            MultiTimeComplete = true, SnapshotComplete = true, DurationComplete = true,
            ContoursComplete = true, DurationGridPointCount = duration.GridPointCount,
            ContourCount = contours.ContourCount, Warnings = warnings
        };
    }

    private static void AddWarnings(List<ForwardRevitStageWarningV0> target, string stage,
        IEnumerable<string> values)
    {
        foreach (var value in values)
            target.Add(new ForwardRevitStageWarningV0 { Stage = stage, Code = value });
    }

    private static ForwardRevitFullForwardSummaryV0 Failed(bool available, string completedStage,
        string blockerStage, IReadOnlyList<string> blockers,
        IReadOnlyList<ForwardRevitStageWarningV0> warnings,
        bool multiTimeComplete = false, bool snapshotComplete = false, bool durationComplete = false,
        int durationGridPointCount = 0, int contourCount = 0) => new() {
            Available = available, FinalCompletedStage = completedStage, BlockerStage = blockerStage,
            MultiTimeComplete = multiTimeComplete, SnapshotComplete = snapshotComplete,
            DurationComplete = durationComplete, DurationGridPointCount = durationGridPointCount,
            ContourCount = contourCount, Blockers = blockers, Warnings = warnings
        };
}
