using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using ShadowCore;

namespace DynamoShadow;

/// <summary>Primitive-only Zero-Touch boundary for the constrained compiled v0 slice.</summary>
public static class ForwardVerticalSliceNodes
{
    public static IDictionary<string, object?> Run(
        double latitudeDeg, double solarDeclinationDeg, double trueNorthDeg,
        double trueSolarStartMinutes, double trueSolarEndMinutes, double sunTimeStepMinutes,
        double measurementPlaneElevationM, double gridResolutionM, double analysisMarginM,
        int maxGridPoints, IList<double> contourLevelsMinutes,
        IList<double> footprintXM, IList<double> footprintYM, double baseZM, double topZM)
    {
        if (footprintXM == null || footprintYM == null || footprintXM.Count != footprintYM.Count)
            throw new ArgumentException("Footprint X/Y lists must have matching lengths.");
        var input = new ForwardVerticalSliceInputV0 {
            LatitudeDeg=latitudeDeg, SolarDeclinationDeg=solarDeclinationDeg, TrueNorthDeg=trueNorthDeg,
            TrueSolarStartMinutes=trueSolarStartMinutes, TrueSolarEndMinutes=trueSolarEndMinutes,
            SunTimeStepMinutes=sunTimeStepMinutes, MeasurementPlaneElevationM=measurementPlaneElevationM,
            GridResolutionM=gridResolutionM, AnalysisMarginM=analysisMarginM, MaxGridPoints=maxGridPoints,
            ContourLevelsMinutes=contourLevelsMinutes,
            Caster=new ConvexPrismCasterV0 { BaseZM=baseZM, TopZM=topZM,
                FootprintPointsM=footprintXM.Select((x,index)=>new Point2M(x,footprintYM[index])).ToList() }
        };
        return (IDictionary<string, object?>)ToPrimitive(ForwardVerticalSliceV0.Run(input))!;
    }

    private static object? ToPrimitive(object? value)
    {
        if (value == null || value is string || value is bool || value is int || value is long || value is double) return value;
        if (value is IEnumerable sequence) { var list=new List<object?>(); foreach(var item in sequence) list.Add(ToPrimitive(item)); return list; }
        var result=new SortedDictionary<string,object?>(StringComparer.Ordinal);
        foreach(var property in value.GetType().GetProperties(BindingFlags.Instance|BindingFlags.Public).OrderBy(p=>p.Name,StringComparer.Ordinal))
            result[ToSnakeCase(property.Name)]=ToPrimitive(property.GetValue(value));
        return result;
    }
    private static string ToSnakeCase(string name) => string.Concat(name.Select((c,i)=>(char.IsUpper(c)&&i>0?"_":"")+char.ToLowerInvariant(c)));
}
