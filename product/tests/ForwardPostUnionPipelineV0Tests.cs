using ShadowCore;
using Xunit;

namespace ShadowCore.Tests;

public sealed class ForwardPostUnionPipelineV0Tests
{
    [Fact] public void SmallGridRunsDurationAndContoursEndToEnd()
    {
        var built=Build(Snapshot(Outer((0,0),(2,0),(2,1),(0,1))),Settings(1,.5),new[]{15d});
        var result=built.Result;

        Assert.True(result.Available); Assert.True(result.Complete);
        Assert.True(result.Duration.Complete); Assert.True(result.EqualTimeContours.Complete);
        Assert.Equal(ForwardShadowDurationV0.Method,result.Duration.Method);
        Assert.Equal(ForwardShadowDurationV0.Method,result.EqualTimeContours.SourceDurationMethod);
        Assert.Equal("row_major_y_then_x",result.Duration.GridSpec!.Ordering);
        Assert.Equal(30,result.Duration.MaximumShadowDurationMinutes);
        Assert.Equal(new[]{0d,0,0,0,0,30,30,0,0,0,0,0},built.DurationField!.Values);
        Assert.Equal(new[]{15d},result.EqualTimeContours.GeneratedLevelsMinutes);
        Assert.False(result.PermitReadyCertified);
        Assert.Contains(ForwardShadowDurationV0.NumericalApproximationWarning,result.Warnings);
        Assert.Contains(ForwardEqualTimeContourV0.DiagnosticWarning,result.Warnings);
    }

    [Fact] public void HoleSemanticsSurviveOrchestration()
    {
        var polygons=new[]{
            Polygon(0,"outer",(0,0),(4,0),(4,4),(0,4)),
            Polygon(0,"inner",(1,1),(3,1),(3,3),(1,3))};
        var built=Build(Snapshot(polygons),Settings(1,0),new[]{15d});

        Assert.True(built.Result.Complete);
        var field=built.DurationField!;
        Assert.Equal(30,field.Values[0]);
        Assert.Equal(0,field.Values[2*5+2]);
        Assert.Equal(16,built.Result.Duration.ShadowedPointCount);
    }

    [Fact] public void MemoryBlockerStopsBeforeContoursAndFieldAllocation()
    {
        var settings=Settings(1,0); settings.MaxGridPoints=300_000;
        var built=Build(Snapshot(Outer((0,0),(52,0),(52,4716),(0,4716))),settings,new[]{15d},
            new ForwardShadowDurationExecutionOptionsV0{AvailablePhysicalMemoryBytes=1});

        Assert.Equal("large_grid_memory_budget_exceeded",Assert.Single(built.Result.Blockers));
        Assert.False(built.Result.Complete);
        Assert.Equal(built.Result.Duration.Available,built.Result.Available);
        Assert.False(built.Result.EqualTimeContours.Available);
        Assert.False(built.Result.EqualTimeContours.Complete); Assert.Null(built.DurationField);
        Assert.DoesNotContain(ForwardEqualTimeContourV0.DiagnosticWarning,built.Result.Warnings);
        Assert.Contains(ForwardShadowDurationV0.NumericalApproximationWarning,built.Result.Warnings);
        Assert.Equal(0,built.Result.Duration.EngineDiagnostics!.ContainmentEvaluationCount);
    }

    [Fact] public void ContourBlockerLeavesCompletedDurationAvailable()
    {
        var input=Input(Snapshot(Outer((0,0),(2,0),(2,1),(0,1))),Settings(1,.5),new[]{15d});
        input.MaximumContourSegmentCount=1;
        var built=ForwardPostUnionPipelineV0.Build(input);

        Assert.True(built.Result.Duration.Complete); Assert.True(built.Result.Duration.Available);
        Assert.NotNull(built.DurationField);
        Assert.False(built.Result.EqualTimeContours.Complete);
        Assert.False(built.Result.EqualTimeContours.Available);
        Assert.False(built.Result.Complete); Assert.False(built.Result.Available);
        Assert.Equal("equal_time_contour_segment_budget_exceeded",Assert.Single(built.Result.Blockers));
    }

    [Fact] public void LargeGridUsesCompactFieldDirectlyForContours()
    {
        var settings=Settings(1,0); settings.MaxGridPoints=300_000;
        var built=Build(Snapshot(Outer((0,0),(52,0),(52,4716),(0,4716))),settings,new[]{15d});

        Assert.True(built.Result.Complete);
        Assert.Equal(ForwardShadowDurationV0.CompactLargeStorageMode,built.Result.Duration.StorageMode);
        Assert.False(built.Result.Duration.DurationGridMaterialized);
        Assert.Empty(built.Result.Duration.DurationValues);
        Assert.Equal(250_001,Assert.IsType<ForwardShadowDurationFieldV0>(built.DurationField).LogicalPointCount);
        Assert.True(built.Result.EqualTimeContours.Complete);
    }

    private static ForwardPostUnionPipelineBuildResultV0 Build(ForwardUnifiedShadowSliceSnapshotV0 snapshot,
        ForwardShadowDurationSettingsV0 settings,double[] levels,ForwardShadowDurationExecutionOptionsV0? options=null) =>
        ForwardPostUnionPipelineV0.Build(Input(snapshot,settings,levels,options));

    private static ForwardPostUnionPipelineInputV0 Input(ForwardUnifiedShadowSliceSnapshotV0 snapshot,
        ForwardShadowDurationSettingsV0 settings,double[] levels,ForwardShadowDurationExecutionOptionsV0? options=null) => new()
    { Snapshot=snapshot,DurationSettings=settings,DurationExecutionOptions=options,
      ContourSettings=new(){EqualTimeContourLevelsMinutes=levels} };

    private static ForwardShadowDurationSettingsV0 Settings(double resolution,double margin) => new()
    {GridResolutionM=resolution,AnalysisMarginM=margin,MaxGridPoints=10_000};

    private static ForwardUnifiedShadowSliceSnapshotV0 Snapshot(IReadOnlyList<ForwardUnifiedShadowPolygonSnapshotV0> polygons) =>
        ForwardUnifiedShadowSliceSnapshotV0.Create(new[]{0d,30}.Select((time,index)=>new ForwardUnifiedShadowTimeSliceSnapshotV0
        {SliceIndex=index,SampleIndex=index,TrueSolarMinutes=time,Complete=true,Polygons=polygons}).ToArray());

    private static ForwardUnifiedShadowPolygonSnapshotV0[] Outer(params (double x,double y)[] points) =>
        new[]{Polygon(0,"outer",points)};

    private static ForwardUnifiedShadowPolygonSnapshotV0 Polygon(int component,string role,params (double x,double y)[] points) => new()
    {PolygonIndex=0,ComponentIndex=component,Role=role,Closed=true,PointCount=points.Length,
     PointsM=points.Select(p=>new Point2M(p.x,p.y)).ToArray()};
}
