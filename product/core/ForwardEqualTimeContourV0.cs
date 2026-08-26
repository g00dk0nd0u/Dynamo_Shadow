using System;
using System.Collections.Generic;
using System.Linq;

namespace ShadowCore;

public sealed class ForwardEqualTimeContourSettingsV0
{
    public double? EqualTimeContourIntervalMinutes { get; set; }
    public IReadOnlyList<double>? EqualTimeContourLevelsMinutes { get; set; }
    public int? MaxEqualTimeContourLevels { get; set; }
}

public sealed class EqualTimeContourV0
{
    public double LevelMinutes { get; set; }
    public int ContourIndex { get; set; }
    public bool Closed { get; set; }
    public int PointCount => PointsM.Count;
    public double LengthM { get; set; }
    public IReadOnlyList<Point2M> PointsM { get; set; } = Array.Empty<Point2M>();
}

public sealed class ForwardEqualTimeContourResultV0
{
    public bool Available { get; set; }
    public bool Complete { get; set; }
    public string Method => ForwardEqualTimeContourV0.Method;
    public string SourceDurationMethod => ForwardShadowDurationV0.Method;
    public IReadOnlyList<double> RequestedLevelsMinutes { get; set; } = Array.Empty<double>();
    public IReadOnlyList<double> GeneratedLevelsMinutes { get; set; } = Array.Empty<double>();
    public int ContourCount => Contours.Count;
    public int ClosedContourCount => Contours.Count(x => x.Closed);
    public int OpenContourCount => Contours.Count(x => !x.Closed);
    public int EffectiveSegmentCap { get; set; }
    public IReadOnlyList<EqualTimeContourV0> Contours { get; set; } = Array.Empty<EqualTimeContourV0>();
    public IReadOnlyList<string> Blockers { get; set; } = Array.Empty<string>();
    public IReadOnlyList<string> Warnings { get; set; } = new[] { ForwardEqualTimeContourV0.DiagnosticWarning };
    public bool PermitReadyCertified => false;
}

/// <summary>Autodesk-free port of runtime/shadow_contours.py production semantics.</summary>
public static class ForwardEqualTimeContourV0
{
    public const string Method = "marching_squares_linear_interpolation_v1";
    public const string DiagnosticWarning = "Contour levels are technical/diagnostic time levels, not statutory thresholds.";
    public const int FixedHardSegmentCap = 100_000;
    private const double Epsilon = 1e-9;

    private readonly struct Key : IEquatable<Key>, IComparable<Key>
    {
        internal Key(double x, double y) { X = x; Y = y; }
        internal double X { get; } internal double Y { get; }
        internal static Key From(Point2M p) => new(Math.Round(p.X, 10, MidpointRounding.ToEven), Math.Round(p.Y, 10, MidpointRounding.ToEven));
        public int CompareTo(Key other) { var x = X.CompareTo(other.X); return x != 0 ? x : Y.CompareTo(other.Y); }
        public bool Equals(Key other) => X.Equals(other.X) && Y.Equals(other.Y);
        public override bool Equals(object? value) => value is Key other && Equals(other);
        public override int GetHashCode() { unchecked { return (X.GetHashCode()*397)^Y.GetHashCode(); } }
    }
    private readonly struct Edge : IEquatable<Edge>, IComparable<Edge>
    {
        internal Edge(Key a, Key b) { if (a.CompareTo(b) <= 0) { A=a; B=b; } else { A=b; B=a; } }
        internal Key A { get; } internal Key B { get; }
        public int CompareTo(Edge other) { var a=A.CompareTo(other.A); return a != 0 ? a : B.CompareTo(other.B); }
        public bool Equals(Edge other) => A.Equals(other.A) && B.Equals(other.B);
        public override bool Equals(object? value) => value is Edge other && Equals(other);
        public override int GetHashCode() { unchecked { return (A.GetHashCode()*397)^B.GetHashCode(); } }
    }

