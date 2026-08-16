using System.Text.Json;
using ShadowCore;
using Xunit;

namespace ShadowCore.Tests;

public sealed class ForwardProjectionParityV0Tests
{
    [Fact]
    public void PublicCompiledProjectionMatchesPythonForTranslatedIrregularPolygonAndBothWindings()
    {
        using var fixture = JsonDocument.Parse(File.ReadAllText(Path.Combine(
            AppContext.BaseDirectory, "fixtures", "parity", "forward_projection_v0.json")));
        var root = fixture.RootElement;
        var results = new List<ForwardVerticalSliceResultV0>();

        foreach (var projectionCase in root.GetProperty("cases").EnumerateArray())
        {
            var actual = ForwardVerticalSliceV0.Run(BuildInput(root, projectionCase));
            Assert.True(actual.Complete);
            Assert.Equal(root.GetProperty("true_solar_minutes").GetArrayLength(), actual.ShadowSlices.Slices.Count);

            var expectedSlices = projectionCase.GetProperty("shadow_slices").EnumerateArray().ToArray();
            for (var index = 0; index < expectedSlices.Length; index++)
            {
                Assert.Equal(expectedSlices[index].GetProperty("true_solar_minutes").GetDouble(),
                    actual.ShadowSlices.Slices[index].TrueSolarMinutes, 8);
                AssertPolygonEquivalent(expectedSlices[index].GetProperty("points_m"),
                    actual.ShadowSlices.Slices[index].Polygons[0].PointsM);
            }
            results.Add(actual);
        }

        for (var index = 0; index < results[0].ShadowSlices.Slices.Count; index++)
        {
            AssertEquivalent(results[0].ShadowSlices.Slices[index].Polygons[0].PointsM,
                results[1].ShadowSlices.Slices[index].Polygons[0].PointsM);
        }

        var slices = results[0].ShadowSlices.Slices;
        Assert.True(slices.SelectMany(x => x.Polygons[0].PointsM).Min(point => point.X) > 100.0);
        Assert.True(slices.SelectMany(x => x.Polygons[0].PointsM).Max(point => point.Y) < -50.0);
        Assert.True(slices[0].Polygons[0].PointsM.Min(point => point.X) < 121.7);
        Assert.True(slices[1].Polygons[0].PointsM.Max(point => point.X) > 131.3);
        Assert.True(slices[2].Polygons[0].PointsM.Max(point => point.X) >
                    slices[1].Polygons[0].PointsM.Max(point => point.X));
    }

    private static ForwardVerticalSliceInputV0 BuildInput(JsonElement root, JsonElement projectionCase)
    {
        var solar = root.GetProperty("solar");
        var times = root.GetProperty("true_solar_minutes").EnumerateArray().Select(x => x.GetDouble()).ToArray();
        return new ForwardVerticalSliceInputV0
        {
            LatitudeDeg = solar.GetProperty("latitude_deg").GetDouble(),
            SolarDeclinationDeg = solar.GetProperty("solar_declination_deg").GetDouble(),
            TrueNorthDeg = solar.GetProperty("true_north_deg").GetDouble(),
            TrueSolarStartMinutes = times[0],
            TrueSolarEndMinutes = times[^1],
            SunTimeStepMinutes = times[1] - times[0],
            MeasurementPlaneElevationM = root.GetProperty("measurement_plane_elevation_m").GetDouble(),
            GridResolutionM = 5.0,
            AnalysisMarginM = 0.0,
            MaxGridPoints = 10_000,
            ContourLevelsMinutes = new List<double> { 60.0 },
            Caster = new ConvexPrismCasterV0
            {
                BaseZM = 0.0,
                TopZM = root.GetProperty("top_z_m").GetDouble(),
                FootprintPointsM = projectionCase.GetProperty("footprint_points_m").EnumerateArray()
                    .Select(point => new Point2M(point.GetProperty("x").GetDouble(), point.GetProperty("y").GetDouble()))
                    .ToList()
            }
        };
    }

    private const double CoordinateTolerance = 1e-6;

    private static void AssertPolygonEquivalent(JsonElement expected, IEnumerable<Point2M> actual)
    {
        var expectedPoints = expected.EnumerateArray()
            .Select(point => new Point2M(point.GetProperty("x").GetDouble(), point.GetProperty("y").GetDouble()));
        AssertEquivalent(expectedPoints, actual);
    }

    private static void AssertEquivalent(IEnumerable<Point2M> first, IEnumerable<Point2M> second)
    {
        var expected = first.ToArray();
        var actual = second.ToArray();
        Assert.Equal(expected.Length, actual.Length);
        for (var start = 0; start < actual.Length; start++)
        {
            if (IsCyclicMatch(expected, actual, start, 1) || IsCyclicMatch(expected, actual, start, -1))
                return;
        }

        Assert.Fail($"Polygons are not cyclically equivalent within coordinate tolerance {CoordinateTolerance:R}.");
    }

    private static bool IsCyclicMatch(Point2M[] expected, Point2M[] actual, int start, int direction)
    {
        for (var index = 0; index < expected.Length; index++)
        {
            var actualIndex = (start+direction*index+actual.Length)%actual.Length;
            if (Math.Abs(expected[index].X-actual[actualIndex].X) > CoordinateTolerance ||
                Math.Abs(expected[index].Y-actual[actualIndex].Y) > CoordinateTolerance)
                return false;
        }
        return true;
    }
}
