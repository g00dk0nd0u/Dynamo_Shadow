using RevitShadow;
using Xunit;

namespace RevitShadow.Tests;

public sealed class ForwardRevitCasterGeometrySummaryV0Tests
{
    [Fact]
    public void ZeroInputIsIncompleteAndNeverPermitCertified()
    {
        var summary = ForwardRevitCasterGeometrySummaryV0.Create(0, 0, 0, 0, 0);

        Assert.False(summary.Complete);
        Assert.Equal(new[] { "caster_elements_required" }, summary.Blockers);
        Assert.False(summary.PermitReadyCertified);
    }

    [Fact]
    public void InputWithoutSupportedElementsIsIncomplete()
    {
        var summary = ForwardRevitCasterGeometrySummaryV0.Create(2, 0, 0, 0, 2);

        Assert.False(summary.Complete);
        Assert.Equal(new[] { "no_supported_caster_elements" }, summary.Blockers);
    }

    [Fact]
    public void SupportedElementsWithoutSolidsAreIncomplete()
    {
        var summary = ForwardRevitCasterGeometrySummaryV0.Create(2, 1, 0, 1, 3);

        Assert.False(summary.Complete);
        Assert.Equal(new[] { "no_shadow_caster_solids" }, summary.Blockers);
    }

    [Fact]
    public void PositiveSolidCountIsCompleteAndRetainsDeterministicDiagnostics()
    {
        var warnings = new[] { "caster_element_geometry_read_failed", "mesh_geometry_ignored" };
        var first = ForwardRevitCasterGeometrySummaryV0.Create(3, 2, 1, 4, 5, warnings);
        var second = ForwardRevitCasterGeometrySummaryV0.Create(3, 2, 1, 4, 5, warnings);

        Assert.True(first.Complete);
        Assert.Empty(first.Blockers);
        Assert.Equal(warnings, first.Warnings);
        Assert.Equal(first.Blockers, second.Blockers);
        Assert.Equal(first.Warnings, second.Warnings);
        Assert.Equal(3, first.InputElementCount);
        Assert.Equal(2, first.SupportedElementCount);
        Assert.Equal(1, first.SolidCount);
        Assert.Equal(4, first.GeometryInstanceCount);
        Assert.Equal(5, first.IgnoredGeometryCount);
        Assert.False(first.PermitReadyCertified);
    }
}
