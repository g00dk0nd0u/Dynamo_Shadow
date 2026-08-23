using RevitShadow; using Xunit;
namespace RevitShadow.Tests;
public sealed class ForwardRevitFormalShadowUnionSummaryV0Tests
{
 [Fact] public void OverlapRemovalIsDurationReadyButNeverCertified(){var s=Create(20,15,10);Assert.True(s.Complete);Assert.True(s.ReadyForDurationAccumulation);Assert.Equal(5,s.OverlapRemovedAreaM2);Assert.False(s.PermitReadyCertified);}
 [Theory][InlineData(20,20.0002,10)][InlineData(20,9.9998,10)][InlineData(20,0,10)] public void PythonAreaBoundsBlock(double i,double u,double l){var s=Create(i,u,l);Assert.Contains("union_area_validation_failed",s.Blockers);Assert.False(s.Complete);}
 [Fact] public void BooleanFailureIsNotSilent(){var s=ForwardRevitFormalShadowUnionSummaryV0.Create(2,0,0,2,0,2,1,20,0,10,.01,new[]{"revit_boolean_union_failed"});Assert.Contains("revit_boolean_union_failed",s.Blockers);Assert.False(s.Complete);}
 static ForwardRevitFormalShadowUnionSummaryV0 Create(double i,double u,double l)=>ForwardRevitFormalShadowUnionSummaryV0.Create(2,1,1,1,1,0,0,i,u,l,.01);
}
