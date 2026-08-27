using RevitShadow;
using ShadowCore;
using Xunit;

namespace RevitShadow.Tests;

public sealed class ForwardRevitFullForwardOrchestratorV0Tests
{
    [Fact]
    public void MultiTimeFailureStopsAllLaterStages()
    {
        var calls = new int[3];
        var summary = ForwardRevitFullForwardOrchestratorV0.Run(
            () => Multi(false, "solar_input_invalid", "multi warning"),
            () => { calls[0]++; return Snapshot(); },
            () => { calls[1]++; return Duration(); },
            () => { calls[2]++; return Contours(); });

        Assert.Equal(new[] { 0, 0, 0 }, calls);
        AssertStopped(summary, "none", "multi_time_forward", "solar_input_invalid");
        Assert.Contains("multi warning", summary.Warnings);
    }

    [Fact]
    public void SnapshotFailureStopsDurationAndContours()
    {
        var laterCalls = 0;
        var summary = ForwardRevitFullForwardOrchestratorV0.Run(
            () => Multi(),
            () => Snapshot(false, "union_output_loop_invalid", "snapshot warning"),
            () => { laterCalls++; return Duration(); },
            () => { laterCalls++; return Contours(); });

        Assert.Equal(0, laterCalls);
        AssertStopped(summary, "multi_time_forward", "unified_snapshot", "union_output_loop_invalid");
        Assert.True(summary.MultiTimeComplete);
        Assert.Contains("snapshot warning", summary.Warnings);
    }

    [Fact]
    public void DurationFailureStopsContours()
    {
        var contourCalls = 0;
        var summary = ForwardRevitFullForwardOrchestratorV0.Run(
            () => Multi(), () => Snapshot(),
            () => Duration(false, "max_duration_grid_points_exceeded", "duration warning"),
            () => { contourCalls++; return Contours(); });

        Assert.Equal(0, contourCalls);
        AssertStopped(summary, "unified_snapshot", "duration", "max_duration_grid_points_exceeded");
        Assert.True(summary.SnapshotComplete);
        Assert.Contains("duration warning", summary.Warnings);
    }

    [Fact]
    public void ContourFailureLeavesIntegrationIncomplete()
    {
        var summary = ForwardRevitFullForwardOrchestratorV0.Run(
            () => Multi(), () => Snapshot(), () => Duration(),
            () => Contours(false, "equal_time_contour_segment_budget_exceeded", "contour warning"));

        AssertStopped(summary, "duration", "equal_time_contours",
            "equal_time_contour_segment_budget_exceeded");
        Assert.True(summary.DurationComplete);
        Assert.False(summary.ContoursComplete);
        Assert.Equal(12, summary.DurationGridPointCount);
        Assert.Contains("contour warning", summary.Warnings);
    }

    [Fact]
    public void EveryStageSuccessCompletesWithoutPermitCertification()
    {
        var summary = ForwardRevitFullForwardOrchestratorV0.Run(
            () => Multi(warning: "multi warning"),
            () => Snapshot(warning: "snapshot warning"),
            () => Duration(warning: "duration warning"),
            () => Contours(warning: "contour warning"));

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
        Assert.Equal(new[] { "multi warning", "snapshot warning", "duration warning", "contour warning" },
            summary.Warnings);
        Assert.False(summary.PermitReadyCertified);
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
        string? blocker = null, string? warning = null) => new() {
            Available = complete, Complete = complete,
            Blockers = blocker is null ? System.Array.Empty<string>() : new[] { blocker },
            Warnings = warning is null ? System.Array.Empty<ForwardRevitStageWarningV0>() :
                new[] { new ForwardRevitStageWarningV0 { Stage = "test", Code = warning } }
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
}
