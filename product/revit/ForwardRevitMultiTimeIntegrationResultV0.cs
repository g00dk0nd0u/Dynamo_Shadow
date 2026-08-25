#if REVIT_API
using System;
using System.Collections.Generic;

namespace RevitShadow;

/// <summary>Owns every completed native per-slice union and disposes them as one unit.</summary>
public sealed class ForwardRevitMultiTimeIntegrationResultV0 : IDisposable
{
    public ForwardRevitMultiTimeIntegrationResultV0(
        IReadOnlyList<ForwardRevitFormalShadowUnionResultV0> unionResults,
        ForwardRevitMultiTimeSummaryV0 summary)
    { UnionResults = unionResults; Summary = summary; }
    public IReadOnlyList<ForwardRevitFormalShadowUnionResultV0> UnionResults { get; }
    public ForwardRevitMultiTimeSummaryV0 Summary { get; }
    public void Dispose() { foreach (var result in UnionResults) result.Dispose(); }
}
#endif
