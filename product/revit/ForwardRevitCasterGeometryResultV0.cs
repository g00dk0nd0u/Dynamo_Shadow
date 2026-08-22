#if REVIT_API
using System.Collections.Generic;
using Autodesk.Revit.DB;

namespace RevitShadow;

/// <summary>
/// Revit-layer result. Native solids intentionally remain on this adapter-only contract.
/// </summary>
public sealed class ForwardRevitCasterGeometryResultV0
{
    public ForwardRevitCasterGeometryResultV0(
        IReadOnlyList<Solid> solids,
        ForwardRevitCasterGeometrySummaryV0 summary)
    {
        Solids = solids;
        Summary = summary;
    }

    public IReadOnlyList<Solid> Solids { get; }
    public ForwardRevitCasterGeometrySummaryV0 Summary { get; }
}
#endif
