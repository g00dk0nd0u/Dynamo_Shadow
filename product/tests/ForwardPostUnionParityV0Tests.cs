using System.Text.Json;
using ShadowCore;
using Xunit;

namespace ShadowCore.Tests;

public sealed class ForwardPostUnionParityV0Tests
{
    private const double CoordinateTolerance = 1e-6;
    private const double DurationTolerance = 1e-9;
    private const double LengthTolerance = 1e-6;

    [Fact]
    public void ProductionPostUnionPipelineMatchesPythonDurationAndContours()
    {
        using var fixture = JsonDocument.Parse(File.ReadAllText(Path.Combine(
            AppContext.BaseDirectory, "fixtures", "parity", "forward_post_union_v0.json")));
        var input = fixture.RootElement.GetProperty("input");
        var expected = fixture.RootElement.GetProperty("expected");
        var tolerances = fixture.RootElement.GetProperty("tolerances");
        Assert.Equal(CoordinateTolerance, tolerances.GetProperty("coordinate_m").GetDouble());
        Assert.Equal(DurationTolerance, tolerances.GetProperty("duration_minutes").GetDouble());
        Assert.Equal(LengthTolerance, tolerances.GetProperty("length_m").GetDouble());
        var snapshot = BuildSnapshot(input.GetProperty("unified_shadow_slices"));

        var built = ForwardPostUnionPipelineV0.Build(new ForwardPostUnionPipelineInputV0 {
            Snapshot = snapshot,
            DurationSettings = new ForwardShadowDurationSettingsV0 {
                GridResolutionM = input.GetProperty("duration_settings").GetProperty("grid_resolution_m").GetDouble(),
                AnalysisMarginM = input.GetProperty("duration_settings").GetProperty("analysis_margin_m").GetDouble(),
                MaxGridPoints = input.GetProperty("duration_settings").GetProperty("max_duration_grid_points").GetInt32()
            },
            ContourSettings = new ForwardEqualTimeContourSettingsV0 {
                EqualTimeContourLevelsMinutes = ReadDoubles(input.GetProperty("contour_settings")
                    .GetProperty("equal_time_contour_levels_minutes"))
            }
        });

        Assert.True(built.Result.Complete);
        Assert.False(snapshot.PermitReadyCertified);
        Assert.False(built.Result.PermitReadyCertified);
        Assert.False(built.Result.Duration.PermitReadyCertified);
        Assert.False(built.Result.EqualTimeContours.PermitReadyCertified);
        AssertDuration(expected, built);
        AssertContours(expected, built.Result.EqualTimeContours);
        AssertChangingState(expected, snapshot, built.DurationField!);
    }

    private static void AssertDuration(JsonElement expected, ForwardPostUnionPipelineBuildResultV0 built)
    {
        var actual = built.Result.Duration;
        var expectedTemporalStep = expected.GetProperty("temporal_step_minutes");
        Assert.Equal(expectedTemporalStep.ValueKind == JsonValueKind.Null
            ? (double?)null : expectedTemporalStep.GetDouble(), actual.TemporalStepMinutes);
        var grid = expected.GetProperty("grid_spec");
        Assert.NotNull(actual.GridSpec);
        Assert.Equal(grid.GetProperty("origin_x_m").GetDouble(), actual.GridSpec!.OriginXM, CoordinateTolerance);
        Assert.Equal(grid.GetProperty("origin_y_m").GetDouble(), actual.GridSpec.OriginYM, CoordinateTolerance);
        Assert.Equal(grid.GetProperty("resolution_m").GetDouble(), actual.GridSpec.ResolutionM, CoordinateTolerance);
        Assert.Equal(grid.GetProperty("x_count").GetInt32(), actual.GridSpec.XCount);
        Assert.Equal(grid.GetProperty("y_count").GetInt32(), actual.GridSpec.YCount);
        Assert.Equal(grid.GetProperty("ordering").GetString(), actual.GridSpec.Ordering);
        Assert.Equal(expected.GetProperty("logical_grid_point_count").GetInt32(), built.DurationField!.LogicalPointCount);
        Assert.Equal(expected.GetProperty("logical_grid_point_count").GetInt32(), actual.GridPointCount);
        Assert.Equal(expected.GetProperty("maximum_shadow_duration_minutes").GetDouble(),
            actual.MaximumShadowDurationMinutes, DurationTolerance);
        Assert.Equal(expected.GetProperty("shadowed_point_count").GetInt32(), actual.ShadowedPointCount);
        var expectedValues = ReadDoubles(expected.GetProperty("duration_values_minutes"));
        Assert.Equal(expectedValues.Count, built.DurationField.Values.Count);
        for (var index = 0; index < expectedValues.Count; index++)
            Assert.Equal(expectedValues[index], built.DurationField.Values[index], DurationTolerance);
    }

