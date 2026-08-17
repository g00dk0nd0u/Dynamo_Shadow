#if REVIT_API
using Autodesk.Revit.DB;

namespace RevitShadow;

/// <summary>
/// Read-only bridge from a live Revit document to the host-neutral Phase 5A adapter.
/// </summary>
public static class ForwardRevitProjectContextExtractorV0
{
    public static ForwardRevitProjectContextResultV0 Extract(
        Document document,
        Level? selectedLevel,
        double? fallbackAverageGroundLevelElevationM,
        double? measurementHeightM,
        double? explicitLatitudeDeg)
    {
        var input = new ForwardRevitProjectContextInputV0
        {
            LevelSelected = selectedLevel is not null,
            FallbackAverageGroundLevelElevationM = fallbackAverageGroundLevelElevationM,
            MeasurementHeightM = measurementHeightM,
            ExplicitLatitudeDeg = explicitLatitudeDeg,
        };

        if (selectedLevel is not null)
        {
            try
            {
                input.SelectedLevelElevationInternal = selectedLevel.Elevation;
            }
            catch
            {
                // The adapter turns an unreadable selected Level into a blocker and
                // deliberately does not use the settings fallback.
                input.SelectedLevelElevationInternal = null;
            }
        }

        try
        {
            input.RawActiveProjectLocationAngleRad = document.ActiveProjectLocation
                .GetProjectPosition(XYZ.Zero)
                .Angle;
        }
        catch
        {
            // Missing runtime project context is represented by the adapter's
            // established true_north_raw_angle_missing blocker.
            input.RawActiveProjectLocationAngleRad = null;
        }

        return ForwardRevitProjectContextAdapterV0.Resolve(
            input,
            value => UnitUtils.ConvertFromInternalUnits(value, UnitTypeId.Meters));
    }
}
#endif