    public static ForwardEqualTimeContourResultV0 Build(ForwardShadowDurationResultV0? duration,
        ForwardEqualTimeContourSettingsV0? settings = null, int? maximumSegmentCount = null)
    {
        if (duration is null || !duration.Complete || !duration.ReadyForEqualTimeContourGeneration)
            return Failed("complete_shadow_duration_required");
        var grid = duration.GridSpec;
        if (!ValidGrid(grid)) return Failed("duration_grid_spec_missing_or_invalid");
        var expected = (long)grid!.XCount*grid.YCount;
        if (duration.DurationValues is null || duration.DurationValues.Count != expected)
            return Failed("duration_grid_size_mismatch");
        if (duration.DurationValues.Any(x => x is null || !ForwardGeometryV0.Finite(x.ShadowDurationMinutes)))
            return Failed("invalid_equal_time_contour_settings");

        IReadOnlyList<double> levels;
        try { levels = Levels(settings, duration.MaximumShadowDurationMinutes); }
        catch (OverflowException) { return Failed("max_equal_time_contour_levels_exceeded"); }
        catch (ArgumentException) { return Failed("invalid_equal_time_contour_settings"); }
        var cap = Math.Min(FixedHardSegmentCap, Math.Max(1, maximumSegmentCount ?? FixedHardSegmentCap));
        var contours = new List<EqualTimeContourV0>();
        foreach (var level in levels)
        {
            var segments = new List<Tuple<Point2M,Point2M>>();
            for (var iy=0; iy<grid.YCount-1; iy++) for (var ix=0; ix<grid.XCount-1; ix++)
            {
                var ids = new[] { iy*grid.XCount+ix, iy*grid.XCount+ix+1, (iy+1)*grid.XCount+ix+1, (iy+1)*grid.XCount+ix };
                var corners = ids.Select(id => new DurationPointV0 { X=grid.OriginXM+(id%grid.XCount)*grid.ResolutionM,
                    Y=grid.OriginYM+(id/grid.XCount)*grid.ResolutionM,
                    ShadowDurationMinutes=duration.DurationValues[id].ShadowDurationMinutes }).ToArray();
                CellSegments(corners, level, segments);
                if (segments.Count > cap) return Failed("equal_time_contour_segment_budget_exceeded");
            }
            foreach (var line in Stitch(segments))
            {
                double length=0;
                for (var i=0; i<line.Count-1; i++) length += Math.Sqrt(Math.Pow(line[i+1].X-line[i].X,2)+Math.Pow(line[i+1].Y-line[i].Y,2));
                if (!ForwardGeometryV0.Finite(length) || line.Any(p => !ForwardGeometryV0.Finite(p.X) || !ForwardGeometryV0.Finite(p.Y)))
                    return Failed("duration_grid_spec_missing_or_invalid");
                contours.Add(new EqualTimeContourV0 { LevelMinutes=level, Closed=line.Count>2 && Key.From(line[0]).Equals(Key.From(line[line.Count-1])), LengthM=length, PointsM=line });
            }
        }
        contours = contours.OrderBy(x=>x.LevelMinutes).ThenBy(x=>x.PointsM[0].X).ThenBy(x=>x.PointsM[0].Y).ThenBy(x=>x.PointCount).ToList();
        foreach (var group in contours.GroupBy(x=>x.LevelMinutes)) { var index=0; foreach (var contour in group) contour.ContourIndex=index++; }
        return new ForwardEqualTimeContourResultV0 { Available=true, Complete=true, EffectiveSegmentCap=cap,
            RequestedLevelsMinutes=levels, GeneratedLevelsMinutes=contours.Select(x=>x.LevelMinutes).Distinct().OrderBy(x=>x).ToArray(), Contours=contours };
    }

