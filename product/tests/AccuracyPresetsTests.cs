using System.Text.Json;
using System.Text.Json.Serialization;
using ShadowCore;
using Xunit;

namespace ShadowCore.Tests;

public sealed class AccuracyPresetsTests
{
    [Fact]
    public void ResolvesValuesFromSharedPythonCSharpParityFixture()
    {
        var fixturePath = Path.Combine(
            AppContext.BaseDirectory,
            "fixtures",
            "parity",
            "accuracy_presets.json");
        var expectedPresets = JsonSerializer.Deserialize<Dictionary<string, PresetFixture>>(
            File.ReadAllText(fixturePath));

        Assert.NotNull(expectedPresets);
        foreach (var expected in expectedPresets)
        {
            Assert.True(AccuracyPresets.TryResolve(expected.Key, out var preset));
            Assert.NotNull(preset);
            Assert.Equal(expected.Key, preset.PresetId);
            Assert.Equal(expected.Value.GridResolutionM, preset.GridResolutionM, precision: 10);
            Assert.Equal(expected.Value.SunTimeStepMinutes, preset.SunTimeStepMinutes);
        }
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("FAST")]
    public void RejectsValuesRejectedByCanonicalPythonResolver(string? value)
    {
        Assert.False(AccuracyPresets.TryResolve(value, out var preset));
        Assert.Null(preset);
    }

    private sealed class PresetFixture
    {
        [JsonPropertyName("grid_resolution_m")]
        public double GridResolutionM { get; init; }

        [JsonPropertyName("sun_time_step_minutes")]
        public int SunTimeStepMinutes { get; init; }
    }
}
