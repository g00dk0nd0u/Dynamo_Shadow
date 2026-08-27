using ShadowCore;
using Xunit;

namespace ShadowCore.Tests;

public sealed class ForwardEqualTimeContourV0Tests
{
    [Fact] public void TwoByTwoMonotonicGridProducesInterpolatedOpenContourFromGridSpec()
    {
        var result=Build(new[]{0.0,10.0,0.0,10.0},new[]{5.0},originX:10,originY:20,pointOffset:1000);
        var contour=Assert.Single(result.Contours); Assert.True(result.Complete); Assert.False(contour.Closed);
        Assert.Equal(new[]{(10.5,20.0),(10.5,21.0)},contour.PointsM.Select(p=>(p.X,p.Y)));
        Assert.Equal(1,contour.LengthM,10);
    }

    [Fact] public void CaseFiveMeanHighUsesPythonPairing()
    {
        var result=Build(new[]{10.0,0.0,0.0,10.0},new[]{5.0});
        Assert.Equal(2,result.ContourCount);
        Assert.Equal(new[]{((0.0,.5),(.5,1.0)),((.5,0.0),(1.0,.5))},
            result.Contours.Select(c=>((c.PointsM[0].X,c.PointsM[0].Y),(c.PointsM[1].X,c.PointsM[1].Y))));
    }

    [Fact] public void CaseTenMeanHighUsesPythonPairing()
    {
        var result=Build(new[]{0.0,10.0,10.0,0.0},new[]{5.0});
        Assert.Equal(new[]{((0.0,.5),(.5,0.0)),((.5,1.0),(1.0,.5))},
            result.Contours.Select(c=>((c.PointsM[0].X,c.PointsM[0].Y),(c.PointsM[1].X,c.PointsM[1].Y))));
    }

    [Fact] public void AdjacentCellsStitchDeterministicallyAndSharedEdgeIsNotDuplicated()
    {
        var result=Build(new[]{0.0,10.0,20.0,0.0,10.0,20.0},new[]{5.0},3,2);
        var contour=Assert.Single(result.Contours);
        Assert.Equal(new[]{(.5,0.0),(.5,1.0)},contour.PointsM.Select(p=>(p.X,p.Y)));
    }

    [Fact] public void EnclosedHighPointProducesClosedContour()
    {
        var result=Build(new[]{0d,0,0,0,10,0,0,0,0},new[]{5.0},3,3);
        var contour=Assert.Single(result.Contours); Assert.True(contour.Closed); Assert.Equal(contour.PointsM[0].X,contour.PointsM[^1].X); Assert.Equal(5,contour.PointCount);
    }

    [Fact] public void MultipleLevelsAreOrderedAndIndicesRestartPerLevel()
    {
        var result=Build(new[]{10d,0,0,10},new[]{7.0,3.0});
        Assert.Equal(new[]{3d,7},result.RequestedLevelsMinutes); Assert.Equal(new[]{3d,7},result.GeneratedLevelsMinutes);
        Assert.Equal(new[]{3d,3,7,7},result.Contours.Select(x=>x.LevelMinutes)); Assert.All(result.Contours.GroupBy(x=>x.LevelMinutes),g=>Assert.Equal(new[]{0,1},g.Select(x=>x.ContourIndex)));
    }

    [Fact] public void ExplicitLevelsAreSortedAndUnique() => Assert.Equal(new[]{2d,5},Build(new[]{0d,10,0,10},new[]{5d,2,5}).RequestedLevelsMinutes);

    [Fact] public void DefaultAndConfiguredIntervalsGenerateLevelsThroughMaximum()
    {
        var duration=Duration(new[]{0d,130,0,130});
        Assert.Equal(new[]{60d,120},ForwardEqualTimeContourV0.Build(duration).RequestedLevelsMinutes);
        Assert.Equal(new[]{50d,100},ForwardEqualTimeContourV0.Build(duration,new(){EqualTimeContourIntervalMinutes=50}).RequestedLevelsMinutes);
    }

    [Fact] public void MaximumLevelCountIsEnforced()
    {
        var result=ForwardEqualTimeContourV0.Build(Duration(new[]{0d,10,0,10}),new(){EqualTimeContourLevelsMinutes=new[]{1d,2},MaxEqualTimeContourLevels=1});
        Assert.Equal("max_equal_time_contour_levels_exceeded",Assert.Single(result.Blockers));
    }

    [Fact] public void GridSizeMismatchIsBlocked()
    {
        var duration=Duration(new[]{0d,1,0,1}); duration.DurationValues=duration.DurationValues.Take(3).ToArray();
        Assert.Equal("duration_grid_size_mismatch",Assert.Single(ForwardEqualTimeContourV0.Build(duration).Blockers));
    }

    [Theory] [InlineData(false,true)] [InlineData(true,false)]
    public void CompleteAndContourReadyAreBothRequired(bool complete,bool ready)
    {
        var duration=Duration(new[]{0d,1,0,1});duration.Complete=complete;duration.ReadyForEqualTimeContourGeneration=ready;
        Assert.Equal("complete_shadow_duration_required",Assert.Single(ForwardEqualTimeContourV0.Build(duration).Blockers));
    }

