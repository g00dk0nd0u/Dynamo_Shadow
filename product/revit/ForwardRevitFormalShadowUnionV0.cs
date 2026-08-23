#if REVIT_API
using System; using System.Collections.Generic; using Autodesk.Revit.DB;
namespace RevitShadow;
/// <summary>Revit-native per-slice union mirroring runtime/shadow_union.py; no fallback.</summary>
public static class ForwardRevitFormalShadowUnionV0
{
 public static ForwardRevitFormalShadowUnionResultV0 Union(IReadOnlyList<ForwardRevitFormalShadowComponentV0>? source,double planeZ,double closureToleranceM=.01)
 {
  var output=new List<ForwardRevitFormalShadowUnionComponentV0>(); var blockers=new List<string>(); var owned=new List<Solid>(); var active=new List<Solid>();
  int attempts=0,successes=0,failures=0,retries=0; double inputArea=0,largest=0,unionArea=0; int inputs=source?.Count??0;
  try{
   if(!double.IsFinite(planeZ)||!double.IsFinite(closureToleranceM)||closureToleranceM<0)throw new Failure("numeric_conversion_failed");
   double thickness=UnitUtils.ConvertToInternalUnits(ForwardRevitFormalShadowUnionSummaryV0.AdapterThicknessM,UnitTypeId.Meters);
   foreach(var component in source??Array.Empty<ForwardRevitFormalShadowComponentV0>()){
    if(component.Loops.Count==0)throw new Failure("invalid_formal_shadow_component"); var profiles=new List<CurveLoop>();
    try{
     // All loops came from the same 5E-A base face. Preserve that native grouping;
     // CreateExtrusionGeometry itself validates the profile collection and holes.
     foreach(var loop in component.Loops)profiles.Add(CurveLoop.CreateViaCopy(loop));
     var solid=GeometryCreationUtilities.CreateExtrusionGeometry(profiles,XYZ.BasisZ,thickness);
     if(solid is null||!(solid.Volume>0))throw new Failure("adapter_solid_invalid"); owned.Add(solid);active.Add(solid);
     var area=ToM2(solid.Volume/thickness);inputArea+=area;largest=Math.Max(largest,area);
    }finally{DisposeLoops(profiles);}
   }
   bool changed=true;
   while(changed){changed=false;for(int i=0;i<active.Count&&!changed;i++)for(int j=i+1;j<active.Count;j++){
    var parts=UnionPair(active[i],active[j],owned,ref attempts,ref successes,ref failures,ref retries);
    if(parts.Count>=2)continue; active.RemoveAt(j);active.RemoveAt(i);active.InsertRange(i,parts);changed=true;break;
   }}
   var final=new List<Solid>();foreach(var solid in active){var parts=Split(solid);owned.AddRange(parts);final.AddRange(parts);}
   foreach(var solid in final){unionArea+=ToM2(solid.Volume/thickness);output.Add(new(CopyBaseLoops(solid,planeZ)));}
  }catch(Failure e){blockers.Add(e.Code);}catch(Exception){blockers.Add("formal_shadow_union_slice_failed");}finally{DisposeUnique(owned);}
  int loopCount=0;foreach(var c in output)loopCount+=c.Loops.Count;
  var summary=ForwardRevitFormalShadowUnionSummaryV0.Create(inputs,output.Count,loopCount,attempts,successes,failures,retries,inputArea,unionArea,largest,closureToleranceM,blockers);
  if(!summary.Complete){foreach(var c in output)DisposeLoops(c.Loops);output.Clear();}
  return new(output,summary);
 }
 static List<Solid> UnionPair(Solid a,Solid b,List<Solid> owned,ref int attempts,ref int successes,ref int failures,ref int retries){Exception? first=null;
  for(int pass=0;pass<2;pass++){attempts++;if(pass==1)retries++;try{var u=BooleanOperationsUtils.ExecuteBooleanOperation(pass==0?a:b,pass==0?b:a,BooleanOperationsType.Union);if(u is null)throw new InvalidOperationException();owned.Add(u);var parts=Split(u);owned.AddRange(parts);successes++;return parts;}catch(Exception e){failures++;first??=e;}}
  throw new Failure("revit_boolean_union_failed",first);
 }
 static List<Solid> Split(Solid solid){var parts=new List<Solid>(SolidUtils.SplitVolumes(solid));if(parts.Count==0)throw new Failure("split_volume_invalid");foreach(var p in parts)if(!(p.Volume>0))throw new Failure("split_volume_invalid");return parts;}
 static IReadOnlyList<CurveLoop> CopyBaseLoops(Solid solid,double planeZ){PlanarFace? selected=null;double distance=double.PositiveInfinity;
  foreach(Face face in solid.Faces)if(face is PlanarFace p&&Math.Abs(Math.Abs(p.FaceNormal.Z)-1)<=1e-7){double d=Math.Abs(p.Origin.Z-planeZ);if(d<distance){selected=p;distance=d;}}
  if(selected is null)throw new Failure("union_base_planar_face_unavailable");var acquired=new List<CurveLoop>(selected.GetEdgesAsCurveLoops());var copies=new List<CurveLoop>();
  try{foreach(var loop in acquired){if(loop.IsOpen()||!loop.HasPlane())throw new Failure("union_output_loop_invalid");int count=0;foreach(var curve in loop){if(curve is not Line)throw new Failure("union_output_non_line_loop");count++;}if(count<3)throw new Failure("union_output_loop_invalid");copies.Add(CurveLoop.CreateViaCopy(loop));}if(copies.Count==0)throw new Failure("union_output_has_no_loops");return copies;}catch{DisposeLoops(copies);throw;}finally{DisposeLoops(acquired);}
 }
 static double ToM2(double area)=>UnitUtils.ConvertFromInternalUnits(area,UnitTypeId.SquareMeters);
 static void DisposeLoops(IEnumerable<CurveLoop> loops){foreach(var l in loops)l.Dispose();}
 static void DisposeUnique(IEnumerable<Solid> solids){var seen=new HashSet<Solid>(ReferenceEqualityComparer.Instance);foreach(var s in solids)if(s is not null&&seen.Add(s))s.Dispose();}
 sealed class Failure:Exception{public Failure(string code,Exception? inner=null):base(code,inner)=>Code=code;public string Code{get;}}
}
#endif
