using ShadowCore;
using Xunit;

namespace ShadowCore.Tests;

public sealed class ForwardUnifiedShadowSliceSnapshotV0Tests
{
    [Fact] public void SingleOuterLoopIsNormalizedCounterclockwise()
    {
        var result = Classify(Loop((0,0),(0,4),(4,4),(4,0)));
        var polygon = Assert.Single(result.Polygons);
        Assert.True(result.Complete); Assert.Equal("outer", polygon.Role); Assert.Equal("ccw", polygon.Orientation);
        Assert.Equal(16, polygon.AreaM2); Assert.True(polygon.Closed); Assert.Equal(4, polygon.PointCount);
    }

    [Fact] public void ContainedSecondaryLoopIsClockwiseInnerDespiteReversedBaseFace()
    {
        var result = Classify(Loop((0,0),(0,8),(8,8),(8,0)), Loop((2,2),(6,2),(6,6),(2,6)));
        Assert.Equal(new[] { "outer", "inner" }, result.Polygons.Select(p => p.Role));
        Assert.Equal(new[] { "ccw", "cw" }, result.Polygons.Select(p => p.Orientation));
        Assert.True(Signed(result.Polygons[0].PointsM) > 0); Assert.True(Signed(result.Polygons[1].PointsM) < 0);
    }

    [Fact] public void NonContainedSecondaryLoopRemainsOuterAndIndicesAreDeterministic()
    {
        var result = ForwardUnifiedShadowComponentClassifierV0.Classify(new[] {
            Loop((0,0),(5,0),(5,5),(0,5)), Loop((10,0),(12,0),(12,2),(10,2)) }, 7);
        Assert.Equal(new[] { 0, 1 }, result.Polygons.Select(p => p.PolygonIndex));
        Assert.All(result.Polygons, p => { Assert.Equal(7, p.ComponentIndex); Assert.Equal("outer", p.Role); });
        Assert.All(result.Polygons, p => Assert.Equal(ForwardUnifiedShadowComponentClassifierV0.GenerationMethod, p.GenerationMethod));
    }

    [Fact] public void DegenerateLoopFailsAndNeverBecomesDurationReady()
    {
        var component = Classify(Loop((0,0),(1,0),(2,0)));
        Assert.False(component.Complete); Assert.Contains("union_output_loop_invalid", component.Blockers);
        var snapshot = ForwardUnifiedShadowSliceSnapshotV0.Create(new[] { new ForwardUnifiedShadowTimeSliceSnapshotV0 {
            SliceIndex = 0, SampleIndex = 0, Complete = false, Blockers = component.Blockers } });
        Assert.False(snapshot.Complete); Assert.False(snapshot.ReadyForDurationAccumulation); Assert.False(snapshot.PermitReadyCertified);
    }

    [Fact] public void CompleteSnapshotIsDurationReadyButNeverPermitCertified()
    {
        var snapshot = ForwardUnifiedShadowSliceSnapshotV0.Create(new[] { new ForwardUnifiedShadowTimeSliceSnapshotV0 {
            SliceIndex = 0, SampleIndex = 0, TrueSolarMinutes = 480, Complete = true,
            Polygons = Classify(Loop((0,0),(1,0),(1,1),(0,1))).Polygons } });
        Assert.True(snapshot.Available); Assert.True(snapshot.Complete); Assert.True(snapshot.ReadyForDurationAccumulation);
        Assert.False(snapshot.PermitReadyCertified);
    }

    private static ForwardUnifiedShadowComponentSnapshotV0 Classify(params IReadOnlyList<Point2M>[] loops) =>
        ForwardUnifiedShadowComponentClassifierV0.Classify(loops, 0);
    private static IReadOnlyList<Point2M> Loop(params (double X,double Y)[] values) => values.Select(p => new Point2M(p.X,p.Y)).ToArray();
    private static double Signed(IReadOnlyList<Point2M> p) => p.Select((a,i) => a.X*p[(i+1)%p.Count].Y-p[(i+1)%p.Count].X*a.Y).Sum()/2;
}
