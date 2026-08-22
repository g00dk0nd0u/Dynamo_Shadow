using System;
using System.Collections.Generic;

namespace RevitShadow;

/// <summary>
/// Host-neutral summary of native Revit caster geometry extraction.
/// This contract never contains Revit API objects.
/// </summary>
public sealed class ForwardRevitCasterGeometrySummaryV0
{
    public bool Complete { get; private set; }
    public int InputElementCount { get; private set; }
    public int SupportedElementCount { get; private set; }
    public int SolidCount { get; private set; }
    public int GeometryInstanceCount { get; private set; }
    public int IgnoredGeometryCount { get; private set; }
    public IReadOnlyList<string> Blockers { get; private set; } = Array.Empty<string>();
    public IReadOnlyList<string> Warnings { get; private set; } = Array.Empty<string>();
    public bool PermitReadyCertified => false;

    public static ForwardRevitCasterGeometrySummaryV0 Create(
        int inputElementCount,
        int supportedElementCount,
        int solidCount,
        int geometryInstanceCount,
        int ignoredGeometryCount,
        IEnumerable<string>? warnings = null)
    {
        var blockers = new List<string>();
        if (inputElementCount == 0)
        {
            blockers.Add("caster_elements_required");
        }
        else if (supportedElementCount == 0)
        {
            blockers.Add("no_supported_caster_elements");
        }
        else if (solidCount == 0)
        {
            blockers.Add("no_shadow_caster_solids");
        }

        return new ForwardRevitCasterGeometrySummaryV0
        {
            Complete = blockers.Count == 0,
            InputElementCount = inputElementCount,
            SupportedElementCount = supportedElementCount,
            SolidCount = solidCount,
            GeometryInstanceCount = geometryInstanceCount,
            IgnoredGeometryCount = ignoredGeometryCount,
            Blockers = blockers,
            Warnings = warnings is null ? Array.Empty<string>() : new List<string>(warnings),
        };
    }
}
