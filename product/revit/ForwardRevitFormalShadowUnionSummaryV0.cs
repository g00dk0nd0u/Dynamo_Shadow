using System;
using System.Collections.Generic;
namespace RevitShadow;
/// <summary>JSON-safe summary for one Revit-native shadow-union time slice.</summary>
public sealed class ForwardRevitFormalShadowUnionSummaryV0
{
 public const double AdapterThicknessM=0.1;
 public bool Available{get;private set;} public bool Complete{get;private set;}
 public bool ReadyForDurationAccumulation{get;private set;} public bool PermitReadyCertified=>false;
 public int InputComponentCount{get;private set;} public int OutputComponentCount{get;private set;}
 public int OutputCurveLoopCount{get;private set;} public int BooleanOperationAttemptCount{get;private set;}
 public int BooleanOperationSuccessCount{get;private set;} public int BooleanOperationFailureCount{get;private set;}
 public int RetryCount{get;private set;} public double InputAreaM2Sum{get;private set;}
 public double UnifiedAreaM2{get;private set;} public double OverlapRemovedAreaM2{get;private set;}
 public double AreaBalanceErrorM2{get;private set;} public IReadOnlyList<string> Blockers{get;private set;}=Array.Empty<string>();
 public IReadOnlyList<string> Warnings{get;private set;}=Array.Empty<string>();
 public static ForwardRevitFormalShadowUnionSummaryV0 Create(int inputs,int outputs,int loops,int attempts,int successes,int failures,int retries,double inputArea,double unionArea,double largestArea,double closureToleranceM,IEnumerable<string>? operationBlockers=null,IEnumerable<string>? warnings=null)
 {
  var b=operationBlockers is null?new List<string>():new List<string>(operationBlockers);
  if(inputs<=0)b.Add("formal_shadow_components_required"); if(outputs<=0||loops<=0)b.Add("no_valid_native_union_curve_loop");
  var tolerance=Math.Max(1e-9,closureToleranceM*closureToleranceM);
  if(!double.IsFinite(inputArea)||!double.IsFinite(unionArea)||!double.IsFinite(largestArea)||!double.IsFinite(closureToleranceM)||closureToleranceM<0||unionArea<=0||unionArea>inputArea+tolerance||unionArea<largestArea-tolerance)b.Add("union_area_validation_failed");
  // A failed result does not return native loops. Keep the host-neutral counts
  // aligned with that ownership contract rather than describing discarded data.
  if(b.Count>0){outputs=0;loops=0;}
  return new(){Available=outputs>0&&loops>0,Complete=b.Count==0,ReadyForDurationAccumulation=b.Count==0,InputComponentCount=inputs,OutputComponentCount=outputs,OutputCurveLoopCount=loops,BooleanOperationAttemptCount=attempts,BooleanOperationSuccessCount=successes,BooleanOperationFailureCount=failures,RetryCount=retries,InputAreaM2Sum=inputArea,UnifiedAreaM2=unionArea,OverlapRemovedAreaM2=Math.Max(0,inputArea-unionArea),AreaBalanceErrorM2=Math.Max(0,unionArea-inputArea),Blockers=b,Warnings=warnings is null?Array.Empty<string>():new List<string>(warnings)};
 }
}
