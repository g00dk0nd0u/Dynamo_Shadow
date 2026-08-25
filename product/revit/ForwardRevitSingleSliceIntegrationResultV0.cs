#if REVIT_API
using System;

namespace RevitShadow;

/// <summary>
/// Revit-only Phase 5F-A result. It owns and disposes UnionResult; inputs and
/// Phase 5D solids are borrowed, while the intermediate projection is disposed by the orchestrator.
/// </summary>
public sealed class ForwardRevitSingleSliceIntegrationResultV0 : IDisposable
{
    public ForwardRevitSingleSliceIntegrationResultV0(
        ForwardRevitFormalShadowUnionResultV0? unionResult,
        ForwardRevitSingleSliceIntegrationSummaryV0 summary)
    {
        UnionResult = unionResult;
        Summary = summary;
    }

    public ForwardRevitFormalShadowUnionResultV0? UnionResult { get; }
    public ForwardRevitSingleSliceIntegrationSummaryV0 Summary { get; }
    public void Dispose() => UnionResult?.Dispose();
}
#endif
