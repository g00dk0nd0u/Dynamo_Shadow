#if REVIT_API
using System;
using System.Collections.Generic;
using Autodesk.Revit.DB;

namespace RevitShadow;

/// <summary>Compiled Revit-native orchestration boundary for one resolved Forward time slice.</summary>
public static class ForwardRevitSingleSliceIntegratorV0
{
    public static ForwardRevitSingleSliceIntegrationResultV0 Run(
        Document document,
        Level? selectedLevel,
        IEnumerable<Element>? selectedCasterElements,
        double? fallbackAverageGroundLevelElevationM,
        double? measurementHeightM,
        double? explicitLatitudeDeg,
        double shadowDirectionModelX,
        double shadowDirectionModelY,
        double shadowLengthFactor,
        double validationToleranceM,
        double closureToleranceM)
    {
        if (document is null) throw new ArgumentNullException(nameof(document));

        var context = ForwardRevitProjectContextExtractorV0.Extract(document, selectedLevel,
            fallbackAverageGroundLevelElevationM, measurementHeightM, explicitLatitudeDeg);
        if (!context.Complete)
            return Result(context);

        var caster = ForwardRevitCasterGeometryExtractorV0.Extract(selectedCasterElements);
        if (!caster.Summary.Complete)
            return Result(context, caster.Summary);

        return ForwardRevitResolvedSingleSliceTailV0.Run(context, caster,
            shadowDirectionModelX, shadowDirectionModelY, shadowLengthFactor,
            validationToleranceM, closureToleranceM, out _, out _);
    }

    private static ForwardRevitSingleSliceIntegrationResultV0 Result(
        ForwardRevitProjectContextResultV0 context,
        ForwardRevitCasterGeometrySummaryV0? caster = null,
        ForwardRevitFormalShadowSummaryV0? projection = null,
        string? boundaryBlocker = null) => new(null,
            ForwardRevitSingleSliceIntegrationSummaryV0.Create(
                context, caster, projection, boundaryBlocker: boundaryBlocker));
}
#endif