    [Fact] public void InvalidGridSpecIsBlocked()
    {
        var duration=Duration(new[]{0d,1,0,1});duration.GridSpec!.ResolutionM=0;
        Assert.Equal("duration_grid_spec_missing_or_invalid",Assert.Single(ForwardEqualTimeContourV0.Build(duration).Blockers));
    }

    [Fact] public void SegmentCapStopsCurrentLevel()
    {
        var result=ForwardEqualTimeContourV0.Build(Duration(new[]{10d,0,0,10}),new(){EqualTimeContourLevelsMinutes=new[]{5d}},1);
        Assert.Equal("equal_time_contour_segment_budget_exceeded",Assert.Single(result.Blockers));
    }

    [Fact] public void NoGeneratedContourIsStillComplete()
    {
        var result=Build(new[]{0d,1,0,1},new[]{2d}); Assert.True(result.Complete); Assert.True(result.Available); Assert.Empty(result.Contours); Assert.Empty(result.GeneratedLevelsMinutes);
    }

    [Fact] public void ResultIsDiagnosticOnlyAndDoesNotPropagateDurationWarnings()
    {
        var duration=Duration(new[]{0d,10,0,10});duration.Warnings=new[]{"duration warning"};
        var result=ForwardEqualTimeContourV0.Build(duration,new(){EqualTimeContourLevelsMinutes=new[]{5d}});
        Assert.False(result.PermitReadyCertified); Assert.Equal(ForwardEqualTimeContourV0.DiagnosticWarning,Assert.Single(result.Warnings)); Assert.DoesNotContain("duration warning",result.Warnings);
        Assert.Equal(ForwardEqualTimeContourV0.Method,result.Method); Assert.Equal(ForwardShadowDurationV0.Method,result.SourceDurationMethod);
    }

    [Fact] public void EffectiveCapClampsToSupportedRange()
    {
        Assert.Equal(1,ForwardEqualTimeContourV0.Build(Duration(new[]{0d,1,0,1}),maximumSegmentCount:0).EffectiveSegmentCap);
        Assert.Equal(ForwardEqualTimeContourV0.FixedHardSegmentCap,ForwardEqualTimeContourV0.Build(Duration(new[]{0d,1,0,1}),maximumSegmentCount:int.MaxValue).EffectiveSegmentCap);
    }

    [Fact] public void CompactTwoByTwoFieldMatchesMaterializedPathAndIgnoresPointCoordinates()
    {
        var duration=Duration(new[]{0d,10,0,10},originX:10,originY:20,pointOffset:1000);
        var settings=new ForwardEqualTimeContourSettingsV0{EqualTimeContourLevelsMinutes=new[]{5d}};
        AssertEquivalent(ForwardEqualTimeContourV0.Build(duration,settings),
            ForwardEqualTimeContourV0.Build(duration,settings,durationField:Field(duration,new[]{0d,10,0,10})));
    }

    [Fact] public void CompactMultipleLevelsMatchMaterializedPath()
    {
        var duration=Duration(new[]{10d,0,0,10});
        var settings=new ForwardEqualTimeContourSettingsV0{EqualTimeContourLevelsMinutes=new[]{7d,3}};
        AssertEquivalent(ForwardEqualTimeContourV0.Build(duration,settings),
            ForwardEqualTimeContourV0.Build(duration,settings,durationField:Field(duration,new[]{10d,0,0,10})));
    }

    [Theory]
    [InlineData(new double[]{10,0,0,10})]
    [InlineData(new double[]{0,10,10,0})]
    public void CompactAmbiguousCasesMatchMaterializedPath(double[] values)
    {
        var duration=Duration(values);
        var settings=new ForwardEqualTimeContourSettingsV0{EqualTimeContourLevelsMinutes=new[]{5d}};
        AssertEquivalent(ForwardEqualTimeContourV0.Build(duration,settings),
            ForwardEqualTimeContourV0.Build(duration,settings,durationField:Field(duration,values)));
    }

    [Fact] public void CompactValueCountMismatchIsBlocked()
    {
        var duration=Duration(new[]{0d,1,0,1});
        Assert.Equal("duration_grid_size_mismatch",Assert.Single(ForwardEqualTimeContourV0.Build(
            duration,durationField:Field(duration,new[]{0d,1,0})).Blockers));
    }

    [Fact] public void CompactGridMismatchIsExplicitlyBlocked()
    {
        var duration=Duration(new[]{0d,1,0,1}); var field=Field(duration,new[]{0d,1,0,1});
        field.GridSpec=new GridSpecV0{OriginXM=99,OriginYM=0,ResolutionM=1,XCount=2,YCount=2,MaxXM=100,MaxYM=1};
        Assert.Equal("duration_grid_spec_missing_or_invalid",Assert.Single(
            ForwardEqualTimeContourV0.Build(duration,durationField:field).Blockers));
    }

