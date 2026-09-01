using RevitShadow;
using Xunit;

namespace RevitShadow.Tests;

public sealed class ForwardFullForwardSmokeSummaryFormatterTests
{
    [Fact]
    public void FormatsSuccessfulSummaryWithoutPermitCertification()
    {
        var text = ForwardFullForwardSmokeSummaryFormatter.Format(new ForwardRevitFullForwardSummaryV0 {
            Available = true, Complete = true, FinalCompletedStage = "equal_time_contours",
            DurationGridPointCount = 42, ContourCount = 3
        });

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
        var text = ForwardFullForwardSmokeSummaryFormatter.Format(new ForwardRevitFullForwardSummaryV0 {
            FinalCompletedStage = "unified_snapshot", BlockerStage = "duration",
            Blockers = new[] { "max_duration_grid_points_exceeded" },
            Warnings = new[] {
                new ForwardRevitStageWarningV0 { Stage = "projection", SampleIndex = 2, Code = "sample_warning" },
                new ForwardRevitStageWarningV0 { Stage = "duration", Code = "grid_warning" }
            }
        });

        Assert.Contains("blocker stage: duration", text);
        Assert.Contains("blockers: max_duration_grid_points_exceeded", text);
        Assert.Contains("warnings: projection[2]:sample_warning, duration:grid_warning", text);
    }
}
