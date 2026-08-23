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

        double planeInternal;
        double validationToleranceInternal;
        try
        {
            // The Phase 5A result is the sole source of the measurement-plane elevation.
            planeInternal = UnitUtils.ConvertToInternalUnits(
                context.MeasurementPlaneElevationM!.Value, UnitTypeId.Meters);
        }
        catch (Exception)
        {
            return Result(context, caster.Summary,
                boundaryBlocker: "measurement_plane_unit_conversion_failed");
        }

        if (!double.IsFinite(validationToleranceM) || validationToleranceM < 0.0)
            return Result(context, caster.Summary, boundaryBlocker: "numeric_conversion_failed");
        try
        {
            validationToleranceInternal = UnitUtils.ConvertToInternalUnits(
                validationToleranceM, UnitTypeId.Meters);
        }
        catch (Exception)
        {
            return Result(context, caster.Summary, boundaryBlocker: "numeric_conversion_failed");
        }

        using var projection = ForwardRevitFormalShadowProjectorV0.Project(caster.Solids,
            planeInternal, shadowDirectionModelX, shadowDirectionModelY, shadowLengthFactor,
            validationToleranceInternal);
        if (!projection.Summary.Complete)
            return Result(context, caster.Summary, projection.Summary);

        var union = ForwardRevitFormalShadowUnionV0.Union(
            projection.Components, planeInternal, closureToleranceM);
        var summary = ForwardRevitSingleSliceIntegrationSummaryV0.Create(
            context, caster.Summary, projection.Summary, union.Summary);
        return new ForwardRevitSingleSliceIntegrationResultV0(union, summary);
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
