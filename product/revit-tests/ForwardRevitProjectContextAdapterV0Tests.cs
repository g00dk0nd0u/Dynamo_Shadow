using RevitShadow;
using Xunit;

namespace RevitShadow.Tests;

public sealed class ForwardRevitProjectContextAdapterV0Tests
{
    [Fact]
    public void SelectedLevelIsConvertedOnceAndBuildsMeasurementPlane()
    {
        var conversionCalls = 0;
        var input = ValidInput();
        input.LevelSelected = true;
        input.SelectedLevelElevationInternal = 32.8083989501312;
        input.FallbackAverageGroundLevelElevationM = 99.0;

        var result = ForwardRevitProjectContextAdapterV0.Resolve(input, value =>
        {
            conversionCalls++;
            return value * 0.3048;
        });

        Assert.True(result.Available);
        Assert.True(result.Complete);
        Assert.Equal(1, conversionCalls);
        Assert.Equal(10.0, result.AverageGroundLevelElevationM!.Value, 10);
        Assert.Equal("selected_revit_level", result.AverageGroundLevelSource);
        Assert.Equal(4.0, result.MeasurementHeightM);
        Assert.Equal(14.0, result.MeasurementPlaneElevationM!.Value, 10);
        Assert.Equal(-30.0, result.TrueNorthDeg!.Value, 10);
        Assert.Equal(35.6812, result.LatitudeDeg);
        Assert.False(result.PermitReadyCertified);
        Assert.Empty(result.Blockers);
        Assert.Empty(result.Warnings);
    }

    [Fact]
    public void NoLevelUsesExplicitSettingsFallbackWithoutCallingConverter()
    {
        var input = ValidInput();
        input.LevelSelected = false;
        input.FallbackAverageGroundLevelElevationM = 2.5;

        var result = ForwardRevitProjectContextAdapterV0.Resolve(input, _ => throw new InvalidOperationException());

        Assert.True(result.Complete);
        Assert.Equal(2.5, result.AverageGroundLevelElevationM);
        Assert.Equal("settings_fallback", result.AverageGroundLevelSource);
        Assert.Equal(6.5, result.MeasurementPlaneElevationM);
    }

    [Theory]
    [InlineData(null, "selected_level_elevation_unreadable")]
    [InlineData(double.NaN, "selected_level_internal_elevation_non_finite")]
    public void SelectedLevelFailureNeverUsesSettingsFallback(double? elevation, string blocker)
    {
        var input = ValidInput();
        input.LevelSelected = true;
        input.SelectedLevelElevationInternal = elevation;
        input.FallbackAverageGroundLevelElevationM = 123.0;

        var result = ForwardRevitProjectContextAdapterV0.Resolve(input, value => value);

        Assert.False(result.Available);
        Assert.False(result.Complete);
        Assert.Contains(blocker, result.Blockers);
        Assert.Null(result.AverageGroundLevelElevationM);
        Assert.Null(result.AverageGroundLevelSource);
        Assert.Null(result.MeasurementPlaneElevationM);
    }

    [Fact]
    public void SelectedLevelConversionFailureIsBlockedWithoutFallback()
    {
        var input = ValidInput();
        input.LevelSelected = true;
        input.SelectedLevelElevationInternal = 10.0;
        input.FallbackAverageGroundLevelElevationM = 123.0;

        var result = ForwardRevitProjectContextAdapterV0.Resolve(
            input,
            _ => throw new InvalidOperationException("test conversion failure"));

        Assert.Equal(new[] { "selected_level_unit_conversion_failed" }, result.Blockers);
        Assert.Null(result.AverageGroundLevelElevationM);
    }

