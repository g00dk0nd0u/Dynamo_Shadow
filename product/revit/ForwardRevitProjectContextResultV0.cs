using System.Collections.Generic;

namespace RevitShadow;

public sealed class ForwardRevitProjectContextResultV0
{
    public bool Available { get; set; }
    public bool Complete { get; set; }
    public double? AverageGroundLevelElevationM { get; set; }
    public string? AverageGroundLevelSource { get; set; }
    public double? MeasurementHeightM { get; set; }
    public double? MeasurementPlaneElevationM { get; set; }
    public double? TrueNorthDeg { get; set; }
    public double? LatitudeDeg { get; set; }
    public IList<string> Blockers { get; } = new List<string>();
    public IList<string> Warnings { get; } = new List<string>();
    public bool PermitReadyCertified => false;
}
