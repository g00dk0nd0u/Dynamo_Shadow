namespace RevitShadow;

public sealed class ForwardRevitProjectContextInputV0
{
    public bool LevelSelected { get; set; }
    public double? SelectedLevelElevationInternal { get; set; }
    public double? FallbackAverageGroundLevelElevationM { get; set; }
    public double? MeasurementHeightM { get; set; }
    public double? RawActiveProjectLocationAngleRad { get; set; }
    public double? ExplicitLatitudeDeg { get; set; }
}
