using System;

namespace RevitShadow;

public static class ForwardRevitProjectContextAdapterV0
{
    public static ForwardRevitProjectContextResultV0 Resolve(
        ForwardRevitProjectContextInputV0? input,
        Func<double, double>? internalLengthToMeters)
    {
        var result = new ForwardRevitProjectContextResultV0();
        if (input is null)
        {
            result.Blockers.Add("project_context_input_required");
            return result;
        }

        ResolveAverageGroundLevel(input, internalLengthToMeters, result);

        if (!input.MeasurementHeightM.HasValue)
        {
            result.Blockers.Add("measurement_height_missing");
        }
        else if (!IsFinite(input.MeasurementHeightM.Value))
        {
            result.Blockers.Add("measurement_height_non_finite");
        }
        else
        {
            result.MeasurementHeightM = input.MeasurementHeightM.Value;
        }

        if (!input.RawActiveProjectLocationAngleRad.HasValue)
        {
            result.Blockers.Add("true_north_raw_angle_missing");
        }
        else if (!IsFinite(input.RawActiveProjectLocationAngleRad.Value))
        {
            result.Blockers.Add("true_north_raw_angle_non_finite");
        }
        else
        {
            result.TrueNorthDeg = input.RawActiveProjectLocationAngleRad.Value * 180.0 / Math.PI;
        }

        if (!input.ExplicitLatitudeDeg.HasValue)
        {
            result.Blockers.Add("latitude_missing");
        }
        else if (!IsFinite(input.ExplicitLatitudeDeg.Value))
        {
            result.Blockers.Add("latitude_non_finite");
        }
        else
        {
            result.LatitudeDeg = input.ExplicitLatitudeDeg.Value;
        }

        if (result.AverageGroundLevelElevationM.HasValue && result.MeasurementHeightM.HasValue)
        {
            var elevation = result.AverageGroundLevelElevationM.Value + result.MeasurementHeightM.Value;
            if (IsFinite(elevation))
            {
                result.MeasurementPlaneElevationM = elevation;
            }
            else
            {
                result.Blockers.Add("measurement_plane_elevation_non_finite");
            }
        }

        result.Available = result.Complete = result.Blockers.Count == 0;
        return result;
    }

    private static void ResolveAverageGroundLevel(
        ForwardRevitProjectContextInputV0 input,
        Func<double, double>? internalLengthToMeters,
        ForwardRevitProjectContextResultV0 result)
    {
        if (input.LevelSelected)
        {
            if (!input.SelectedLevelElevationInternal.HasValue)
            {
                result.Blockers.Add("selected_level_elevation_unreadable");
                return;
            }

            var internalElevation = input.SelectedLevelElevationInternal.Value;
            if (!IsFinite(internalElevation))
            {
                result.Blockers.Add("selected_level_internal_elevation_non_finite");
                return;
            }

            if (internalLengthToMeters is null)
            {
                result.Blockers.Add("internal_length_converter_unavailable");
                return;
            }

            try
            {
                var elevationM = internalLengthToMeters(internalElevation);
                if (!IsFinite(elevationM))
                {
                    result.Blockers.Add("selected_level_unit_conversion_failed");
                    return;
                }

                result.AverageGroundLevelElevationM = elevationM;
                result.AverageGroundLevelSource = "selected_revit_level";
            }
            catch (Exception)
            {
                result.Blockers.Add("selected_level_unit_conversion_failed");
            }

            return;
        }

        if (!input.FallbackAverageGroundLevelElevationM.HasValue)
        {
            result.Blockers.Add("average_ground_level_unavailable");
        }
        else if (!IsFinite(input.FallbackAverageGroundLevelElevationM.Value))
        {
            result.Blockers.Add("fallback_average_ground_level_non_finite");
        }
        else
        {
            result.AverageGroundLevelElevationM = input.FallbackAverageGroundLevelElevationM.Value;
            result.AverageGroundLevelSource = "settings_fallback";
        }
    }

    private static bool IsFinite(double value) => !double.IsNaN(value) && !double.IsInfinity(value);
}
