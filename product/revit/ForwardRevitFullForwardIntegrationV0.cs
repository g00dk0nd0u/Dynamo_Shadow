#if REVIT_API
using System;
using System.Collections.Generic;
using Autodesk.Revit.DB;
using ShadowCore;

namespace RevitShadow;

/// <summary>Owns the native multi-time result and exposes independent host-neutral stage results.</summary>
public sealed class ForwardRevitFullForwardIntegrationResultV0 : IDisposable
{
    internal ForwardRevitFullForwardIntegrationResultV0(
        ForwardRevitMultiTimeIntegrationResultV0 multiTimeResult,
        ForwardUnifiedShadowSliceSnapshotV0? snapshot,
        ForwardShadowDurationResultV0? duration,
        ForwardShadowDurationFieldV0? durationField,
        ForwardEqualTimeContourResultV0? contours,
        ForwardRevitFullForwardSummaryV0 summary)
    {
        MultiTimeResult = multiTimeResult; Snapshot = snapshot; Duration = duration; DurationField = durationField;
        Contours = contours; Summary = summary;
    }

    public ForwardRevitMultiTimeIntegrationResultV0 MultiTimeResult { get; }
    public ForwardUnifiedShadowSliceSnapshotV0? Snapshot { get; }
    public ForwardShadowDurationResultV0? Duration { get; }
    public ForwardShadowDurationFieldV0? DurationField { get; }
    public ForwardEqualTimeContourResultV0? Contours { get; }
    public ForwardRevitFullForwardSummaryV0 Summary { get; }
    public void Dispose() => MultiTimeResult.Dispose();
}

/// <summary>Connects the existing native Forward, snapshot, duration, and contour boundaries.</summary>
public static class ForwardRevitFullForwardIntegratorV0
{
    public static ForwardRevitFullForwardIntegrationResultV0 Run(Document document, Level? selectedLevel,
        IEnumerable<Element>? selectedCasterElements, double? fallbackAverageGroundLevelElevationM,
        double? measurementHeightM, double? explicitLatitudeDeg, double solarDeclinationDeg,
        double trueSolarStartMinutes, double trueSolarEndMinutes, double sunTimeStepMinutes,
        double validationToleranceM, double closureToleranceM,
        ForwardShadowDurationSettingsV0? durationSettings,
        ForwardEqualTimeContourSettingsV0? contourSettings = null,
        int? maximumContourSegmentCount = null)
    {
        var multiTime = ForwardRevitMultiTimeIntegratorV0.Run(document, selectedLevel,
            selectedCasterElements, fallbackAverageGroundLevelElevationM, measurementHeightM,
            explicitLatitudeDeg, solarDeclinationDeg, trueSolarStartMinutes, trueSolarEndMinutes,
            sunTimeStepMinutes, validationToleranceM, closureToleranceM);
        ForwardUnifiedShadowSliceSnapshotV0? snapshot = null;
        ForwardShadowDurationResultV0? duration = null;
        ForwardShadowDurationFieldV0? durationField = null;
        ForwardEqualTimeContourResultV0? contours = null;
        try
        {
            var summary = ForwardRevitFullForwardOrchestratorV0.Run(
                () => multiTime.Summary,
                () => snapshot = ForwardRevitUnifiedShadowSliceSnapshotAdapterV0.Create(multiTime),
                () => {
                    var built = ForwardPostUnionPipelineV0.Build(new ForwardPostUnionPipelineInputV0 {
                        Snapshot = snapshot,
                        DurationSettings = durationSettings,
                        ContourSettings = contourSettings,
                        MaximumContourSegmentCount = maximumContourSegmentCount
                    });
                    duration = built.Result.Duration;
                    durationField = built.DurationField;
                    contours = built.Result.EqualTimeContours;
                    return built;
                });
            return new ForwardRevitFullForwardIntegrationResultV0(
                multiTime, snapshot, duration, durationField, contours, summary);
        }
        catch
        {
            multiTime.Dispose();
            throw;
        }
    }
}
#endif
