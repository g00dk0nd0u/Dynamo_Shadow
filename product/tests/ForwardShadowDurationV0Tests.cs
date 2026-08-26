using ShadowCore;
using Xunit;

namespace ShadowCore.Tests;

public sealed class ForwardShadowDurationV0Tests
{
    [Fact] public void TrapezoidalHelperHalfIntervalTransitionIsFifteenMinutes() =>
        Assert.Equal(15, ForwardShadowDurationV0.IntegrateShadowStatesTrapezoidal(
            new[] { 0, 1 }, new[] { 0.0, 30.0 }));

    [Fact] public void TrapezoidalHelperFullIntervalIsThirtyMinutes() =>
        Assert.Equal(30, ForwardShadowDurationV0.IntegrateShadowStatesTrapezoidal(
            new[] { 1, 1 }, new[] { 0.0, 30.0 }));

    [Fact] public void TrapezoidalHelperNonUniformIntervalsUseActualTimes() =>
        Assert.Equal(45, ForwardShadowDurationV0.IntegrateShadowStatesTrapezoidal(
            new[] { 1, 0, 1 }, new[] { 0.0, 30.0, 90.0 }));

    [Fact] public void RectangleContainmentIncludesInteriorAndExcludesExterior()
    {
        var polygons = Polygons((0, "outer", Loop((0,0),(4,0),(4,4),(0,4))));
        Assert.True(ForwardShadowDurationV0.ContainsShadowPoint(polygons, 2, 2));
        Assert.False(ForwardShadowDurationV0.ContainsShadowPoint(polygons, 5, 2));
    }

    [Fact] public void InnerLoopRemovesHoleFromItsComponent()
    {
        var polygons = Polygons((0,"outer",Loop((0,0),(6,0),(6,6),(0,6))),
            (0,"inner",Loop((2,2),(4,2),(4,4),(2,4))));
        Assert.True(ForwardShadowDurationV0.ContainsShadowPoint(polygons, 1, 1));
        Assert.False(ForwardShadowDurationV0.ContainsShadowPoint(polygons, 3, 3));
    }

    [Fact] public void DisconnectedComponentsAreCombinedByLogicalOr()
    {
        var polygons = Polygons((0,"outer",Loop((0,0),(2,0),(2,2),(0,2))),
            (1,"outer",Loop((5,0),(7,0),(7,2),(5,2))));
        Assert.True(ForwardShadowDurationV0.ContainsShadowPoint(polygons, 1, 1));
        Assert.True(ForwardShadowDurationV0.ContainsShadowPoint(polygons, 6, 1));
        Assert.False(ForwardShadowDurationV0.ContainsShadowPoint(polygons, 3, 1));
    }

    [Fact] public void PolygonBoundaryIsInside()
    {
        Assert.True(ForwardShadowDurationV0.ContainsShadowPoint(
            Polygons((0,"outer",Loop((0,0),(2,0),(2,2),(0,2)))), 0, 1));
    }

    [Fact] public void BuildsExactBoundsAndDeterministicRowMajorGrid()
    {
        var result = ForwardShadowDurationV0.Build(Snapshot(new[] { 0.0, 30.0 },
            Polygons((0,"outer",Loop((0,0),(2,0),(2,1),(0,1))))), Settings(1, .5));
        Assert.True(result.Complete); Assert.Equal(12, result.GridPointCount);
        Assert.Equal("row_major_y_then_x", result.GridSpec!.Ordering);
        Assert.Equal(-.5, result.GridSpec.OriginXM); Assert.Equal(-.5, result.GridSpec.OriginYM);
        Assert.Equal(4, result.GridSpec.XCount); Assert.Equal(3, result.GridSpec.YCount);
        Assert.Equal(2.5, result.GridSpec.MaxXM); Assert.Equal(1.5, result.GridSpec.MaxYM);
        Assert.Equal(new[] { (-.5,-.5),(.5,-.5),(1.5,-.5),(2.5,-.5),(-.5,.5) },
            result.DurationValues.Take(5).Select(p => (p.X,p.Y)));
    }

