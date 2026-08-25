#if REVIT_API
using System;
using System.Collections.Generic;

namespace RevitShadow;

/// <summary>Owns every completed native per-slice union and disposes them as one unit.</summary>
public sealed class ForwardRevitMultiTimeIntegrationResultV0 : IDisposable
{
    public ForwardRevitMultiTimeIntegrationResultV0(
        IReadOnlyList<ForwardRevitSingleSliceIntegrationResultV0> sliceResults,
        ForwardRevitMultiTimeSummaryV0 summary)
    { SliceResults = sliceResults; Summary = summary; }
    public IReadOnlyList<ForwardRevitSingleSliceIntegrationResultV0> SliceResults { get; }
    public ForwardRevitMultiTimeSummaryV0 Summary { get; }
    public void Dispose() { foreach (var result in SliceResults) result.Dispose(); }
}
#endif