    [Theory] [InlineData(double.NaN)] [InlineData(double.PositiveInfinity)]
    public void InvalidCompactScalarIsBlocked(double invalid)
    {
        var duration=Duration(new[]{0d,1,0,1});
        Assert.Equal("invalid_equal_time_contour_settings",Assert.Single(ForwardEqualTimeContourV0.Build(
            duration,durationField:Field(duration,new[]{0d,invalid,0,1})).Blockers));
    }

    [Fact] public void DurationToCompactFieldToContourPipelineIsAutodeskFree()
    {
        var built=ForwardShadowDurationV0.BuildWithField(
            new ForwardUnifiedShadowSliceSnapshotV0{Available=true,Complete=true,ReadyForDurationAccumulation=true,
                Slices=new[]{0d,30}.Select((time,index)=>new ForwardUnifiedShadowTimeSliceSnapshotV0{
                    SliceIndex=index,SampleIndex=index,TrueSolarMinutes=time,Complete=true,
                    Polygons=new[]{new ForwardUnifiedShadowPolygonSnapshotV0{PolygonIndex=0,ComponentIndex=0,
                        Role="outer",Closed=true,PointCount=4,PointsM=new[]{new Point2M(0,0),new Point2M(1,0),
                            new Point2M(1,1),new Point2M(0,1)}}}}).ToArray()},
            new ForwardShadowDurationSettingsV0{GridResolutionM=1,AnalysisMarginM=0,MaxGridPoints=100});
        var contours=ForwardEqualTimeContourV0.Build(built.Result,
            new(){EqualTimeContourLevelsMinutes=new[]{15d}},durationField:built.Field);
        Assert.True(built.Result.Complete); Assert.NotNull(built.Field); Assert.True(contours.Complete);
    }

    [Fact] public void CompactLargeContractGeneratesContoursWithoutMaterializedDurationPoints()
    {
        var duration=Duration(new[]{0d,30,0,30});
        duration.DurationValues=Array.Empty<DurationPointV0>();
        var contours=ForwardEqualTimeContourV0.Build(duration,
            new(){EqualTimeContourLevelsMinutes=new[]{15d}},durationField:Field(duration,new[]{0d,30,0,30}));

        Assert.True(contours.Complete);
        Assert.NotEmpty(contours.Contours);
    }

    private static ForwardShadowDurationFieldV0 Field(ForwardShadowDurationResultV0 duration,double[] values) => new()
    {
        Values=values,GridSpec=duration.GridSpec,LogicalPointCount=values.Length
    };

    private static void AssertEquivalent(ForwardEqualTimeContourResultV0 expected,ForwardEqualTimeContourResultV0 actual)
    {
        Assert.Equal(expected.RequestedLevelsMinutes,actual.RequestedLevelsMinutes);
        Assert.Equal(expected.GeneratedLevelsMinutes,actual.GeneratedLevelsMinutes);
        Assert.Equal(expected.ContourCount,actual.ContourCount); Assert.Equal(expected.ClosedContourCount,actual.ClosedContourCount);
        Assert.Equal(expected.OpenContourCount,actual.OpenContourCount); Assert.Equal(expected.Blockers,actual.Blockers);
        Assert.Equal(expected.PermitReadyCertified,actual.PermitReadyCertified);
        Assert.Equal(expected.Contours.Count,actual.Contours.Count);
        for(var i=0;i<expected.Contours.Count;i++)
        {
            var a=expected.Contours[i];var b=actual.Contours[i];
            Assert.Equal(a.LevelMinutes,b.LevelMinutes);Assert.Equal(a.ContourIndex,b.ContourIndex);
            Assert.Equal(a.Closed,b.Closed);Assert.Equal(a.LengthM,b.LengthM,10);
            Assert.Equal(a.PointsM.Select(p=>(p.X,p.Y)),b.PointsM.Select(p=>(p.X,p.Y)));
        }
    }

    private static ForwardEqualTimeContourResultV0 Build(double[] values,double[] levels,int xCount=2,int yCount=2,double originX=0,double originY=0,double pointOffset=0) =>
        ForwardEqualTimeContourV0.Build(Duration(values,xCount,yCount,originX,originY,pointOffset),new(){EqualTimeContourLevelsMinutes=levels});

    private static ForwardShadowDurationResultV0 Duration(double[] values,int xCount=2,int yCount=2,double originX=0,double originY=0,double pointOffset=0) => new()
    {
        Available=true,Complete=true,ReadyForEqualTimeContourGeneration=true,MaximumShadowDurationMinutes=values.Max(),
        GridSpec=new GridSpecV0{OriginXM=originX,OriginYM=originY,ResolutionM=1,XCount=xCount,YCount=yCount},
        DurationValues=values.Select((value,index)=>new DurationPointV0{X=pointOffset+index,Y=pointOffset-index,ShadowDurationMinutes=value}).ToArray()
    };
}
