using System;
using System.Collections.Generic;

namespace RevitShadow;

/// <summary>JSON-safe diagnostic summary; it never contains Revit objects.</summary>
public sealed class ForwardRevitFormalShadowSummaryV0
{
    public bool Available { get; private set; }
    public bool Complete { get; private set; }
    public int InputSolidCount { get; private set; }
    public int ClippedComponentCount { get; private set; }
    public int ProjectedComponentCount { get; private set; }
    public int CurveLoopCount { get; private set; }
    public bool DirectionValidationPassed { get; private set; }
    public bool ExtentValidationPassed { get; private set; }
    public IReadOnlyList<string> Blockers { get; private set; } = Array.Empty<string>();
    public IReadOnlyList<string> Warnings { get; private set; } = Array.Empty<string>();
    public bool PermitReadyCertified => false;

    public static ForwardRevitFormalShadowSummaryV0 Create(
        int inputSolidCount,
        int clippedComponentCount,
        int projectedComponentCount,
        int curveLoopCount,
        ForwardFormalShadowDirectionV0 direction,
        bool directionValidationPassed,
        bool extentValidationAttempted,
        bool extentValidationPassed,
        IEnumerable<string>? operationBlockers = null,
        IEnumerable<string>? warnings = null)
    {
        var blockers = operationBlockers is null
            ? new List<string>() : new List<string>(operationBlockers);
        if (!direction.Valid)
        {
            blockers.Add(direction.FailureCode ?? "invalid_shadow_direction_vector");
        }
        else if (!directionValidationPassed)
        {
            blockers.Add("direction_validation_failed");
        }
        if (projectedComponentCount == 0 || curveLoopCount == 0)
        {
            blockers.Add("no_valid_native_line_shadow_loop");
        }
        if (projectedComponentCount > 0 && (!extentValidationAttempted || !extentValidationPassed))
        {
            blockers.Add(extentValidationAttempted
                ? "runtime_projection_validation_failed"
                : "runtime_projection_validation_unverified");
        }

        return new ForwardRevitFormalShadowSummaryV0
        {
            Available = curveLoopCount > 0,
            Complete = blockers.Count == 0,
            InputSolidCount = inputSolidCount,
            ClippedComponentCount = clippedComponentCount,
            ProjectedComponentCount = projectedComponentCount,
            CurveLoopCount = curveLoopCount,
            DirectionValidationPassed = directionValidationPassed,
            ExtentValidationPassed = extentValidationAttempted && extentValidationPassed,
            Blockers = blockers,
            Warnings = warnings is null ? Array.Empty<string>() : new List<string>(warnings),
        };
    }
}
