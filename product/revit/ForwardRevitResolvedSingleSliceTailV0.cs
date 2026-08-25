#if REVIT_API
using System;
using System.Collections.Generic;
using Autodesk.Revit.DB;

namespace RevitShadow;

/// <summary>Shared Phase 5F native projection/union tail for already-resolved context and casters.</summary>
internal static class ForwardRevitResolvedSingleSliceTailV0
{
    internal static ForwardRevitSingleSliceIntegrationResultV0 Run(
        ForwardRevitProjectContextResultV0 context, ForwardRevitCasterGeometryResultV0 caster,
        double shadowDirectionModelX, double shadowDirectionModelY, double shadowLengthFactor,
        double validationToleranceM, double closureToleranceM,
        out IReadOnlyList<string> projectionWarnings, out IReadOnlyList<string> unionWarnings)
    {
        projectionWarnings = Array.Empty<string>(); unionWarnings = Array.Empty<string>();
        var numeric = ForwardRevitSingleSliceNumericBoundaryV0.Resolve(
            context.MeasurementPlaneElevationM!.Value, validationToleranceM,
            value => UnitUtils.ConvertToInternalUnits(value, UnitTypeId.Meters));
        if (!numeric.Complete) return Result(context, caster.Summary, boundaryBlocker: numeric.Blocker);

        using var projection = ForwardRevitFormalShadowProjectorV0.Project(caster.Solids,
            numeric.PlaneInternal, shadowDirectionModelX, shadowDirectionModelY, shadowLengthFactor,
            numeric.ValidationToleranceInternal);
        projectionWarnings = projection.Summary.Warnings;
        if (!projection.Summary.Complete) return Result(context, caster.Summary, projection.Summary);
        var union = ForwardRevitFormalShadowUnionV0.Union(
            projection.Components, numeric.PlaneInternal, closureToleranceM);
        unionWarnings = union.Summary.Warnings;
        var summary = ForwardRevitSingleSliceIntegrationSummaryV0.Create(
            context, caster.Summary, projection.Summary, union.Summary);
        return new ForwardRevitSingleSliceIntegrationResultV0(union, summary);
    }

    private static ForwardRevitSingleSliceIntegrationResultV0 Result(
        ForwardRevitProjectContextResultV0 context, ForwardRevitCasterGeometrySummaryV0 caster,
        ForwardRevitFormalShadowSummaryV0? projection = null, string? boundaryBlocker = null) =>
        new(null, ForwardRevitSingleSliceIntegrationSummaryV0.Create(
            context, caster, projection, boundaryBlocker: boundaryBlocker));
}
#endif