    private static void AssertContours(JsonElement expected, ForwardEqualTimeContourResultV0 actual)
    {
        Assert.Equal(ReadDoubles(expected.GetProperty("requested_levels_minutes")), actual.RequestedLevelsMinutes);
        Assert.Equal(ReadDoubles(expected.GetProperty("generated_levels_minutes")), actual.GeneratedLevelsMinutes);
        Assert.Equal(expected.GetProperty("contour_count").GetInt32(), actual.ContourCount);
        Assert.Equal(expected.GetProperty("closed_contour_count").GetInt32(), actual.ClosedContourCount);
        Assert.Equal(expected.GetProperty("open_contour_count").GetInt32(), actual.OpenContourCount);
        var unmatched = actual.Contours.ToList();
        foreach (var item in expected.GetProperty("contours").EnumerateArray())
        {
            var points = ReadPoints(item.GetProperty("points_m"));
            var matches = unmatched.Where(candidate =>
                Math.Abs(candidate.LevelMinutes-item.GetProperty("level_minutes").GetDouble()) <= DurationTolerance &&
                candidate.Closed == item.GetProperty("closed").GetBoolean() &&
                TopologicallyEquivalent(points, candidate.PointsM, candidate.Closed)).ToList();
            var match = Assert.Single(matches);
            Assert.Equal(item.GetProperty("point_count").GetInt32(), match.PointCount);
            Assert.Equal(item.GetProperty("length_m").GetDouble(), match.LengthM, LengthTolerance);
            unmatched.Remove(match);
        }
        Assert.Empty(unmatched);
    }

    private static void AssertChangingState(JsonElement expected,
        ForwardUnifiedShadowSliceSnapshotV0 snapshot, ForwardShadowDurationFieldV0 field)
    {
        var point = expected.GetProperty("changing_state_point");
        var states = point.GetProperty("states").EnumerateArray().Select(x => x.GetBoolean() ? 1 : 0).ToArray();
        Assert.True(states.Distinct().Count() > 1);
        var integrated = ForwardShadowDurationV0.IntegrateShadowStatesTrapezoidal(
            states, snapshot.Slices.Select(x => x.TrueSolarMinutes).ToArray());
        Assert.Equal(point.GetProperty("duration_minutes").GetDouble(), integrated, DurationTolerance);
        var grid = field.GridSpec;
        var ix = (int)Math.Round((point.GetProperty("x_m").GetDouble()-grid.OriginXM)/grid.ResolutionM);
        var iy = (int)Math.Round((point.GetProperty("y_m").GetDouble()-grid.OriginYM)/grid.ResolutionM);
        Assert.Equal(integrated, field.Values[iy*grid.XCount+ix], DurationTolerance);
    }

    private static ForwardUnifiedShadowSliceSnapshotV0 BuildSnapshot(JsonElement source) =>
        ForwardUnifiedShadowSliceSnapshotV0.Create(source.GetProperty("slices").EnumerateArray().Select(slice =>
            new ForwardUnifiedShadowTimeSliceSnapshotV0 {
                SliceIndex = slice.GetProperty("slice_index").GetInt32(),
                SampleIndex = slice.GetProperty("sample_index").GetInt32(),
                TrueSolarMinutes = slice.GetProperty("true_solar_minutes").GetDouble(),
                Complete = slice.GetProperty("complete").GetBoolean(),
                Polygons = slice.GetProperty("polygons").EnumerateArray().Select(polygon =>
                    new ForwardUnifiedShadowPolygonSnapshotV0 {
                        PolygonIndex = polygon.GetProperty("polygon_index").GetInt32(),
                        ComponentIndex = polygon.GetProperty("component_index").GetInt32(),
                        Role = polygon.GetProperty("role").GetString()!,
                        Orientation = polygon.GetProperty("orientation").GetString()!,
                        Closed = polygon.GetProperty("closed").GetBoolean(),
                        PointCount = polygon.GetProperty("point_count").GetInt32(),
                        AreaM2 = polygon.GetProperty("area_m2").GetDouble(),
                        GenerationMethod = polygon.GetProperty("generation_method").GetString()!,
                        PointsM = ReadPoints(polygon.GetProperty("points_m"))
                    }).ToArray()
            }).ToArray());

    private static IReadOnlyList<double> ReadDoubles(JsonElement values) =>
        values.EnumerateArray().Select(value => value.GetDouble()).ToArray();

    private static Point2M[] ReadPoints(JsonElement points) => points.EnumerateArray()
        .Select(point => new Point2M(point.GetProperty("x").GetDouble(), point.GetProperty("y").GetDouble()))
        .ToArray();

    private static bool TopologicallyEquivalent(Point2M[] expected, IReadOnlyList<Point2M> actual, bool closed)
    {
        if (expected.Length != actual.Count) return false;
        if (!closed) return Matches(expected, actual, 0, 1) || Matches(expected, actual, actual.Count-1, -1);
        var expectedCycle = Same(expected[0], expected[^1]) ? expected[..^1] : expected;
        var actualCycle = Same(actual[0], actual[^1]) ? actual.Take(actual.Count-1).ToArray() : actual.ToArray();
        if (expectedCycle.Length != actualCycle.Length) return false;
        return Enumerable.Range(0, actualCycle.Length).Any(start =>
            Matches(expectedCycle, actualCycle, start, 1) || Matches(expectedCycle, actualCycle, start, -1));
    }

    private static bool Matches(IReadOnlyList<Point2M> expected, IReadOnlyList<Point2M> actual,
        int start, int direction) => Enumerable.Range(0, expected.Count).All(index =>
    {
        var actualIndex = (start+direction*index+actual.Count)%actual.Count;
        return Math.Abs(expected[index].X-actual[actualIndex].X) <= CoordinateTolerance &&
               Math.Abs(expected[index].Y-actual[actualIndex].Y) <= CoordinateTolerance;
    });

    private static bool Same(Point2M left, Point2M right) =>
        Math.Abs(left.X-right.X) <= CoordinateTolerance && Math.Abs(left.Y-right.Y) <= CoordinateTolerance;
}
