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
        var owned = new List<ForwardRevitSingleSliceIntegrationResultV0>();
        var context = ForwardRevitProjectContextExtractorV0.Extract(document, selectedLevel,
            fallbackAverageGroundLevelElevationM, measurementHeightM, explicitLatitudeDeg);
        if (!context.Complete)
            return Failed(owned, context.Blockers, Warnings("project_context", context.Warnings));
        var caster = ForwardRevitCasterGeometryExtractorV0.Extract(selectedCasterElements);
        if (!caster.Summary.Complete)
        {
            var failedWarnings = Warnings("project_context", context.Warnings);
            failedWarnings.AddRange(Warnings("caster_extraction", caster.Summary.Warnings));
            return Failed(owned, caster.Summary.Blockers, failedWarnings);
        }

        // TrueNorthDeg is already the resolved ProjectContext model rotation. Do not rotate again in Revit.
        var solar = ForwardSolarTimelineV0.Build(new ForwardSolarTimelineInputV0 {
            LatitudeDeg = context.LatitudeDeg!.Value, SolarDeclinationDeg = solarDeclinationDeg,
            TrueNorthDeg = context.TrueNorthDeg!.Value, TrueSolarStartMinutes = trueSolarStartMinutes,
            TrueSolarEndMinutes = trueSolarEndMinutes, SunTimeStepMinutes = sunTimeStepMinutes
        });
        var initialWarnings = Warnings("project_context", context.Warnings);
        initialWarnings.AddRange(Warnings("caster_extraction", caster.Summary.Warnings));
        var summary = ForwardRevitMultiTimeOrchestratorV0.Run(solar, sample =>
        {
            var result = ForwardRevitResolvedSingleSliceTailV0.Run(context, caster,
                sample.ShadowDirectionModel.X, sample.ShadowDirectionModel.Y,
                sample.ShadowLengthFactor, validationToleranceM, closureToleranceM,
                out var projectionWarnings, out var unionWarnings);
            var warnings = Warnings("projection", projectionWarnings, sample.SampleIndex);
            warnings.AddRange(Warnings("union", unionWarnings, sample.SampleIndex));
            if (!result.Summary.Complete) {
                var outcome = Slice(false, result.Summary.Blockers, result.Summary.BlockerStage, warnings);
                result.Dispose(); return outcome;
            }
            owned.Add(result);
            return Slice(true, Array.Empty<string>(), null, warnings);
        }, initialWarnings);
        return new ForwardRevitMultiTimeIntegrationResultV0(owned, summary);
    }

    private static ForwardRevitTimeSliceOutcomeV0 Slice(bool complete, IReadOnlyList<string> blockers,
        string? blockerStage, IReadOnlyList<ForwardRevitStageWarningV0> warnings) => new() {
            Complete = complete, Blockers = blockers, BlockerStage = blockerStage, Warnings = warnings };

    private static List<ForwardRevitStageWarningV0> Warnings(string stage,
        IEnumerable<string> values, int? sampleIndex = null)
    {
        var result = new List<ForwardRevitStageWarningV0>();
        foreach (var value in values) result.Add(new ForwardRevitStageWarningV0 {
            Stage = stage, SampleIndex = sampleIndex, Code = value });
        return result;
    }

    private static ForwardRevitMultiTimeIntegrationResultV0 Failed(
        IReadOnlyList<ForwardRevitSingleSliceIntegrationResultV0> owned, IEnumerable<string> blockers,
        IReadOnlyList<ForwardRevitStageWarningV0> warnings) => new(owned,
            new ForwardRevitMultiTimeSummaryV0 { Blockers = new List<string>(blockers), Warnings = warnings });
}
#endif
