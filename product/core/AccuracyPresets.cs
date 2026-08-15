using System;
using System.Collections.Generic;

namespace ShadowCore;

/// <summary>
/// Small semantic port of runtime/shadow_accuracy_presets.py used to prove the
/// portable core boundary. Python remains the behavioral source of truth.
/// </summary>
public static class AccuracyPresets
{
    private static readonly IReadOnlyDictionary<string, AccuracyPreset> Presets =
        new Dictionary<string, AccuracyPreset>(StringComparer.Ordinal)
        {
            ["rough"] = new AccuracyPreset("rough", 1.0, 30),
            ["standard"] = new AccuracyPreset("standard", 0.5, 15),
            ["high"] = new AccuracyPreset("high", 0.25, 5),
        };

    public static bool TryResolve(string? value, out AccuracyPreset? preset)
    {
        var presetId = value?.Trim() ?? string.Empty;
        return Presets.TryGetValue(presetId, out preset);
    }
}

public sealed class AccuracyPreset
{
    public AccuracyPreset(string presetId, double gridResolutionM, int sunTimeStepMinutes)
    {
        PresetId = presetId;
        GridResolutionM = gridResolutionM;
        SunTimeStepMinutes = sunTimeStepMinutes;
    }

    public string PresetId { get; }

    public double GridResolutionM { get; }

    public int SunTimeStepMinutes { get; }
}
