#if REVIT_API
using System;
using System.Collections.Generic;
using Autodesk.Revit.DB;

namespace RevitShadow;

public sealed class ForwardRevitFormalShadowComponentV0
{
    public ForwardRevitFormalShadowComponentV0(int sourceSolidIndex, int splitSolidIndex,
        int clippedComponentIndex, IReadOnlyList<CurveLoop> loops)
    {
        SourceSolidIndex = sourceSolidIndex;
        SplitSolidIndex = splitSolidIndex;
        ClippedComponentIndex = clippedComponentIndex;
        Loops = loops;
    }
    public int SourceSolidIndex { get; }
    public int SplitSolidIndex { get; }
    public int ClippedComponentIndex { get; }
    // GetEdgesAsCurveLoops preserves outer, inner, and disconnected native loops.
    public IReadOnlyList<CurveLoop> Loops { get; }
}

/// <summary>Revit-only result. Native loops never cross into ShadowCore diagnostics.</summary>
public sealed class ForwardRevitFormalShadowResultV0 : IDisposable
{
    public ForwardRevitFormalShadowResultV0(
        IReadOnlyList<ForwardRevitFormalShadowComponentV0> components,
        ForwardRevitFormalShadowSummaryV0 summary)
    {
        Components = components;
        Summary = summary;
    }
    public IReadOnlyList<ForwardRevitFormalShadowComponentV0> Components { get; }
    public ForwardRevitFormalShadowSummaryV0 Summary { get; }

    public void Dispose()
    {
        foreach (var component in Components)
            foreach (var loop in component.Loops)
                loop.Dispose();
    }
}
#endif
