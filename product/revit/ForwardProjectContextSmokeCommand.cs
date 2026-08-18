#if REVIT_API
using System;
using System.Collections.Generic;
using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;

namespace RevitShadow;

/// <summary>DEVELOPMENT / SMOKE TEST ONLY: invokes the read-only Phase 5B project-context path.</summary>
[Transaction(TransactionMode.ReadOnly)]
public sealed class ForwardProjectContextSmokeCommand : IExternalCommand
{
    // Test-only defaults for manual smoke testing. These are not production settings semantics.
    private const double SmokeTestMeasurementHeightM = 4.0;
    private const double SmokeTestExplicitLatitudeDeg = 35.6812;
    private const double SmokeTestFallbackAverageGroundLevelElevationM = 0.0;

    public Result Execute(ExternalCommandData commandData, ref string message, ElementSet elements)
    {
        var uiApplication = commandData?.Application;
        if (uiApplication is null)
        {
            return ShowBlocker("ui_application_unavailable", ref message);
        }

        var uiDocument = uiApplication.ActiveUIDocument;
        if (uiDocument is null)
        {
            return ShowBlocker("active_ui_document_unavailable", ref message);
        }

        var document = uiDocument.Document;
        if (document is null)
        {
            return ShowBlocker("active_document_unavailable", ref message);
        }

        var level = document.ActiveView?.GenLevel;
        if (level is null || level.Document is null || level.Id == ElementId.InvalidElementId)
        {
            return ShowBlocker("active_view_level_unavailable", ref message);
        }

        try
        {
            var diagnostic = ForwardRevitProjectContextDiagnosticV0.Extract(
                document,
                level,
                SmokeTestFallbackAverageGroundLevelElevationM,
                SmokeTestMeasurementHeightM,
                SmokeTestExplicitLatitudeDeg);

            TaskDialog.Show("Dynamo Shadow — Development Smoke Test", ForwardProjectContextDiagnosticFormatterV0.Format(diagnostic));
            if (diagnostic["complete"] is true)
            {
                return Result.Succeeded;
            }

            message = "Forward project-context smoke test reported extraction blockers.";
            return Result.Failed;
        }
        catch (Exception exception)
        {
            // Revit commands are an exception boundary: preserve unexpected defect details
            // for the journal/host while preventing an unhandled exception from escaping.
            message = $"Unexpected forward project-context smoke-test failure: {exception}";
            TaskDialog.Show("Dynamo Shadow — Development Smoke Test", message);
            return Result.Failed;
        }
    }

    private static Result ShowBlocker(string blocker, ref string message)
    {
        var diagnostic = new Dictionary<string, object?>
        {
            ["available"] = false,
            ["complete"] = false,
            ["average_ground_level_elevation_m"] = null,
            ["average_ground_level_source"] = null,
            ["measurement_height_m"] = SmokeTestMeasurementHeightM,
            ["measurement_plane_elevation_m"] = null,
            ["true_north_deg"] = null,
            ["latitude_deg"] = SmokeTestExplicitLatitudeDeg,
            ["blockers"] = new[] { blocker },
            ["warnings"] = Array.Empty<string>(),
            ["permit_ready_certified"] = false,
        };
        message = blocker;
        TaskDialog.Show("Dynamo Shadow — Development Smoke Test", ForwardProjectContextDiagnosticFormatterV0.Format(diagnostic));
        return Result.Failed;
    }
}
#endif
