using System;
using System.Collections.Generic;

namespace ShadowCore;

public sealed class Point2M
{
    public Point2M() { }
    public Point2M(double x, double y) { X = x; Y = y; }
    public double X { get; set; }
    public double Y { get; set; }
}

public sealed class ConvexPrismCasterV0
{
    public IList<Point2M> FootprintPointsM { get; set; } = new List<Point2M>();
    public double BaseZM { get; set; }
    public double TopZM { get; set; }
}

public sealed class ForwardVerticalSliceInputV0
{
    public double LatitudeDeg { get; set; }
    public double SolarDeclinationDeg { get; set; }
    public double TrueNorthDeg { get; set; }
    public double TrueSolarStartMinutes { get; set; }
    public double TrueSolarEndMinutes { get; set; }
    public double SunTimeStepMinutes { get; set; }
    public double MeasurementPlaneElevationM { get; set; }
    public double GridResolutionM { get; set; }
    public double AnalysisMarginM { get; set; }
    public int MaxGridPoints { get; set; }
    public IList<double> ContourLevelsMinutes { get; set; } = new List<double>();
    public ConvexPrismCasterV0 Caster { get; set; } = new ConvexPrismCasterV0();
}

internal static class ForwardGeometryV0
{
    internal const double Epsilon = 1e-9;
    internal static bool Finite(double value) => !double.IsNaN(value) && !double.IsInfinity(value);
    internal static double Cross(Point2M a, Point2M b, Point2M c) =>
        (b.X-a.X)*(c.Y-a.Y)-(b.Y-a.Y)*(c.X-a.X);
    internal static double SignedArea(IList<Point2M> points)
    {
        double area = 0;
        for (var i=0; i<points.Count; i++) { var a=points[i]; var b=points[(i+1)%points.Count]; area += a.X*b.Y-b.X*a.Y; }
        return area/2.0;
    }
    internal static bool OnSegment(double x,double y,Point2M a,Point2M b)
    {
        var cross=(x-a.X)*(b.Y-a.Y)-(y-a.Y)*(b.X-a.X);
        return Math.Abs(cross)<=Epsilon && x>=Math.Min(a.X,b.X)-Epsilon && x<=Math.Max(a.X,b.X)+Epsilon && y>=Math.Min(a.Y,b.Y)-Epsilon && y<=Math.Max(a.Y,b.Y)+Epsilon;
    }
    internal static bool Contains(IList<Point2M> p,double x,double y)
    {
        var inside=false;
        for(var i=0;i<p.Count;i++){var a=p[i];var b=p[(i+1)%p.Count];if(OnSegment(x,y,a,b))return true;if((a.Y>y)!=(b.Y>y)&&x<(b.X-a.X)*(y-a.Y)/(b.Y-a.Y)+a.X)inside=!inside;}
        return inside;
    }
    internal static List<Point2M> Hull(IEnumerable<Point2M> source)
    {
        var p=new List<Point2M>(source);p.Sort((a,b)=>a.X!=b.X?a.X.CompareTo(b.X):a.Y.CompareTo(b.Y));
        var unique=new List<Point2M>();foreach(var q in p)if(unique.Count==0||q.X!=unique[unique.Count-1].X||q.Y!=unique[unique.Count-1].Y)unique.Add(q);
        if(unique.Count<=1)return unique;var lower=new List<Point2M>();foreach(var q in unique){while(lower.Count>=2&&Cross(lower[lower.Count-2],lower[lower.Count-1],q)<=0)lower.RemoveAt(lower.Count-1);lower.Add(q);}var upper=new List<Point2M>();for(var i=unique.Count-1;i>=0;i--){var q=unique[i];while(upper.Count>=2&&Cross(upper[upper.Count-2],upper[upper.Count-1],q)<=0)upper.RemoveAt(upper.Count-1);upper.Add(q);}lower.RemoveAt(lower.Count-1);upper.RemoveAt(upper.Count-1);lower.AddRange(upper);return lower;
    }
}
