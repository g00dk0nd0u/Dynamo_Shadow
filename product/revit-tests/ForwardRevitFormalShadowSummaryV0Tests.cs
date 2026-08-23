using RevitShadow;
using Xunit;

namespace RevitShadow.Tests;

public sealed class ForwardRevitFormalShadowSummaryV0Tests
{
    [Fact]
    public void DirectionContractReversesSignOnlyForAnalyzerBoundary()
    {
        var direction = ForwardFormalShadowDirectionV0.Create(0.6, 0.8, 2.0);

        Assert.True(direction.Valid);
        Assert.True(direction.ContractPassed);
        Assert.True(direction.PhysicalZ < 0.0);
        Assert.True(direction.AnalyzerZ > 0.0);
        Assert.Equal(-direction.PhysicalX, direction.AnalyzerX, 12);
        Assert.Equal(-direction.PhysicalY, direction.AnalyzerY, 12);
        Assert.Equal(-direction.PhysicalZ, direction.AnalyzerZ, 12);
        Assert.Equal(2.0,
            Math.Sqrt(direction.PhysicalX * direction.PhysicalX
                + direction.PhysicalY * direction.PhysicalY) / Math.Abs(direction.PhysicalZ), 12);
    }

    [Fact]
    public void PureDirectionContractIsSeparateFromActualPolygonValidation()
    {
        var direction = ForwardFormalShadowDirectionV0.Create(0.0, 1.0, 2.0);
        var summary = ForwardRevitFormalShadowSummaryV0.Create(1, 1, 1, 1,
            direction, actualPolygonDirectionValidationPassed: false,
            extentValidationAttempted: true, extentValidationPassed: true);

        Assert.True(summary.DirectionVectorContractPassed);
        Assert.False(summary.ActualPolygonDirectionValidationPassed);
        Assert.False(summary.Complete);
        Assert.Contains("runtime_projection_validation_failed", summary.Blockers);
        Assert.DoesNotContain("direction_validation_failed", summary.Blockers);
    }

    [Theory]
    [InlineData(double.NaN, 1.0, 1.0, "invalid_shadow_direction_model_or_factor")]
    [InlineData(1.0, 1.0, 0.0, "invalid_shadow_direction_model_or_factor")]
    [InlineData(1.0, 1.0, 101.0, "shadow_length_factor_exceeds_guard")]
    public void InvalidDirectionOrFactorIsBlocked(double x, double y, double factor, string code)
    {
        var direction = ForwardFormalShadowDirectionV0.Create(x, y, factor);
        Assert.False(direction.Valid);
        Assert.Equal(code, direction.FailureCode);
    }

    [Fact]
    public void ZeroProjectionIsIncomplete()
    {
        var summary = Create(projected: 0, loops: 0, extentAttempted: false, extentPassed: false);
        Assert.False(summary.Complete);
        Assert.Contains("no_valid_native_line_shadow_loop", summary.Blockers);
    }

    [Fact]
    public void ExtentFailureIsIncomplete()
    {
        var summary = Create(projected: 1, loops: 1, extentAttempted: true, extentPassed: false);
        Assert.False(summary.Complete);
        Assert.Contains("runtime_projection_validation_failed", summary.Blockers);
    }

    [Fact]
    public void ValidSummaryIsCompleteAndNeverPermitCertified()
    {
        var summary = Create(projected: 1, loops: 2, extentAttempted: true, extentPassed: true);
        Assert.True(summary.Available);
        Assert.True(summary.Complete);
        Assert.Empty(summary.Blockers);
        Assert.False(summary.PermitReadyCertified);
    }

    private static ForwardRevitFormalShadowSummaryV0 Create(
        int projected, int loops, bool extentAttempted, bool extentPassed) =>
        ForwardRevitFormalShadowSummaryV0.Create(1, 1, projected, loops,
            ForwardFormalShadowDirectionV0.Create(0.0, 1.0, 2.0),
            actualPolygonDirectionValidationPassed: true, extentAttempted, extentPassed);
}
