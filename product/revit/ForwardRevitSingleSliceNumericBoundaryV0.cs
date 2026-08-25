using System;

namespace RevitShadow;

public sealed class ForwardRevitSingleSliceNumericResultV0
{
    public bool Complete { get; set; }
    public double PlaneInternal { get; set; }
    public double ValidationToleranceInternal { get; set; }
    public string? Blocker { get; set; }
}

/// <summary>Host-neutral contract for the two Revit unit conversions in the resolved native tail.</summary>
public static class ForwardRevitSingleSliceNumericBoundaryV0
{
    public static ForwardRevitSingleSliceNumericResultV0 Resolve(double measurementPlaneElevationM,
        double validationToleranceM, Func<double, double> metersToInternal)
    {
        if (metersToInternal is null) throw new ArgumentNullException(nameof(metersToInternal));
        double plane;
        try { plane = metersToInternal(measurementPlaneElevationM); }
        catch (Exception) { return Failed("measurement_plane_unit_conversion_failed"); }
        if (!double.IsFinite(validationToleranceM) || validationToleranceM < 0.0)
            return Failed("numeric_conversion_failed");
        double tolerance;
        try { tolerance = metersToInternal(validationToleranceM); }
        catch (Exception) { return Failed("numeric_conversion_failed"); }
        return new ForwardRevitSingleSliceNumericResultV0 { Complete = true,
            PlaneInternal = plane, ValidationToleranceInternal = tolerance };
    }

    private static ForwardRevitSingleSliceNumericResultV0 Failed(string blocker) =>
        new() { Blocker = blocker };
}
