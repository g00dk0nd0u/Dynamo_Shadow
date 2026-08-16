using System.Text.Json;
using ShadowCore;
using Xunit;

namespace ShadowCore.Tests;

public sealed class ForwardVerticalSliceV0Tests
{
    [Fact]
    public void MatchesSharedPythonReferenceFixtureEndToEnd()
    {
        using var fixture=JsonDocument.Parse(File.ReadAllText(Path.Combine(AppContext.BaseDirectory,"fixtures","parity","forward_vertical_slice_v0.json")));
        var root=fixture.RootElement;var input=Build(root.GetProperty("input"));var expected=root.GetProperty("expected");var actual=ForwardVerticalSliceV0.Run(input);
        Assert.True(actual.Complete);Assert.False(actual.PermitReadyCertified);
        Assert.Equal(expected.GetProperty("sample_count").GetInt32(),actual.Solar.Samples.Count);
        Assert.Equal(expected.GetProperty("sample_times_minutes").EnumerateArray().Select(x=>x.GetDouble()),actual.Solar.Samples.Select(x=>x.TrueSolarMinutes));
        var solar=expected.GetProperty("representative_solar");var sample=actual.Solar.Samples[solar.GetProperty("sample_index").GetInt32()];
        Assert.Equal(solar.GetProperty("solar_altitude_deg").GetDouble(),sample.SolarAltitudeDeg,5);Assert.Equal(solar.GetProperty("solar_azimuth_deg").GetDouble(),sample.SolarAzimuthDeg,5);
        Assert.Equal(solar.GetProperty("shadow_direction_model").GetProperty("x").GetDouble(),sample.ShadowDirectionModel.X,8);Assert.Equal(solar.GetProperty("shadow_direction_model").GetProperty("y").GetDouble(),sample.ShadowDirectionModel.Y,8);
        var polygon=expected.GetProperty("representative_polygon");var points=actual.ShadowSlices.Slices[polygon.GetProperty("slice_index").GetInt32()].Polygons[0].PointsM;var expectedPoints=polygon.GetProperty("points_m").EnumerateArray().ToList();Assert.Equal(expectedPoints.Count,points.Count);for(var i=0;i<points.Count;i++){Assert.Equal(expectedPoints[i].GetProperty("x").GetDouble(),points[i].X,5);Assert.Equal(expectedPoints[i].GetProperty("y").GetDouble(),points[i].Y,5);}
        var grid=expected.GetProperty("grid_spec");Assert.Equal(grid.GetProperty("x_count").GetInt32(),actual.Duration.GridSpec!.XCount);Assert.Equal(grid.GetProperty("y_count").GetInt32(),actual.Duration.GridSpec.YCount);Assert.Equal(grid.GetProperty("origin_x_m").GetDouble(),actual.Duration.GridSpec.OriginXM,5);Assert.Equal(expected.GetProperty("maximum_shadow_duration_minutes").GetDouble(),actual.Duration.MaximumShadowDurationMinutes,8);Assert.Equal(expected.GetProperty("shadowed_point_count").GetInt32(),actual.Duration.ShadowedPointCount);
        Assert.Equal(expected.GetProperty("generated_contour_levels_minutes").EnumerateArray().Select(x=>x.GetDouble()),actual.Contours.GeneratedLevelsMinutes);Assert.Equal(expected.GetProperty("contour_count").GetInt32(),actual.Contours.ContourCount);var contour=expected.GetProperty("representative_contour");Assert.Equal(contour.GetProperty("closed").GetBoolean(),actual.Contours.Contours[0].Closed);Assert.Equal(contour.GetProperty("point_count").GetInt32(),actual.Contours.Contours[0].PointCount);Assert.Equal(contour.GetProperty("points_m")[0].GetProperty("x").GetDouble(),actual.Contours.Contours[0].PointsM[0].X,5);
    }

