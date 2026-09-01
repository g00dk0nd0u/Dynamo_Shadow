#if REVIT_API
using System;
using System.Linq;
using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;
using ShadowCore;

namespace RevitShadow;

/// <summary>DEVELOPMENT / SMOKE TEST ONLY: invokes the connected compiled Full Forward pipeline.</summary>
[Transaction(TransactionMode.ReadOnly)]
public sealed class ForwardFullForwardSmokeCommand : IExternalCommand
{
    // Explicit smoke-test defaults only. They are not production, ordinance, or legal settings.
    private const double MeasurementHeightM = 4.0;
    private const double LatitudeDeg = 35.6812;
    private const double SolarDeclinationDeg = -23.45;
    private const double TrueSolarStartMinutes = 480.0;
    private const double TrueSolarEndMinutes = 960.0;
    private const double SunTimeStepMinutes = 30.0;
    private const double GridResolutionM = 1.0;
    private const double AnalysisMarginM = 10.0;
    private const int MaxGridPoints = 250_000;
    private const double ValidationToleranceM = 0.001;
    private const double ClosureToleranceM = 0.001;
    private const double ContourIntervalMinutes = 60.0;
    private const int MaxContourLevels = 10;
    private const int MaxContourSegments = 10_000;

    public Result Execute(ExternalCommandData commandData, ref string message, ElementSet elements)
    {
        try
        {
            var uiDocument = commandData?.Application?.ActiveUIDocument;
            var document = uiDocument?.Document;
            var level = document?.ActiveView?.GenLevel;
            if (document is null || level is null)
            {
                message = document is null ? "active_document_unavailable" : "active_view_level_unavailable";
                Show(Failed(message));
                return Result.Failed;
            }

            // Selection is used verbatim; the existing integrator enforces the formal Mass / Generic Model contract.
            var casters = uiDocument!.Selection.GetElementIds().Select(document.GetElement).ToArray();
            using var result = ForwardRevitFullForwardIntegratorV0.Run(
                document, level, casters, fallbackAverageGroundLevelElevationM: null,
                MeasurementHeightM, LatitudeDeg, SolarDeclinationDeg,
                TrueSolarStartMinutes, TrueSolarEndMinutes, SunTimeStepMinutes,
                ValidationToleranceM, ClosureToleranceM,
                new ForwardShadowDurationSettingsV0 {
                    GridResolutionM = GridResolutionM,
                    AnalysisMarginM = AnalysisMarginM,
                    MaxGridPoints = MaxGridPoints
                },
                new ForwardEqualTimeContourSettingsV0 {
                    EqualTimeContourIntervalMinutes = ContourIntervalMinutes,
                    MaxEqualTimeContourLevels = MaxContourLevels
                },
                MaxContourSegments);

            Show(result.Summary);
            if (result.Summary.Complete) return Result.Succeeded;
            message = "Full Forward smoke test reported structured blockers.";
            return Result.Failed;
        }
        catch (Exception exception)
        {
            message = $"Unexpected Full Forward smoke-test failure: {exception}";
            TaskDialog.Show("Dynamo Shadow — Full Forward Development Smoke Test", message);
            return Result.Failed;
        }
    }

    private static ForwardRevitFullForwardSummaryV0 Failed(string blocker) => new() {
        Available = false, Complete = false, FinalCompletedStage = "none",
        BlockerStage = "command_input", Blockers = new[] { blocker }
    };

    private static void Show(ForwardRevitFullForwardSummaryV0 summary) =>
        TaskDialog.Show("Dynamo Shadow — Full Forward Development Smoke Test",
            ForwardFullForwardSmokeSummaryFormatter.Format(summary));
}
#endif
