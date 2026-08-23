using RevitShadow;
using Xunit;

namespace RevitShadow.Tests;

public sealed class ForwardRevitSingleSliceIntegrationSummaryV0Tests
{
    [Fact]
    public void ProjectContextFailureStopsBeforeCaster()
    {
        var context = Context(false, "latitude_missing");
        var summary = ForwardRevitSingleSliceIntegrationSummaryV0.Create(context);

        AssertStopped(summary, "none", "project_context", "latitude_missing");
        Assert.False(summary.CasterExtractionComplete);
    }

    [Fact]
    public void CasterFailureStopsBeforeProjection()
    {
        var caster = ForwardRevitCasterGeometrySummaryV0.Create(1, 1, 0, 0, 0);
        var summary = ForwardRevitSingleSliceIntegrationSummaryV0.Create(Context(), caster);

        AssertStopped(summary, "project_context", "caster_extraction", "no_shadow_caster_solids");
        Assert.False(summary.ProjectionComplete);
    }

    [Fact]
    public void ProjectionFailureStopsBeforeUnion()
    {
        var summary = ForwardRevitSingleSliceIntegrationSummaryV0.Create(
            Context(), Caster(), Projection(false));

        AssertStopped(summary, "caster_extraction", "projection", "no_valid_native_line_shadow_loop");
        Assert.False(summary.UnionComplete);
    }

    [Fact]
    public void UnionFailureLeavesIntegrationIncomplete()
    {
        var union = ForwardRevitFormalShadowUnionSummaryV0.Create(
            1, 0, 0, 1, 0, 1, 0, 10, 0, 10, .01,
            new[] { "revit_boolean_union_failed" });
        var summary = ForwardRevitSingleSliceIntegrationSummaryV0.Create(
            Context(), Caster(), Projection(), union);

        AssertStopped(summary, "projection", "union", "revit_boolean_union_failed");
    }

    [Fact]
    public void EveryCompleteStageCompletesIntegrationButNeverCertifiesPermitReadiness()
    {
        var union = ForwardRevitFormalShadowUnionSummaryV0.Create(
            1, 1, 1, 0, 0, 0, 0, 10, 10, 10, .01);
        var summary = ForwardRevitSingleSliceIntegrationSummaryV0.Create(
            Context(), Caster(), Projection(), union);

        Assert.True(summary.Available);
        Assert.True(summary.Complete);
        Assert.Equal("union", summary.CompletedStage);
        Assert.True(summary.ProjectContextComplete);
        Assert.True(summary.CasterExtractionComplete);
        Assert.True(summary.ProjectionComplete);
        Assert.True(summary.UnionComplete);
        Assert.Null(summary.BlockerStage);
        Assert.Empty(summary.Blockers);
        Assert.False(summary.PermitReadyCertified);
    }

    private static void AssertStopped(ForwardRevitSingleSliceIntegrationSummaryV0 summary,
        string completedStage, string blockerStage, string blocker)
    {
        Assert.False(summary.Complete);
        Assert.Equal(completedStage, summary.CompletedStage);
        Assert.Equal(blockerStage, summary.BlockerStage);
        Assert.Contains(blocker, summary.Blockers);
        Assert.False(summary.PermitReadyCertified);
    }

    private static ForwardRevitProjectContextResultV0 Context(bool complete = true, string? blocker = null)
    {
        var result = new ForwardRevitProjectContextResultV0 { Available = complete, Complete = complete };
        if (blocker is not null) result.Blockers.Add(blocker);
        return result;
    }

    private static ForwardRevitCasterGeometrySummaryV0 Caster() =>
        ForwardRevitCasterGeometrySummaryV0.Create(1, 1, 1, 0, 0);

    private static ForwardRevitFormalShadowSummaryV0 Projection(bool complete = true) =>
        ForwardRevitFormalShadowSummaryV0.Create(1, 1, complete ? 1 : 0, complete ? 1 : 0,
            ForwardFormalShadowDirectionV0.Create(0, 1, 2), true,
            extentValidationAttempted: complete, extentValidationPassed: complete);
}
