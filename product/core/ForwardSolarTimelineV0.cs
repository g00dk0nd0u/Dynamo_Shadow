using System;
using System.Collections.Generic;

namespace ShadowCore;

/// <summary>Portable, host-independent input for the frozen true-solar-time calculation.</summary>
public sealed class ForwardSolarTimelineInputV0
{
    public double LatitudeDeg { get; set; }
    public double SolarDeclinationDeg { get; set; }
    public double TrueNorthDeg { get; set; }
    public double TrueSolarStartMinutes { get; set; }
    public double TrueSolarEndMinutes { get; set; }
    public double SunTimeStepMinutes { get; set; }
}

/// <summary>Builds the inclusive ordered timeline used by the portable Forward pipeline.</summary>
public static class ForwardSolarTimelineV0
{
    public static SolarResultV0 Build(ForwardSolarTimelineInputV0? input)
    {
        var result = new SolarResultV0();
        if (input is null) { result.Blockers.Add("solar_input_required"); return result; }
        if (!ForwardGeometryV0.Finite(input.LatitudeDeg) || input.LatitudeDeg < -90 || input.LatitudeDeg > 90)
            result.Blockers.Add("invalid_latitude");
        if (!ForwardGeometryV0.Finite(input.SolarDeclinationDeg)) result.Blockers.Add("invalid_solar_declination");
        if (!ForwardGeometryV0.Finite(input.TrueNorthDeg)) result.Blockers.Add("invalid_true_north");
        if (!ForwardGeometryV0.Finite(input.TrueSolarStartMinutes) ||
            !ForwardGeometryV0.Finite(input.TrueSolarEndMinutes) ||
            input.TrueSolarEndMinutes <= input.TrueSolarStartMinutes) result.Blockers.Add("invalid_time_range");
        if (!ForwardGeometryV0.Finite(input.SunTimeStepMinutes) || input.SunTimeStepMinutes <= 0)
            result.Blockers.Add("invalid_sun_time_step");
        if (result.Blockers.Count > 0) return result;

        var times = new List<double> { input.TrueSolarStartMinutes };
        for (var time = input.TrueSolarStartMinutes + input.SunTimeStepMinutes;
             time < input.TrueSolarEndMinutes - 1e-9; time += input.SunTimeStepMinutes) times.Add(time);
        if (Math.Abs(times[times.Count - 1] - input.TrueSolarEndMinutes) > 1e-9)
            times.Add(input.TrueSolarEndMinutes);

        for (var index = 0; index < times.Count; index++)
        {
            var minute = times[index];
            var hourAngle = Radians(15 * (minute / 60 - 12));
            var latitude = Radians(input.LatitudeDeg);
            var declination = Radians(input.SolarDeclinationDeg);
            var sineAltitude = Math.Sin(latitude) * Math.Sin(declination) +
                Math.Cos(latitude) * Math.Cos(declination) * Math.Cos(hourAngle);
            sineAltitude = Math.Max(-1, Math.Min(1, sineAltitude));
            var altitude = Math.Asin(sineAltitude);
            var altitudeDeg = Degrees(altitude);
            if (altitudeDeg <= 0) { result.Blockers.Add("solar_sample_at_or_below_horizon"); return result; }
            var azimuth = (Degrees(Math.Atan2(Math.Sin(hourAngle),
                Math.Cos(hourAngle) * Math.Sin(latitude) - Math.Tan(declination) * Math.Cos(latitude)) + Math.PI) + 360) % 360;
            var shadowTrueNorth = (azimuth + 180) % 360;
            var shadowModel = (shadowTrueNorth + input.TrueNorthDeg) % 360;
            if (shadowModel < 0) shadowModel += 360;
            result.Samples.Add(new SolarSampleV0 {
                SampleIndex = index, TrueSolarMinutes = minute, SolarAltitudeDeg = altitudeDeg,
                SolarAzimuthDeg = azimuth, ShadowAzimuthTrueNorthDeg = shadowTrueNorth,
                ShadowAzimuthModelDeg = shadowModel, ShadowLengthFactor = 1 / Math.Tan(altitude),
                ShadowDirectionModel = new Point2M(Math.Sin(Radians(shadowModel)), Math.Cos(Radians(shadowModel)))
            });
        }
        result.Available = result.Complete = true;
        return result;
    }

    private static double Radians(double degrees) => degrees * Math.PI / 180;
    private static double Degrees(double radians) => radians * 180 / Math.PI;
}
