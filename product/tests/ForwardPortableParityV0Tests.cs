using System.Text.Json;
using ShadowCore;
using Xunit;

namespace ShadowCore.Tests;

public sealed class ForwardPortableParityV0Tests
{
    private const double CoordinateTolerance = 1e-6;
    private const double DurationTolerance = 1e-9;
    private const double LengthTolerance = 1e-6;

    [Fact]
    public void DensePortablePipelineMatchesEveryPythonDurationPointAndContourTopology()
    {
        using var fixture = LoadFixture();
        var root = fixture.RootElement;
        var expected = root.GetProperty("expected");
        var actual = ForwardVerticalSliceV0.Run(BuildInput(root.GetProperty("input")));

        Assert.True(actual.Available);
        Assert.True(actual.Complete);
        Assert.False(actual.PermitReadyCertified);
        Assert.False(actual.Solar.PermitReadyCertified);
        Assert.False(actual.ShadowSlices.PermitReadyCertified);
        Assert.False(actual.Duration.PermitReadyCertified);
        Assert.False(actual.Contours.PermitReadyCertified);

        var sampleTimes = expected.GetProperty("sample_times_minutes").EnumerateArray()
            .Select(value => value.GetDouble()).ToArray();
        Assert.Equal(new[] { 600.0, 670.0, 740.0, 800.0 }, sampleTimes);
        Assert.Equal(sampleTimes, actual.Solar.Samples.Select(sample => sample.TrueSolarMinutes));
        Assert.Equal(new[] { 70.0, 70.0, 60.0 }, actual.Solar.Samples.Zip(
            actual.Solar.Samples.Skip(1), (left, right) => right.TrueSolarMinutes-left.TrueSolarMinutes));
        Assert.Null(actual.Duration.TemporalStepMinutes);

        AssertRepresentativeSlices(expected.GetProperty("representative_shadow_slices"), actual);
        AssertDuration(expected.GetProperty("duration"), actual.Duration);
        AssertContours(expected.GetProperty("contours"), actual.Contours);
        AssertChangingStateIntegration(expected.GetProperty("duration"), actual.Duration);
    }

    [Fact]
    public void RepeatedExecutionPreservesAllOrderedPortableOutputsExactly()
    {
        using var fixture = LoadFixture();
        var input = fixture.RootElement.GetProperty("input");
        var first = ForwardVerticalSliceV0.Run(BuildInput(input));
        var second = ForwardVerticalSliceV0.Run(BuildInput(input));
        var third = ForwardVerticalSliceV0.Run(BuildInput(input));

        Assert.Equal(Snapshot(first), Snapshot(second));
        Assert.Equal(Snapshot(first), Snapshot(third));
    }

    [Fact]
    public void ContourMatcherRejectsVertexPermutationThatBreaksAdjacency()
    {
        using var fixture = LoadFixture();
        var item = fixture.RootElement.GetProperty("expected").GetProperty("contours")
            .GetProperty("items")[0];
        var expected = ReadPoints(item.GetProperty("points_m"));
        var permuted = expected.ToArray();
        (permuted[2], permuted[7]) = (permuted[7], permuted[2]);

        Assert.False(TopologicallyEquivalent(expected, permuted, true));
    }

    [Theory]
    [InlineData("non_positive_step")]
    [InlineData("below_horizon")]
    [InlineData("zero_area")]
    public void MissingHighValueFailuresAreExplicitAndNeverPermitReady(string scenario)
    {
        using var fixture = LoadFixture();
        var input = BuildInput(fixture.RootElement.GetProperty("input"));
        var expectedBlocker = scenario switch
        {
            "non_positive_step" => SetStep(input, 0.0),
            "below_horizon" => SetBelowHorizon(input),
            "zero_area" => SetZeroArea(input),
            _ => throw new ArgumentOutOfRangeException(nameof(scenario))
        };

        var exception = Record.Exception(() => ForwardVerticalSliceV0.Run(input));
        Assert.Null(exception);
        var actual = ForwardVerticalSliceV0.Run(input);
        Assert.False(actual.Complete);
        Assert.False(actual.Available);
        Assert.Contains(expectedBlocker, actual.Blockers);
        Assert.False(actual.PermitReadyCertified);
        Assert.False(actual.Solar.PermitReadyCertified);
        Assert.False(actual.ShadowSlices.PermitReadyCertified);
        Assert.False(actual.Duration.PermitReadyCertified);
        Assert.False(actual.Contours.PermitReadyCertified);
    }

