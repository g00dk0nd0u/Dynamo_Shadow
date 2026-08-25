#if REVIT_API
using System;
using System.Collections.Generic;
using Autodesk.Revit.DB;
using ShadowCore;

namespace RevitShadow;

/// <summary>Revit-native Forward orchestration through per-time-slice union only.</summary>
public static class ForwardRevitMultiTimeIntegratorV0
{
    public static ForwardRevitMultiTimeIntegrationResultV0 Run(Document document, Level? selectedLevel,
        IEnumerable<Element>? selectedCasterElements, double? fallbackAverageGroundLevelElevationM,
        double? measurementHeightM, double? explicitLatitudeDeg, double solarDeclinationDeg,
        double trueSolarStartMinutes, double trueSolarEndMinutes, double sunTimeStepMinutes,
        double validationToleranceM, double closureToleranceM)
    {
        if (document is null) throw new ArgumentNullException(nameof(document));
        var owned = new List<ForwardRevitFormalShadowUnionResultV0>();
        var context = ForwardRevitProjectContextExtractorV0.Extract(document, selectedLevel,
            fallbackAverageGroundLevelElevationM, measurementHeightM, explicitLatitudeDeg);
        if (!context.Complete)
            return Failed(owned, context.Blockers);
        var caster = ForwardRevitCasterGeometryExtractorV0.Extract(selectedCasterElements);
        if (!caster.Summary.Complete)
            return Failed(owned, caster.Summary.Blockers);

        double planeInternal, validationToleranceInternal;
        try {
            planeInternal = UnitUtils.ConvertToInternalUnits(context.MeasurementPlaneElevationM!.Value, UnitTypeId.Meters);
            validationToleranceInternal = UnitUtils.ConvertToInternalUnits(validationToleranceM, UnitTypeId.Meters);
        } catch (Exception) { return Failed(owned, new[] { "numeric_conversion_failed" }); }

        // TrueNorthDeg is already the resolved ProjectContext model rotation. Do not rotate again in Revit.
        var solar = ForwardSolarTimelineV0.Build(new ForwardSolarTimelineInputV0 {
            LatitudeDeg = context.LatitudeDeg!.Value, SolarDeclinationDeg = solarDeclinationDeg,
            TrueNorthDeg = context.TrueNorthDeg!.Value, TrueSolarStartMinutes = trueSolarStartMinutes,
            TrueSolarEndMinutes = trueSolarEndMinutes, SunTimeStepMinutes = sunTimeStepMinutes
        });
        var summary = ForwardRevitMultiTimeOrchestratorV0.Run(solar, sample =>
        {
            using var projection = ForwardRevitFormalShadowProjectorV0.Project(caster.Solids, planeInternal,
                sample.ShadowDirectionModel.X, sample.ShadowDirectionModel.Y,
                sample.ShadowLengthFactor, validationToleranceInternal);
            if (!projection.Summary.Complete) return Slice(false, projection.Summary.Blockers);
            var union = ForwardRevitFormalShadowUnionV0.Union(projection.Components, planeInternal, closureToleranceM);
            if (!union.Summary.Complete) { union.Dispose(); return Slice(false, union.Summary.Blockers); }
            owned.Add(union);
            return Slice(true, Array.Empty<string>());
        });
        return new ForwardRevitMultiTimeIntegrationResultV0(owned, summary);
    }

    private static ForwardRevitTimeSliceOutcomeV0 Slice(bool complete,
        IReadOnlyList<string> blockers) => new() { Complete = complete, Blockers = blockers };

    private static ForwardRevitMultiTimeIntegrationResultV0 Failed(
        IReadOnlyList<ForwardRevitFormalShadowUnionResultV0> owned, IEnumerable<string> blockers) =>
        new(owned, new ForwardRevitMultiTimeSummaryV0 { Blockers = new List<string>(blockers) });
}
#endif