    private static bool ValidGrid(GridSpecV0? g)
    {
        if (g is null || g.XCount<2 || g.YCount<2 || g.Ordering!="row_major_y_then_x" ||
            !ForwardGeometryV0.Finite(g.OriginXM) || !ForwardGeometryV0.Finite(g.OriginYM) ||
            !ForwardGeometryV0.Finite(g.ResolutionM) || g.ResolutionM<=0) return false;
        return ForwardGeometryV0.Finite(g.OriginXM+(g.XCount-1)*g.ResolutionM) && ForwardGeometryV0.Finite(g.OriginYM+(g.YCount-1)*g.ResolutionM);
    }
    private static IReadOnlyList<double> Levels(ForwardEqualTimeContourSettingsV0? s, double maximum)
    {
        var limit=s?.MaxEqualTimeContourLevels ?? 100;
        if (limit<=0 || !ForwardGeometryV0.Finite(maximum)) throw new ArgumentException();
        IEnumerable<double> values;
        if (s?.EqualTimeContourLevelsMinutes is not null) values=s.EqualTimeContourLevelsMinutes;
        else
        {
            var interval=s?.EqualTimeContourIntervalMinutes ?? 60.0;
            if (!ForwardGeometryV0.Finite(interval) || interval<=0) throw new ArgumentException();
            var count=maximum<0 ? 0 : Math.Floor(maximum/interval);
            if (!ForwardGeometryV0.Finite(count) || count>int.MaxValue) throw new OverflowException();
            values=Enumerable.Range(1,(int)count).Select(i=>interval*i);
        }
        var result=values.ToArray();
        if (result.Any(x=>!ForwardGeometryV0.Finite(x)||x<=0)) throw new ArgumentException();
        result=result.Distinct().OrderBy(x=>x).ToArray();
        if (result.Length>limit) throw new OverflowException();
        return result;
    }
    private static Point2M Interpolate(DurationPointV0 a, DurationPointV0 b, double level)
    {
        var delta=b.ShadowDurationMinutes-a.ShadowDurationMinutes;
        var t=Math.Abs(delta)<=Epsilon ? .5 : (level-a.ShadowDurationMinutes)/delta;
        t=Math.Min(1,Math.Max(0,t)); return new Point2M(a.X+t*(b.X-a.X),a.Y+t*(b.Y-a.Y));
    }
    private static void CellSegments(DurationPointV0[] c,double level,List<Tuple<Point2M,Point2M>> output)
    {
        var edges=new[]{(0,1),(1,2),(2,3),(3,0)}; var points=new Dictionary<int,Point2M>(); var active=new List<int>();
        var code=0; for(var i=0;i<4;i++) if(c[i].ShadowDurationMinutes>=level) code|=1<<i;
        if(code==0||code==15)return;
        for(var i=0;i<4;i++) if((c[edges[i].Item1].ShadowDurationMinutes>=level)!=(c[edges[i].Item2].ShadowDurationMinutes>=level)) { active.Add(i); points[i]=Interpolate(c[edges[i].Item1],c[edges[i].Item2],level); }
        if(active.Count==2){output.Add(Tuple.Create(points[active[0]],points[active[1]]));return;} if(active.Count!=4)return;
        var centerHigh=c.Average(x=>x.ShadowDurationMinutes)>=level;
        var pairs=(code==5&&centerHigh)||(code==10&&!centerHigh) ? new[]{(0,1),(2,3)} : new[]{(0,3),(1,2)};
        foreach(var pair in pairs)output.Add(Tuple.Create(points[pair.Item1],points[pair.Item2]));
    }
    private static List<IReadOnlyList<Point2M>> Stitch(IEnumerable<Tuple<Point2M,Point2M>> segments)
    {
        var unique=new SortedDictionary<Edge,Tuple<Key,Key>>();
        foreach(var segment in segments){var a=Key.From(segment.Item1);var b=Key.From(segment.Item2);if(Math.Sqrt(Math.Pow(segment.Item1.X-segment.Item2.X,2)+Math.Pow(segment.Item1.Y-segment.Item2.Y,2))<=Epsilon)continue;unique[new Edge(a,b)]=Tuple.Create(a,b);}
        var adjacency=new SortedDictionary<Key,List<Key>>(); foreach(var pair in unique.Values){if(!adjacency.ContainsKey(pair.Item1))adjacency[pair.Item1]=new List<Key>();if(!adjacency.ContainsKey(pair.Item2))adjacency[pair.Item2]=new List<Key>();adjacency[pair.Item1].Add(pair.Item2);adjacency[pair.Item2].Add(pair.Item1);}foreach(var neighbors in adjacency.Values)neighbors.Sort();
        var unused=new SortedSet<Edge>(unique.Keys);var lines=new List<IReadOnlyList<Point2M>>();while(unused.Count>0){var endpoints=adjacency.Keys.Where(p=>adjacency[p].Count(n=>unused.Contains(new Edge(p,n)))==1).ToList();var start=endpoints.Count>0?endpoints[0]:unused.Min.A;var line=new List<Point2M>{new(start.X,start.Y)};Key? previous=null;var current=start;while(true){var candidates=adjacency[current].Where(n=>(previous is null||!n.Equals(previous.Value))&&unused.Contains(new Edge(current,n))).ToList();if(candidates.Count==0)break;var next=candidates[0];unused.Remove(new Edge(current,next));line.Add(new Point2M(next.X,next.Y));previous=current;current=next;if(current.Equals(start))break;}if(line.Count>1)lines.Add(line);}
        return lines.OrderBy(x=>x[0].X).ThenBy(x=>x[0].Y).ThenBy(x=>x.Count).ThenBy(x=>string.Join(";",x.Select(p=>$"{p.X:R},{p.Y:R}")),StringComparer.Ordinal).ToList();
    }
    private static ForwardEqualTimeContourResultV0 Failed(string blocker) => new() { Blockers=new[]{blocker} };
}