    [Fact]
    public void ExactTranslatedPolygonBoundaryGridPointIsInside()
    {
        var input = new ForwardVerticalSliceInputV0
        {
            LatitudeDeg = 0.0, SolarDeclinationDeg = 0.0, TrueNorthDeg = 0.0,
            TrueSolarStartMinutes = 720.0, TrueSolarEndMinutes = 722.0, SunTimeStepMinutes = 1.0,
            MeasurementPlaneElevationM = 4.0, GridResolutionM = 2.0, AnalysisMarginM = 0.0,
            MaxGridPoints = 100, ContourLevelsMinutes = new List<double> { 0.5 },
            Caster = new ConvexPrismCasterV0
            {
                BaseZM = 0.0, TopZM = 12.0,
                FootprintPointsM = new List<Point2M>
                    { new(100, -50), new(104, -50), new(104, -46), new(100, -46) }
            }
        };

        var actual = ForwardVerticalSliceV0.Run(input);
        Assert.True(actual.Complete);
        var boundary = Assert.Single(actual.Duration.DurationValues, point =>
            Math.Abs(point.X-100.0) <= DurationTolerance && Math.Abs(point.Y+50.0) <= DurationTolerance);
        Assert.Equal(2.0, boundary.ShadowDurationMinutes, DurationTolerance);
    }

    private static string SetStep(ForwardVerticalSliceInputV0 input, double value)
    {
        input.SunTimeStepMinutes = value;
        return "invalid_sun_time_step";
    }

    private static string SetBelowHorizon(ForwardVerticalSliceInputV0 input)
    {
        input.TrueSolarStartMinutes = 0.0;
        input.TrueSolarEndMinutes = 60.0;
        input.SunTimeStepMinutes = 30.0;
        return "solar_sample_at_or_below_horizon";
    }

    private static string SetZeroArea(ForwardVerticalSliceInputV0 input)
    {
        input.Caster.FootprintPointsM = new List<Point2M>
            { new(100, -40), new(102, -40), new(104, -40) };
        return "zero_area_footprint";
    }

    private static void AssertRepresentativeSlices(JsonElement expected, ForwardVerticalSliceResultV0 actual)
    {
        foreach (var slice in expected.EnumerateArray())
        {
            var index = slice.GetProperty("sample_index").GetInt32();
            var expectedPoints = ReadPoints(slice.GetProperty("points_m"));
            AssertPolygonEquivalent(expectedPoints, actual.ShadowSlices.Slices[index].Polygons[0].PointsM);
        }
    }

    private static void AssertDuration(JsonElement expected, DurationResultV0 actual)
    {
        Assert.Equal(expected.GetProperty("spatial_resolution_m").GetDouble(), actual.SpatialResolutionM,
            DurationTolerance);
        Assert.Equal(expected.GetProperty("grid_point_count").GetInt32(), actual.GridPointCount);
        Assert.Equal(expected.GetProperty("maximum_shadow_duration_minutes").GetDouble(),
            actual.MaximumShadowDurationMinutes, DurationTolerance);
        Assert.Equal(expected.GetProperty("shadowed_point_count").GetInt32(), actual.ShadowedPointCount);
        var grid = expected.GetProperty("grid_spec");
        Assert.NotNull(actual.GridSpec);
        Assert.Equal(grid.GetProperty("origin_x_m").GetDouble(), actual.GridSpec!.OriginXM, CoordinateTolerance);
        Assert.Equal(grid.GetProperty("origin_y_m").GetDouble(), actual.GridSpec.OriginYM, CoordinateTolerance);
        Assert.Equal(grid.GetProperty("resolution_m").GetDouble(), actual.GridSpec.ResolutionM, CoordinateTolerance);
        Assert.Equal(grid.GetProperty("x_count").GetInt32(), actual.GridSpec.XCount);
        Assert.Equal(grid.GetProperty("y_count").GetInt32(), actual.GridSpec.YCount);
        Assert.Equal(grid.GetProperty("ordering").GetString(), actual.GridSpec.Ordering);
        Assert.Equal(actual.GridSpec.OriginXM+(actual.GridSpec.XCount-1)*actual.GridSpec.ResolutionM,
            actual.GridSpec.MaxXM, CoordinateTolerance);
        Assert.Equal(actual.GridSpec.OriginYM+(actual.GridSpec.YCount-1)*actual.GridSpec.ResolutionM,
            actual.GridSpec.MaxYM, CoordinateTolerance);

        var expectedPoints = expected.GetProperty("duration_grid").EnumerateArray().ToArray();
        Assert.Equal(expectedPoints.Length, actual.DurationValues.Count);
        for (var index = 0; index < expectedPoints.Length; index++)
        {
            Assert.Equal(expectedPoints[index].GetProperty("x_m").GetDouble(),
                actual.DurationValues[index].X, CoordinateTolerance);
            Assert.Equal(expectedPoints[index].GetProperty("y_m").GetDouble(),
                actual.DurationValues[index].Y, CoordinateTolerance);
            Assert.Equal(expectedPoints[index].GetProperty("shadow_duration_minutes").GetDouble(),
                actual.DurationValues[index].ShadowDurationMinutes, DurationTolerance);
        }
    }

