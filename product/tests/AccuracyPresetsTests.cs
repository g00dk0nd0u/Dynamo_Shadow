using ShadowCore;
using Xunit;

namespace ShadowCore.Tests;

public sealed class AccuracyPresetsTests
{
    [Theory]
    [InlineData("rough", 1.0, 30)]
    [InlineData("standard", 0.5, 15)]
    [InlineData("high", 0.25, 5)]
    public void ResolvesCanonicalPythonPresetValues(
        string id,
        double expectedResolution,
        int expectedMinutes)
    {
        Assert.True(AccuracyPresets.TryResolve(id, out var preset));
        Assert.NotNull(preset);
        Assert.Equal(id, preset.PresetId);
        Assert.Equal(expectedResolution, preset.GridResolutionM, precision: 10);
        Assert.Equal(expectedMinutes, preset.SunTimeStepMinutes);
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
}
