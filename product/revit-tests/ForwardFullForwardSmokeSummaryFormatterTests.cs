using RevitShadow;
using ShadowCore;
using Xunit;

namespace RevitShadow.Tests;

public sealed class ForwardFullForwardSmokeSummaryFormatterTests
{
    [Fact]
    public void FormatsSuccessfulSummaryWithoutPermitCertification()
    {
        var summary = ForwardRevitFullForwardOrchestratorV0.Run(
            () => MultiTime(), () => Snapshot(),
            () => Pipeline(Duration(), Contours(3)));
        var text = ForwardFullForwardSmokeSummaryFormatter.Format(summary);

        Assert.Contains("available: true", text);
        Assert.Contains("complete: true", text);
        Assert.Contains("final completed stage: equal_time_contours", text);
        Assert.Contains("blocker stage: none", text);
        Assert.Contains("duration grid point count: 42", text);
        Assert.Contains("contour count: 3", text);
        Assert.Contains("blockers: none", text);
        Assert.Contains("warnings: none", text);
        Assert.Contains("permit_ready_certified = false", text);
    }

    [Fact]
    public void FormatsBlockersAndStructuredWarnings()
    {
        var summary = ForwardRevitFullForwardOrchestratorV0.Run(
            () => MultiTime(), () => Snapshot(),
            () => Pipeline(Duration(
                complete: false,
                blocker: "max_duration_grid_points_exceeded",
                warning: "grid_warning"), Contours()));
        var text = ForwardFullForwardSmokeSummaryFormatter.Format(summary);

        Assert.Contains("blocker stage: duration", text);
        Assert.Contains("blockers: max_duration_grid_points_exceeded", text);
        Assert.Contains("warnings: duration:grid_warning", text);
    }

    private static ForwardRevitMultiTimeSummaryV0 MultiTime() => new() {
        Available = true, Complete = true
    };

    private static ForwardUnifiedShadowSliceSnapshotV0 Snapshot() => new() {
        Available = true, Complete = true
    };

    private static ForwardShadowDurationResultV0 Duration(bool complete = true,
        string? blocker = null, string? warning = null) => new() {
            Available = complete, Complete = complete, GridPointCount = 42,
            Blockers = blocker is null ? System.Array.Empty<string>() : new[] { blocker },
            Warnings = warning is null ? System.Array.Empty<string>() : new[] { warning }
        };

    private static ForwardEqualTimeContourResultV0 Contours(int count = 0) => new() {
        Available = true, Complete = true,
        Contours = System.Linq.Enumerable.Range(0, count)
            .Select(_ => new EqualTimeContourV0()).ToArray()
    };

    private static ForwardPostUnionPipelineBuildResultV0 Pipeline(
        ForwardShadowDurationResultV0 duration,
        ForwardEqualTimeContourResultV0 contours) => new() {
            Result = new ForwardPostUnionPipelineResultV0 {
                Available = duration.Complete && contours.Complete,
                Complete = duration.Complete && contours.Complete,
                Duration = duration,
                EqualTimeContours = contours
            }
        };
}