    private static void AssertChangingStateIntegration(JsonElement duration, DurationResultV0 actual)
    {
        var point = duration.GetProperty("changing_state_point");
        var states = point.GetProperty("states").EnumerateArray().Select(value => value.GetBoolean() ? 1 : 0).ToArray();
        Assert.True(states.Distinct().Count() > 1);
        Assert.NotEqual(states[2], states[3]);
        var independent = 70*(states[0]+states[1])/2.0 + 70*(states[1]+states[2])/2.0
            + 60*(states[2]+states[3])/2.0;
        Assert.Equal(point.GetProperty("duration_minutes").GetDouble(), independent, DurationTolerance);
        var actualPoint = Assert.Single(actual.DurationValues, value =>
            Math.Abs(value.X-point.GetProperty("x").GetDouble()) <= CoordinateTolerance &&
            Math.Abs(value.Y-point.GetProperty("y").GetDouble()) <= CoordinateTolerance);
        Assert.Equal(independent, actualPoint.ShadowDurationMinutes, DurationTolerance);
    }

    private static void AssertContours(JsonElement expected, ContoursResultV0 actual)
    {
        Assert.Equal(expected.GetProperty("generated_levels_minutes").EnumerateArray().Select(x => x.GetDouble()),
            actual.GeneratedLevelsMinutes);
        Assert.Equal(expected.GetProperty("contour_count").GetInt32(), actual.ContourCount);
        Assert.Equal(expected.GetProperty("closed_contour_count").GetInt32(), actual.ClosedContourCount);
        Assert.Equal(expected.GetProperty("open_contour_count").GetInt32(), actual.OpenContourCount);
        var unmatched = actual.Contours.ToList();
        foreach (var expectedContour in expected.GetProperty("items").EnumerateArray())
        {
            var level = expectedContour.GetProperty("level_minutes").GetDouble();
            var closed = expectedContour.GetProperty("closed").GetBoolean();
            var points = ReadPoints(expectedContour.GetProperty("points_m"));
            var matches = unmatched.Where(candidate =>
                Math.Abs(candidate.LevelMinutes-level) <= DurationTolerance && candidate.Closed == closed &&
                TopologicallyEquivalent(points, candidate.PointsM, closed)).ToList();
            var match = Assert.Single(matches);
            Assert.Equal(expectedContour.GetProperty("point_count").GetInt32(), match.PointCount);
            Assert.Equal(expectedContour.GetProperty("length_m").GetDouble(), match.LengthM, LengthTolerance);
            unmatched.Remove(match);
        }
        Assert.Empty(unmatched);
    }

    private static bool TopologicallyEquivalent(Point2M[] expected, IList<Point2M> actual, bool closed)
    {
        if (expected.Length != actual.Count) return false;
        if (!closed) return SequenceMatches(expected, actual, 0, 1) || SequenceMatches(expected, actual, actual.Count-1, -1);
        var expectedCycle = IsSamePoint(expected[0], expected[^1]) ? expected[..^1] : expected;
        var actualCycle = IsSamePoint(actual[0], actual[^1]) ? actual.Take(actual.Count-1).ToArray() : actual.ToArray();
        if (expectedCycle.Length != actualCycle.Length) return false;
        for (var start = 0; start < actualCycle.Length; start++)
            if (SequenceMatches(expectedCycle, actualCycle, start, 1) ||
                SequenceMatches(expectedCycle, actualCycle, start, -1)) return true;
        return false;
    }

