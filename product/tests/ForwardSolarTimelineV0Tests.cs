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
    public void NonDivisibleStepStillIncludesOrderedEndSample()
    {
        var actual = ForwardSolarTimelineV0.Build(new ForwardSolarTimelineInputV0 {
            LatitudeDeg = 35.6812, SolarDeclinationDeg = -23.439, TrueNorthDeg = 0,
            TrueSolarStartMinutes = 600, TrueSolarEndMinutes = 800, SunTimeStepMinutes = 70 });
        Assert.Equal(new[] { 600d, 670d, 740d, 800d }, actual.Samples.Select(x => x.TrueSolarMinutes));
    }
}
