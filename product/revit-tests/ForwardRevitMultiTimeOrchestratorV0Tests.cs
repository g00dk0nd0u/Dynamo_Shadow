using RevitShadow;
using ShadowCore;
using Xunit;

namespace RevitShadow.Tests;

public sealed class ForwardRevitMultiTimeOrchestratorV0Tests
{
    [Fact]
    public void RunsDeterministicallyAndRetainsFirstMiddleLastMetadata()
    {
        var solar = Solar();
        var visited = new List<int>();
        var actual = ForwardRevitMultiTimeOrchestratorV0.Run(solar, sample => {
            visited.Add(sample.SampleIndex); return Slice(sample, true);
        });
        Assert.Equal(new[] { 0, 1, 2 }, visited);
        Assert.Equal(new[] { 600d, 720d, 840d }, actual.Slices.Select(x => x.TrueSolarMinutes));
        Assert.Equal(solar.Samples[0].ShadowDirectionModel.X, actual.Slices[0].ShadowDirectionModelX);
        Assert.Equal(solar.Samples[1].ShadowLengthFactor, actual.Slices[1].ShadowLengthFactor);
        Assert.Equal(solar.Samples[2].ShadowDirectionModel.Y, actual.Slices[2].ShadowDirectionModelY);
        Assert.True(actual.Complete);
        Assert.False(actual.PermitReadyCertified);
        Assert.All(actual.Slices, slice => Assert.False(slice.PermitReadyCertified));
    }

    [Fact]
    public void OneSliceFailureStopsAndPreservesBlockerSampleIndex()
    {
        var visited = new List<int>();
        var actual = ForwardRevitMultiTimeOrchestratorV0.Run(Solar(), sample => {
            visited.Add(sample.SampleIndex);
            return Slice(sample, sample.SampleIndex != 1, "revit_boolean_union_failed");
        });
        Assert.Equal(new[] { 0, 1 }, visited);
        Assert.False(actual.Available);
        Assert.False(actual.Complete);
        Assert.Equal(1, actual.BlockerSampleIndex);
        Assert.Contains("revit_boolean_union_failed", actual.Blockers);
        Assert.False(actual.PermitReadyCertified);
    }

    [Fact]
    public void InvalidSolarSampleIsNotSilentlySkipped()
    {
        var solar = ForwardSolarTimelineV0.Build(new ForwardSolarTimelineInputV0 {
            LatitudeDeg = 35, SolarDeclinationDeg = -23, TrueNorthDeg = 0,
            TrueSolarStartMinutes = 0, TrueSolarEndMinutes = 60, SunTimeStepMinutes = 30 });
        var actual = ForwardRevitMultiTimeOrchestratorV0.Run(solar, _ => throw new Xunit.Sdk.XunitException("must not execute"));
        Assert.False(actual.Complete);
        Assert.Equal(0, actual.BlockerSampleIndex);
        Assert.Contains("solar_sample_at_or_below_horizon", actual.Blockers);
    }

    private static SolarResultV0 Solar() => ForwardSolarTimelineV0.Build(new ForwardSolarTimelineInputV0 {
        LatitudeDeg = 35.6812, SolarDeclinationDeg = -23.439, TrueNorthDeg = 30,
        TrueSolarStartMinutes = 600, TrueSolarEndMinutes = 840, SunTimeStepMinutes = 120 });

    private static ForwardRevitTimeSliceOutcomeV0 Slice(SolarSampleV0 sample, bool complete,
        params string[] blockers) => new() { Complete = complete, Blockers = blockers };
}