    [Theory]
    [InlineData(0.0, 0.0)]
    [InlineData(-Math.PI / 6.0, -30.0)]
    [InlineData(Math.PI / 6.0, 30.0)]
    public void TrueNorthRadiansBecomeSignedDegreesWithoutSignInversion(double radians, double degrees)
    {
        var input = ValidInput();
        input.RawActiveProjectLocationAngleRad = radians;

        var result = ForwardRevitProjectContextAdapterV0.Resolve(input, value => value);

        Assert.Equal(degrees, result.TrueNorthDeg!.Value, 10);
    }

    [Fact]
    public void InvalidIndependentValuesReturnOrderedBlockersWithoutThrowing()
    {
        var input = ValidInput();
        input.LevelSelected = false;
        input.FallbackAverageGroundLevelElevationM = null;
        input.MeasurementHeightM = double.PositiveInfinity;
        input.RawActiveProjectLocationAngleRad = null;
        input.ExplicitLatitudeDeg = double.NaN;

        var first = ForwardRevitProjectContextAdapterV0.Resolve(input, value => value);
        var second = ForwardRevitProjectContextAdapterV0.Resolve(input, value => value);

        var expected = new[]
        {
            "average_ground_level_unavailable",
            "measurement_height_non_finite",
            "true_north_raw_angle_missing",
            "latitude_non_finite",
        };
        Assert.Equal(expected, first.Blockers);
        Assert.Equal(first.Blockers, second.Blockers);
        Assert.Equal(first.Warnings, second.Warnings);
        Assert.Equal(first.AverageGroundLevelSource, second.AverageGroundLevelSource);
        Assert.Equal(first.MeasurementPlaneElevationM, second.MeasurementPlaneElevationM);
        Assert.False(first.PermitReadyCertified);
    }

    [Fact]
    public void MissingMeasurementHeightTrueNorthAndLatitudeAreExplicitBlockers()
    {
        var input = ValidInput();
        input.MeasurementHeightM = null;
        input.RawActiveProjectLocationAngleRad = double.NegativeInfinity;
        input.ExplicitLatitudeDeg = null;

        var result = ForwardRevitProjectContextAdapterV0.Resolve(input, value => value);

        Assert.Equal(
            new[] { "measurement_height_missing", "true_north_raw_angle_non_finite", "latitude_missing" },
            result.Blockers);
    }

    [Fact]
    public void DiagnosticProjectionUsesJsonSafeContractAndNeverCertifiesPermitReadiness()
    {
        var result = ForwardRevitProjectContextAdapterV0.Resolve(ValidInput(), value => value);

        var data = ForwardRevitProjectContextDiagnosticV0.ToData(result);

        Assert.Equal(true, data["available"]);
        Assert.Equal(10.0, data["average_ground_level_elevation_m"]);
        Assert.Equal("settings_fallback", data["average_ground_level_source"]);
        Assert.Equal(-30.0, (double)data["true_north_deg"]!, 10);
        Assert.Empty((string[])data["blockers"]!);
        Assert.Empty((string[])data["warnings"]!);
        Assert.Equal(false, data["permit_ready_certified"]);
    }

    [Fact]
    public void SmokeDiagnosticFormatterIncludesCompleteCompactContract()
    {
        var data = ForwardRevitProjectContextDiagnosticV0.ToData(
            ForwardRevitProjectContextAdapterV0.Resolve(ValidInput(), value => value));

        var text = ForwardProjectContextDiagnosticFormatterV0.Format(data);

        Assert.Contains("available: true", text);
        Assert.Contains("measurement_plane_elevation_m: 14", text);
        Assert.Contains("blockers: (none)", text);
        Assert.Contains("warnings: (none)", text);
        Assert.EndsWith("permit_ready_certified: false", text);
    }

    private static ForwardRevitProjectContextInputV0 ValidInput() => new()
    {
        LevelSelected = false,
        FallbackAverageGroundLevelElevationM = 10.0,
        MeasurementHeightM = 4.0,
        RawActiveProjectLocationAngleRad = -Math.PI / 6.0,
        ExplicitLatitudeDeg = 35.6812,
    };
}
