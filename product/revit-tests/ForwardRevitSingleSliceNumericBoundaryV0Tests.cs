using RevitShadow;
using Xunit;

namespace RevitShadow.Tests;

public sealed class ForwardRevitSingleSliceNumericBoundaryV0Tests
{
    [Fact]
    public void MeasurementPlaneConversionFailureUsesPhase5FAContract()
    {
        var calls = 0;
        var actual = ForwardRevitSingleSliceNumericBoundaryV0.Resolve(4, .01, value => {
            calls++; throw new InvalidOperationException();
        });
        Assert.Equal(1, calls);
        Assert.False(actual.Complete);
        Assert.Equal("measurement_plane_unit_conversion_failed", actual.Blocker);
    }

    [Theory]
    [InlineData(double.NaN)]
    [InlineData(double.PositiveInfinity)]
    [InlineData(-0.01)]
    public void InvalidValidationToleranceUsesPhase5FAContract(double tolerance)
    {
        var actual = ForwardRevitSingleSliceNumericBoundaryV0.Resolve(4, tolerance, value => value);
        Assert.False(actual.Complete);
        Assert.Equal("numeric_conversion_failed", actual.Blocker);
    }

    [Fact]
    public void ValidationToleranceConversionFailureUsesNumericContract()
    {
        var calls = 0;
        var actual = ForwardRevitSingleSliceNumericBoundaryV0.Resolve(4, .01, value => {
            calls++; return calls == 1 ? value : throw new InvalidOperationException();
        });
        Assert.False(actual.Complete);
        Assert.Equal("numeric_conversion_failed", actual.Blocker);
    }
}