    [Fact] public void GridCapBlocksWithoutResolutionDegradation()
    {
        var settings = Settings(1, 0); settings.MaxGridPoints = 8;
        var result = ForwardShadowDurationV0.Build(Snapshot(new[] { 0.0, 30.0 },
            Polygons((0,"outer",Loop((0,0),(2,0),(2,2),(0,2))))), settings);
        Assert.False(result.Complete); Assert.Contains("max_duration_grid_points_exceeded", result.Blockers);
        Assert.Equal(1, result.SpatialResolutionM); Assert.Empty(result.DurationValues);
    }

    [Fact] public void OneSliceCannotProduceDuration()
    {
        var result = ForwardShadowDurationV0.Build(Snapshot(new[] { 0.0 },
            Polygons((0,"outer",Loop((0,0),(1,0),(1,1),(0,1))))), Settings());
        Assert.Contains("invalid_duration_input_or_settings", result.Blockers);
        Assert.False(result.ReadyForEqualTimeContourGeneration);
    }

    [Fact] public void OnlyCompleteResultIsContourReadyAndNeverPermitCertified()
    {
        var complete = ForwardShadowDurationV0.Build(Snapshot(new[] { 0.0, 30.0 },
            Polygons((0,"outer",Loop((0,0),(1,0),(1,1),(0,1))))), Settings());
        var failed = ForwardShadowDurationV0.Build(null, Settings());
        Assert.True(complete.Available); Assert.True(complete.Complete);
        Assert.True(complete.ReadyForEqualTimeContourGeneration); Assert.False(complete.PermitReadyCertified);
        Assert.False(failed.ReadyForEqualTimeContourGeneration); Assert.False(failed.PermitReadyCertified);
        Assert.Contains("complete_unified_shadow_slices_required", failed.Blockers);
    }

    [Fact] public void NonUniformTimelineHasNullNominalStepAndMatchesFrozenSemantics()
    {
        var first = Polygons((0,"outer",Loop((0,0),(1,0),(1,1),(0,1))));
        var empty = Array.Empty<ForwardUnifiedShadowPolygonSnapshotV0>();
        var snapshot = Snapshot(new[] { 0.0, 30.0, 90.0 }, first, empty, first);
        snapshot.Warnings = new[] { "snapshot warning" };
        var result = ForwardShadowDurationV0.Build(snapshot, Settings(1, 0));
        Assert.Null(result.TemporalStepMinutes);
        Assert.Equal(45, Assert.Single(result.DurationValues, p => p.X == 0 && p.Y == 0).ShadowDurationMinutes);
        Assert.Contains("snapshot warning", result.Warnings);
        Assert.Contains(ForwardShadowDurationV0.NumericalApproximationWarning, result.Warnings);
    }

    private static ForwardShadowDurationSettingsV0 Settings(double resolution=1,double margin=0) =>
        new() { GridResolutionM=resolution, AnalysisMarginM=margin, MaxGridPoints=1000 };

    private static ForwardUnifiedShadowSliceSnapshotV0 Snapshot(double[] times,
        params IReadOnlyList<ForwardUnifiedShadowPolygonSnapshotV0>[] polygons)
    {
        if (polygons.Length == 1) polygons = Enumerable.Repeat(polygons[0], times.Length).ToArray();
        return ForwardUnifiedShadowSliceSnapshotV0.Create(times.Select((time,index) =>
            new ForwardUnifiedShadowTimeSliceSnapshotV0 { SliceIndex=index, SampleIndex=index,
                TrueSolarMinutes=time, Complete=true, Polygons=polygons[index] }).ToArray());
    }

    private static IReadOnlyList<ForwardUnifiedShadowPolygonSnapshotV0> Polygons(
        params (int Component,string Role,IReadOnlyList<Point2M> Points)[] values) =>
        values.Select((value,index) => new ForwardUnifiedShadowPolygonSnapshotV0 {
            PolygonIndex=index, ComponentIndex=value.Component, Role=value.Role,
            Closed=true, PointCount=value.Points.Count, PointsM=value.Points }).ToArray();

    private static IReadOnlyList<Point2M> Loop(params (double X,double Y)[] values) =>
        values.Select(value => new Point2M(value.X,value.Y)).ToArray();
}
