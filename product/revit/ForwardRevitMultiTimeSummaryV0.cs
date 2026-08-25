using System;
using System.Collections.Generic;
using ShadowCore;

namespace RevitShadow;

public sealed class ForwardRevitStageWarningV0
{
    public string Stage { get; set; } = "unknown";
    public int? SampleIndex { get; set; }
    public string Code { get; set; } = "";
}

public sealed class ForwardRevitTimeSliceSummaryV0
{
    public int SampleIndex { get; set; }
    public double TrueSolarMinutes { get; set; }
    public double ShadowDirectionModelX { get; set; }
    public double ShadowDirectionModelY { get; set; }
    public double ShadowLengthFactor { get; set; }
    public bool Complete { get; set; }
    public string? BlockerStage { get; set; }
    public IReadOnlyList<string> Blockers { get; set; } = Array.Empty<string>();
    public IReadOnlyList<ForwardRevitStageWarningV0> Warnings { get; set; } = Array.Empty<ForwardRevitStageWarningV0>();
    public bool PermitReadyCertified => false;
}

public sealed class ForwardRevitTimeSliceOutcomeV0
{
    public bool Complete { get; set; }
    public string? BlockerStage { get; set; }
    public IReadOnlyList<string> Blockers { get; set; } = Array.Empty<string>();
    public IReadOnlyList<ForwardRevitStageWarningV0> Warnings { get; set; } = Array.Empty<ForwardRevitStageWarningV0>();
}

public sealed class ForwardRevitMultiTimeSummaryV0
{
    public bool Available { get; set; }
    public bool Complete { get; set; }
    public IReadOnlyList<ForwardRevitTimeSliceSummaryV0> Slices { get; set; } = Array.Empty<ForwardRevitTimeSliceSummaryV0>();
    public int? BlockerSampleIndex { get; set; }
    public IReadOnlyList<string> Blockers { get; set; } = Array.Empty<string>();
    public IReadOnlyList<ForwardRevitStageWarningV0> Warnings { get; set; } = Array.Empty<ForwardRevitStageWarningV0>();
    public bool PermitReadyCertified => false;
}

/// <summary>Autodesk-free sequencing boundary; the callback owns host-specific work.</summary>
public static class ForwardRevitMultiTimeOrchestratorV0
{
    public static ForwardRevitMultiTimeSummaryV0 Run(SolarResultV0 solar,
        Func<SolarSampleV0, ForwardRevitTimeSliceOutcomeV0> executeSlice,
        IReadOnlyList<ForwardRevitStageWarningV0>? initialWarnings = null)
    {
        if (solar is null) throw new ArgumentNullException(nameof(solar));
        if (executeSlice is null) throw new ArgumentNullException(nameof(executeSlice));
        var slices = new List<ForwardRevitTimeSliceSummaryV0>();
        var warnings = new List<ForwardRevitStageWarningV0>(initialWarnings ?? Array.Empty<ForwardRevitStageWarningV0>());
        foreach (var warning in solar.Warnings)
            warnings.Add(new ForwardRevitStageWarningV0 { Stage = "solar", Code = warning });
        if (!solar.Complete)
            return new ForwardRevitMultiTimeSummaryV0 { Slices = slices,
                BlockerSampleIndex = solar.Samples.Count, Blockers = new List<string>(solar.Blockers), Warnings = warnings };
        foreach (var sample in solar.Samples)
        {
            var outcome = executeSlice(sample);
            var slice = new ForwardRevitTimeSliceSummaryV0 {
                SampleIndex = sample.SampleIndex, TrueSolarMinutes = sample.TrueSolarMinutes,
                ShadowDirectionModelX = sample.ShadowDirectionModel.X,
                ShadowDirectionModelY = sample.ShadowDirectionModel.Y,
                ShadowLengthFactor = sample.ShadowLengthFactor,
                Complete = outcome.Complete, BlockerStage = outcome.BlockerStage,
                Blockers = outcome.Blockers, Warnings = outcome.Warnings
            };
            slices.Add(slice);
            warnings.AddRange(outcome.Warnings);
            if (!slice.Complete)
                return new ForwardRevitMultiTimeSummaryV0 { Slices = slices,
                    BlockerSampleIndex = sample.SampleIndex, Blockers = slice.Blockers, Warnings = warnings };
        }
        return new ForwardRevitMultiTimeSummaryV0 { Available = true, Complete = true,
            Slices = slices, Warnings = warnings };
    }
}
