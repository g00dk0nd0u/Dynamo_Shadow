using RevitShadow;
using ShadowCore;
using Xunit;

namespace RevitShadow.Tests;

public sealed class ForwardRevitFullForwardOrchestratorV0Tests
{
    [Fact]
    public void MultiTimeFailureStopsAllLaterStages()
    {
        var calls = new int[2];
        var failedMultiTime = Multi(false, "solar_input_invalid", "multi warning");
        var summary = ForwardRevitFullForwardOrchestratorV0.Run(
            () => failedMultiTime,
            () => { calls[0]++; return Snapshot(); },
            () => { calls[1]++; return Pipeline(); });

        Assert.Equal(new[] { 0, 0 }, calls);
        AssertStopped(summary, "none", "multi_time_forward", "solar_input_invalid");
        Assert.Equal(failedMultiTime.Available, summary.Available);
        Assert.Contains(summary.Warnings, warning => warning.Code == "multi warning");
    }

    [Fact]
    public void SnapshotFailureStopsDurationAndContours()
    {
        var laterCalls = 0;
        var failedSnapshot = Snapshot(false, "union_output_loop_invalid", "snapshot warning");
        var summary = ForwardRevitFullForwardOrchestratorV0.Run(
            () => Multi(),
            () => failedSnapshot,
            () => { laterCalls++; return Pipeline(); });

        Assert.Equal(0, laterCalls);
        AssertStopped(summary, "multi_time_forward", "unified_snapshot", "union_output_loop_invalid");
        Assert.Equal(failedSnapshot.Available, summary.Available);
        Assert.True(summary.MultiTimeComplete);
        Assert.Contains(summary.Warnings, warning => warning.Code == "snapshot warning");
    }

    [Fact]
    public void DurationFailureStopsContours()
    {
        var failedDuration = Duration(false, "max_duration_grid_points_exceeded", "duration warning");
        var summary = ForwardRevitFullForwardOrchestratorV0.Run(
            () => Multi(), () => Snapshot(),
            () => Pipeline(failedDuration, Contours()));

        AssertStopped(summary, "unified_snapshot", "duration", "max_duration_grid_points_exceeded");
        Assert.Equal(failedDuration.Available, summary.Available);
        Assert.True(summary.SnapshotComplete);
        Assert.Contains(summary.Warnings, warning => warning.Code == "duration warning");
    }

    [Fact]
    public void ContourFailureLeavesIntegrationIncomplete()
    {
        var failedContours = Contours(
            false, "equal_time_contour_segment_budget_exceeded", "contour warning");
        var summary = ForwardRevitFullForwardOrchestratorV0.Run(
            () => Multi(), () => Snapshot(), () => Pipeline(Duration(), failedContours));

        AssertStopped(summary, "duration", "equal_time_contours",
            "equal_time_contour_segment_budget_exceeded");
        Assert.Equal(failedContours.Available, summary.Available);
        Assert.True(summary.DurationComplete);
        Assert.False(summary.ContoursComplete);
        Assert.Equal(12, summary.DurationGridPointCount);
        Assert.Contains(summary.Warnings, warning => warning.Code == "contour warning");
    }

    [Fact]
    public void EveryStageSuccessCompletesWithoutPermitCertification()
    {
        var summary = ForwardRevitFullForwardOrchestratorV0.Run(
            () => Multi(warning: "multi warning"),
            () => Snapshot(warning: "snapshot warning"),
            () => Pipeline(Duration(warning: "duration warning"),
                Contours(warning: "contour warning")));

        Assert.True(summary.Available);
        Assert.True(summary.Complete);
        Assert.Equal("equal_time_contours", summary.FinalCompletedStage);
        Assert.Null(summary.BlockerStage);
        Assert.True(summary.MultiTimeComplete);
        Assert.True(summary.SnapshotComplete);
        Assert.True(summary.DurationComplete);
        Assert.True(summary.ContoursComplete);
        Assert.Equal(12, summary.DurationGridPointCount);
        Assert.Equal(2, summary.ContourCount);
        Assert.Empty(summary.Blockers);
        Assert.Collection(summary.Warnings,
            warning => AssertWarning(warning, "test", null, "multi warning"),
            warning => AssertWarning(warning, "unified_snapshot", null, "snapshot warning"),
            warning => AssertWarning(warning, "duration", null, "duration warning"),
            warning => AssertWarning(warning, "equal_time_contours", null, "contour warning"));
        Assert.False(summary.PermitReadyCertified);
    }

