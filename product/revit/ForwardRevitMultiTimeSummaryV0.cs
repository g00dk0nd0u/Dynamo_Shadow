using System;
using System.Collections.Generic;
using ShadowCore;

namespace RevitShadow;

public sealed class ForwardRevitTimeSliceSummaryV0
{
    public int SampleIndex { get; set; }
    public double TrueSolarMinutes { get; set; }
    public double ShadowDirectionModelX { get; set; }
    public double ShadowDirectionModelY { get; set; }
    public double ShadowLengthFactor { get; set; }
    public bool Complete { get; set; }
    public IReadOnlyList<string> Blockers { get; set; } = Array.Empty<string>();
    public bool PermitReadyCertified => false;
}

public sealed class ForwardRevitTimeSliceOutcomeV0
{
    public bool Complete { get; set; }
    public IReadOnlyList<string> Blockers { get; set; } = Array.Empty<string>();
}

public sealed class ForwardRevitMultiTimeSummaryV0
{
    public bool Available { get; set; }
    public bool Complete { get; set; }
    public IReadOnlyList<ForwardRevitTimeSliceSummaryV0> Slices { get; set; } = Array.Empty<ForwardRevitTimeSliceSummaryV0>();
    public int? BlockerSampleIndex { get; set; }
    public IReadOnlyList<string> Blockers { get; set; } = Array.Empty<string>();
    public bool PermitReadyCertified => false;
}

/// <summary>Autodesk-free sequencing boundary; the callback owns host-specific work.</summary>
public static class ForwardRevitMultiTimeOrchestratorV0
{
    public static ForwardRevitMultiTimeSummaryV0 Run(SolarResultV0 solar,
        Func<SolarSampleV0, ForwardRevitTimeSliceOutcomeV0> executeSlice)
    {
        if (solar is null) throw new ArgumentNullException(nameof(solar));
        if (executeSlice is null) throw new ArgumentNullException(nameof(executeSlice));
        var slices = new List<ForwardRevitTimeSliceSummaryV0>();
        if (!solar.Complete)
            return new ForwardRevitMultiTimeSummaryV0 { Slices = slices,
                BlockerSampleIndex = solar.Samples.Count, Blockers = new List<string>(solar.Blockers) };
        foreach (var sample in solar.Samples)
        {
            var outcome = executeSlice(sample);
            var slice = new ForwardRevitTimeSliceSummaryV0 {
                SampleIndex = sample.SampleIndex, TrueSolarMinutes = sample.TrueSolarMinutes,
                ShadowDirectionModelX = sample.ShadowDirectionModel.X,
                ShadowDirectionModelY = sample.ShadowDirectionModel.Y,
                ShadowLengthFactor = sample.ShadowLengthFactor,
                Complete = outcome.Complete, Blockers = outcome.Blockers
            };
            slices.Add(slice);
            if (!slice.Complete)
                return new ForwardRevitMultiTimeSummaryV0 { Slices = slices,
                    BlockerSampleIndex = sample.SampleIndex, Blockers = slice.Blockers };
        }
        return new ForwardRevitMultiTimeSummaryV0 { Available = true, Complete = true, Slices = slices };
    }
}
