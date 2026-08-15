using System;
using ShadowCore;

namespace DynamoShadow;

/// <summary>Minimal Zero-Touch entry point for the compiled-host proof of load.</summary>
public static class AccuracyPresetNodes
{
    public static double GetGridResolutionMeters(string presetId)
    {
        if (!AccuracyPresets.TryResolve(presetId, out var preset) || preset is null)
        {
            throw new ArgumentException("Unknown accuracy preset.", nameof(presetId));
        }

        return preset.GridResolutionM;
    }
}