    [Fact]
    public void MultiTimeWarningsPreserveStageSampleIndexCodeAndDuplicates()
    {
        var warnings = new[] {
            new ForwardRevitStageWarningV0 { Stage = "projection", SampleIndex = 0, Code = "same_warning" },
            new ForwardRevitStageWarningV0 { Stage = "projection", SampleIndex = 1, Code = "same_warning" }
        };

        var summary = ForwardRevitFullForwardOrchestratorV0.Run(
            () => Multi(warnings: warnings), () => Snapshot(), () => Pipeline());

        Assert.Collection(summary.Warnings,
            warning => AssertWarning(warning, "projection", 0, "same_warning"),
            warning => AssertWarning(warning, "projection", 1, "same_warning"));
    }

    private static void AssertWarning(ForwardRevitStageWarningV0 warning,
        string stage, int? sampleIndex, string code)
    {
        Assert.Equal(stage, warning.Stage);
        Assert.Equal(sampleIndex, warning.SampleIndex);
        Assert.Equal(code, warning.Code);
    }

    private static void AssertStopped(ForwardRevitFullForwardSummaryV0 summary,
        string finalCompletedStage, string blockerStage, string blocker)
    {
        Assert.False(summary.Complete);
        Assert.Equal(finalCompletedStage, summary.FinalCompletedStage);
        Assert.Equal(blockerStage, summary.BlockerStage);
        Assert.Contains(blocker, summary.Blockers);
        Assert.False(summary.PermitReadyCertified);
    }

    private static ForwardRevitMultiTimeSummaryV0 Multi(bool complete = true,
        string? blocker = null, string? warning = null,
        System.Collections.Generic.IReadOnlyList<ForwardRevitStageWarningV0>? warnings = null) => new() {
            Available = complete, Complete = complete,
            Blockers = blocker is null ? System.Array.Empty<string>() : new[] { blocker },
            Warnings = warnings ?? (warning is null ? System.Array.Empty<ForwardRevitStageWarningV0>() :
                new[] { new ForwardRevitStageWarningV0 { Stage = "test", Code = warning } })
        };

    private static ForwardUnifiedShadowSliceSnapshotV0 Snapshot(bool complete = true,
        string? blocker = null, string? warning = null) => new() {
            Available = complete, Complete = complete,
            Blockers = blocker is null ? System.Array.Empty<string>() : new[] { blocker },
            Warnings = warning is null ? System.Array.Empty<string>() : new[] { warning }
        };

    private static ForwardShadowDurationResultV0 Duration(bool complete = true,
        string? blocker = null, string? warning = null) => new() {
            Available = complete, Complete = complete, GridPointCount = 12,
            Blockers = blocker is null ? System.Array.Empty<string>() : new[] { blocker },
            Warnings = warning is null ? System.Array.Empty<string>() : new[] { warning }
        };

    private static ForwardEqualTimeContourResultV0 Contours(bool complete = true,
        string? blocker = null, string? warning = null) => new() {
            Available = complete, Complete = complete,
            Contours = complete ? new[] { new EqualTimeContourV0(), new EqualTimeContourV0() } :
                System.Array.Empty<EqualTimeContourV0>(),
            Blockers = blocker is null ? System.Array.Empty<string>() : new[] { blocker },
            Warnings = warning is null ? System.Array.Empty<string>() : new[] { warning }
        };

    private static ForwardPostUnionPipelineBuildResultV0 Pipeline(
        ForwardShadowDurationResultV0? duration = null,
        ForwardEqualTimeContourResultV0? contours = null) => new() {
            Result = new ForwardPostUnionPipelineResultV0 {
                Available = true,
                Complete = (duration ?? Duration()).Complete && (contours ?? Contours()).Complete,
                Duration = duration ?? Duration(),
                EqualTimeContours = contours ?? Contours()
            }
        };
}
