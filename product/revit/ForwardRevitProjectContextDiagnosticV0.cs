using System.Collections.Generic;
using System.Linq;

#if REVIT_API
using Autodesk.Revit.DB;
#endif

namespace RevitShadow;

/// <summary>JSON-safe diagnostic projection for real-machine invocation.</summary>
public static class ForwardRevitProjectContextDiagnosticV0
{
    public static IReadOnlyDictionary<string, object?> ToData(ForwardRevitProjectContextResultV0 result) =>
        new Dictionary<string, object?>
        {
            ["available"] = result.Available,
            ["complete"] = result.Complete,
            ["average_ground_level_elevation_m"] = result.AverageGroundLevelElevationM,
            ["average_ground_level_source"] = result.AverageGroundLevelSource,
            ["measurement_height_m"] = result.MeasurementHeightM,
            ["measurement_plane_elevation_m"] = result.MeasurementPlaneElevationM,
            ["true_north_deg"] = result.TrueNorthDeg,
            ["latitude_deg"] = result.LatitudeDeg,
            ["blockers"] = result.Blockers.ToArray(),
            ["warnings"] = result.Warnings.ToArray(),
            ["permit_ready_certified"] = result.PermitReadyCertified,
        };

#if REVIT_API
    public static IReadOnlyDictionary<string, object?> Extract(
        Document document,
        Level? selectedLevel,
        double? fallbackAverageGroundLevelElevationM,
        double? measurementHeightM,
        double? explicitLatitudeDeg) =>
        ToData(ForwardRevitProjectContextExtractorV0.Extract(
            document,
            selectedLevel,
            fallbackAverageGroundLevelElevationM,
            measurementHeightM,
            explicitLatitudeDeg));
#endif
}
