using System.Text.Json;
using ShadowCore;
using Xunit;

namespace ShadowCore.Tests;

public sealed class ForwardSolarTimelineV0Tests
{
    [Fact]
    public void InclusiveTimelineAndTrueNorthDirectionsMatchFrozenPythonFixture()
    {
        using var document = JsonDocument.Parse(File.ReadAllText(Path.Combine(AppContext.BaseDirectory,
            "fixtures", "parity", "forward_solar_true_north_v0.json")));
        var root = document.RootElement;
        var input = root.GetProperty("input");
        var times = input.GetProperty("true_solar_minutes").EnumerateArray().Select(x => x.GetDouble()).ToArray();
        foreach (var item in root.GetProperty("cases").EnumerateArray())
        {
            var actual = ForwardSolarTimelineV0.Build(new ForwardSolarTimelineInputV0 {
                LatitudeDeg = input.GetProperty("latitude_deg").GetDouble(),
                SolarDeclinationDeg = input.GetProperty("solar_declination_deg").GetDouble(),
                TrueNorthDeg = item.GetProperty("true_north_deg").GetDouble(),
                TrueSolarStartMinutes = times[0], TrueSolarEndMinutes = times[^1],
                SunTimeStepMinutes = times[1] - times[0]
            });
            Assert.True(actual.Complete);
            Assert.Equal(times, actual.Samples.Select(x => x.TrueSolarMinutes));
            var expected = item.GetProperty("samples").EnumerateArray().ToArray();
            for (var index = 0; index < expected.Length; index++)
            {
                Assert.Equal(index, actual.Samples[index].SampleIndex);
                Assert.Equal(expected[index].GetProperty("shadow_azimuth_model_deg").GetDouble(),
                    actual.Samples[index].ShadowAzimuthModelDeg, 6);
                Assert.Equal(expected[index].GetProperty("shadow_direction_model").GetProperty("x").GetDouble(),
                    actual.Samples[index].ShadowDirectionModel.X, 12);
                Assert.Equal(expected[index].GetProperty("shadow_direction_model").GetProperty("y").GetDouble(),
                    actual.Samples[index].ShadowDirectionModel.Y, 12);
            }
            Assert.False(actual.PermitReadyCertified);
        }
    }

    [Fact]
    public void NonDivisibleStepDoesNotAppendEndSample()
    {
        var actual = ForwardSolarTimelineV0.Build(new ForwardSolarTimelineInputV0 {
            LatitudeDeg = 35.6812, SolarDeclinationDeg = -23.439, TrueNorthDeg = 0,
            TrueSolarStartMinutes = 600, TrueSolarEndMinutes = 800, SunTimeStepMinutes = 70 });
        Assert.Equal(new[] { 600d, 670d, 740d }, actual.Samples.Select(x => x.TrueSolarMinutes));
    }

    [Fact]
    public void DivisibleStepIncludesEndSample()
    {
        var actual = ForwardSolarTimelineV0.Build(new ForwardSolarTimelineInputV0 {
            LatitudeDeg = 35.6812, SolarDeclinationDeg = -23.439, TrueNorthDeg = 0,
            TrueSolarStartMinutes = 600, TrueSolarEndMinutes = 840, SunTimeStepMinutes = 120 });
        Assert.Equal(new[] { 600d, 720d, 840d }, actual.Samples.Select(x => x.TrueSolarMinutes));
    }

    [Theory]
    [InlineData(double.NaN)]
    [InlineData(double.PositiveInfinity)]
    [InlineData(0)]
    [InlineData(-1)]
    [InlineData(0.5)]
    [InlineData(70.25)]
    public void NonPositiveNonFiniteOrFractionalStepIsInvalid(double step)
    {
        var actual = BuildWithStep(600, 800, step);
        Assert.False(actual.Complete);
        Assert.Contains("invalid_sun_time_step", actual.Blockers);
    }

    [Fact]
    public void NonAdvancingIntegerStepIsInvalid()
    {
        var start = 9007199254740992d;
        var actual = BuildWithStep(start, start + 2, 1);
        Assert.False(actual.Complete);
        Assert.Contains("invalid_sun_time_step", actual.Blockers);
    }

    private static SolarResultV0 BuildWithStep(double start, double end, double step) =>
        ForwardSolarTimelineV0.Build(new ForwardSolarTimelineInputV0 {
            LatitudeDeg = 35.6812, SolarDeclinationDeg = -23.439, TrueNorthDeg = 0,
            TrueSolarStartMinutes = start, TrueSolarEndMinutes = end, SunTimeStepMinutes = step });
}