    private static bool IsSamePoint(Point2M left, Point2M right) =>
        Math.Abs(left.X-right.X) <= CoordinateTolerance && Math.Abs(left.Y-right.Y) <= CoordinateTolerance;

    private static bool SequenceMatches(Point2M[] expected, IList<Point2M> actual, int start, int direction)
    {
        for (var index = 0; index < expected.Length; index++)
        {
            var actualIndex = (start+direction*index+actual.Count)%actual.Count;
            if (Math.Abs(expected[index].X-actual[actualIndex].X) > CoordinateTolerance ||
                Math.Abs(expected[index].Y-actual[actualIndex].Y) > CoordinateTolerance) return false;
        }
        return true;
    }

    private static void AssertPolygonEquivalent(Point2M[] expected, IList<Point2M> actual) =>
        Assert.True(TopologicallyEquivalent(expected, actual, true));

    private static Point2M[] ReadPoints(JsonElement points) => points.EnumerateArray()
        .Select(point => new Point2M(point.GetProperty("x").GetDouble(), point.GetProperty("y").GetDouble()))
        .ToArray();

    private static string Snapshot(ForwardVerticalSliceResultV0 result) => JsonSerializer.Serialize(new
    {
        Samples = result.Solar.Samples.Select(x => new { x.SampleIndex, x.TrueSolarMinutes }).ToArray(),
        Duration = result.Duration.DurationValues.Select(x => new { x.X, x.Y, x.ShadowDurationMinutes }).ToArray(),
        Contours = result.Contours.Contours.Select(x => new { x.LevelMinutes, x.ContourIndex, x.Closed,
            Points = x.PointsM.Select(point => new { point.X, point.Y }).ToArray() }).ToArray(),
        SolarBlockers = result.Solar.Blockers.ToArray(), SolarWarnings = result.Solar.Warnings.ToArray(),
        SliceBlockers = result.ShadowSlices.Blockers.ToArray(), SliceWarnings = result.ShadowSlices.Warnings.ToArray(),
        DurationBlockers = result.Duration.Blockers.ToArray(), DurationWarnings = result.Duration.Warnings.ToArray(),
        ContourBlockers = result.Contours.Blockers.ToArray(), ContourWarnings = result.Contours.Warnings.ToArray(),
        Blockers = result.Blockers.ToArray(), Warnings = result.Warnings.ToArray()
    });

    private static JsonDocument LoadFixture() => JsonDocument.Parse(File.ReadAllText(Path.Combine(
        AppContext.BaseDirectory, "fixtures", "parity", "forward_portable_parity_v0.json")));

    private static ForwardVerticalSliceInputV0 BuildInput(JsonElement input)
    {
        var caster = input.GetProperty("caster");
        return new ForwardVerticalSliceInputV0
        {
            LatitudeDeg = input.GetProperty("latitude_deg").GetDouble(),
            SolarDeclinationDeg = input.GetProperty("solar_declination_deg").GetDouble(),
            TrueNorthDeg = input.GetProperty("true_north_deg").GetDouble(),
            TrueSolarStartMinutes = input.GetProperty("true_solar_start_minutes").GetDouble(),
            TrueSolarEndMinutes = input.GetProperty("true_solar_end_minutes").GetDouble(),
            SunTimeStepMinutes = input.GetProperty("sun_time_step_minutes").GetDouble(),
            MeasurementPlaneElevationM = input.GetProperty("measurement_plane_elevation_m").GetDouble(),
            GridResolutionM = input.GetProperty("grid_resolution_m").GetDouble(),
            AnalysisMarginM = input.GetProperty("analysis_margin_m").GetDouble(),
            MaxGridPoints = input.GetProperty("max_grid_points").GetInt32(),
            ContourLevelsMinutes = input.GetProperty("contour_levels_minutes").EnumerateArray()
                .Select(value => value.GetDouble()).ToList(),
            Caster = new ConvexPrismCasterV0
            {
                BaseZM = caster.GetProperty("base_z_m").GetDouble(),
                TopZM = caster.GetProperty("top_z_m").GetDouble(),
                FootprintPointsM = ReadPoints(caster.GetProperty("footprint_points_m")).ToList()
            }
        };
    }
}
