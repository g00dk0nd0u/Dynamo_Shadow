#if REVIT_API
using System; using System.Collections.Generic; using Autodesk.Revit.DB;
namespace RevitShadow;
public sealed class ForwardRevitFormalShadowUnionComponentV0{public ForwardRevitFormalShadowUnionComponentV0(IReadOnlyList<CurveLoop> loops)=>Loops=loops; public IReadOnlyList<CurveLoop> Loops{get;}}
public sealed class ForwardRevitFormalShadowUnionResultV0:IDisposable
{public ForwardRevitFormalShadowUnionResultV0(IReadOnlyList<ForwardRevitFormalShadowUnionComponentV0> components,ForwardRevitFormalShadowUnionSummaryV0 summary){Components=components;Summary=summary;} public IReadOnlyList<ForwardRevitFormalShadowUnionComponentV0> Components{get;} public ForwardRevitFormalShadowUnionSummaryV0 Summary{get;} public void Dispose(){foreach(var c in Components)foreach(var l in c.Loops)l.Dispose();}}
#endif