    [Fact]
    public void BlocksUnsupportedAndUnsafeInputs()
    {
        var input=Valid();input.Caster.FootprintPointsM=new List<Point2M>{new(0,0),new(2,0),new(1,1),new(2,2),new(0,2)};Assert.Contains("non_convex_footprint",ForwardVerticalSliceV0.Run(input).Blockers);
        input=Valid();input.Caster.TopZM=3;Assert.Contains("caster_top_not_above_measurement_plane",ForwardVerticalSliceV0.Run(input).Blockers);
        input=Valid();input.TrueSolarEndMinutes=input.TrueSolarStartMinutes;Assert.Contains("invalid_time_range",ForwardVerticalSliceV0.Run(input).Blockers);
        input=Valid();input.MaxGridPoints=1;Assert.Contains("max_grid_points_exceeded",ForwardVerticalSliceV0.Run(input).Blockers);
    }

    [Fact]
    public void ContoursRetainWorldModelCoordinatesAndStartAtNumericMinimum()
    {
        using var fixture=JsonDocument.Parse(File.ReadAllText(Path.Combine(AppContext.BaseDirectory,"fixtures","parity","forward_vertical_slice_v0.json")));
        var root=fixture.RootElement;var actual=ForwardVerticalSliceV0.Run(Build(root.GetProperty("input")));var first=actual.Contours.Contours[0].PointsM[0];
        Assert.Equal(-12.87757,actual.Duration.GridSpec!.OriginXM,5);
        Assert.Equal(actual.Duration.GridSpec.OriginXM+actual.Duration.GridSpec.ResolutionM,first.X,5);
        Assert.Equal(-10.87757,first.X,5);
        Assert.Equal(15.0,first.Y,5);
    }

    private static ForwardVerticalSliceInputV0 Build(JsonElement x){var caster=x.GetProperty("caster");return new ForwardVerticalSliceInputV0{LatitudeDeg=x.GetProperty("latitude_deg").GetDouble(),SolarDeclinationDeg=x.GetProperty("solar_declination_deg").GetDouble(),TrueNorthDeg=x.GetProperty("true_north_deg").GetDouble(),TrueSolarStartMinutes=x.GetProperty("true_solar_start_minutes").GetDouble(),TrueSolarEndMinutes=x.GetProperty("true_solar_end_minutes").GetDouble(),SunTimeStepMinutes=x.GetProperty("sun_time_step_minutes").GetDouble(),MeasurementPlaneElevationM=x.GetProperty("measurement_plane_elevation_m").GetDouble(),GridResolutionM=x.GetProperty("grid_resolution_m").GetDouble(),AnalysisMarginM=x.GetProperty("analysis_margin_m").GetDouble(),MaxGridPoints=x.GetProperty("max_grid_points").GetInt32(),ContourLevelsMinutes=x.GetProperty("contour_levels_minutes").EnumerateArray().Select(v=>v.GetDouble()).ToList(),Caster=new ConvexPrismCasterV0{BaseZM=caster.GetProperty("base_z_m").GetDouble(),TopZM=caster.GetProperty("top_z_m").GetDouble(),FootprintPointsM=caster.GetProperty("footprint_points_m").EnumerateArray().Select(p=>new Point2M(p.GetProperty("x").GetDouble(),p.GetProperty("y").GetDouble())).ToList()}};}
    private static ForwardVerticalSliceInputV0 Valid()=>new(){LatitudeDeg=35.6812,SolarDeclinationDeg=-23.439,TrueSolarStartMinutes=600,TrueSolarEndMinutes=840,SunTimeStepMinutes=120,MeasurementPlaneElevationM=4,GridResolutionM=2,AnalysisMarginM=2,MaxGridPoints=10000,ContourLevelsMinutes=new List<double>{60},Caster=new ConvexPrismCasterV0{BaseZM=0,TopZM=12,FootprintPointsM=new List<Point2M>{new(-2,-1),new(2,-1),new(2,1),new(-2,1)}}};
}
