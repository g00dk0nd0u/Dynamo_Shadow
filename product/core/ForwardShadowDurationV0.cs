using System;
using System.Collections.Generic;

namespace ShadowCore;

public sealed class ForwardShadowDurationSettingsV0
{
    public double GridResolutionM { get; set; }
    public double AnalysisMarginM { get; set; }
    public int MaxGridPoints { get; set; }
}

public sealed class ForwardShadowDurationResultV0
{
    public bool Available { get; set; }
    public bool Complete { get; set; }
    public string Method => ForwardShadowDurationV0.Method;
    public double? TemporalStepMinutes { get; set; }
    public double SpatialResolutionM { get; set; }
    public int GridPointCount { get; set; }
    public long? RequestedGridPointCount { get; set; }
    public int? ConfiguredMaxGridPoints { get; set; }
    public int DenseHardPointCap { get; set; } = ForwardShadowDurationV0.DenseHardPointCap;
    public double MaximumShadowDurationMinutes { get; set; }
    public int ShadowedPointCount { get; set; }
    public GridSpecV0? GridSpec { get; set; }
    public IReadOnlyList<DurationPointV0> DurationValues { get; set; } = Array.Empty<DurationPointV0>();
    public string StorageMode { get; set; } = string.Empty;
    public bool DurationGridMaterialized { get; set; }
    public IReadOnlyList<string> Blockers { get; set; } = Array.Empty<string>();
    public IReadOnlyList<string> Warnings { get; set; } = Array.Empty<string>();
    public bool ReadyForEqualTimeContourGeneration { get; set; }
    public bool PermitReadyCertified => false;
}

/// <summary>Compact row-major scalar boundary for contour generation.</summary>
public sealed class ForwardShadowDurationFieldV0
{
    public IReadOnlyList<double> Values { get; set; } = Array.Empty<double>();
    public GridSpecV0 GridSpec { get; set; } = new();
    public int LogicalPointCount { get; set; }
}

/// <summary>Materialized duration result paired with its compact scalar field.</summary>
public sealed class ForwardShadowDurationBuildResultV0
{
    public ForwardShadowDurationResultV0 Result { get; set; } = new();
    public ForwardShadowDurationFieldV0? Field { get; set; }
    public string StorageMode { get; set; } = string.Empty;
    public bool DurationGridMaterialized { get; set; }
    public int SmallGridMaterializationLimit { get; set; } = ForwardShadowDurationV0.SmallGridMaterializationLimit;
}

/// <summary>
/// Autodesk-free duration accumulation over complete, already-unified shadow slices.
/// Polygon roles and component indices are consumed exactly as supplied by the snapshot.
/// </summary>
public static class ForwardShadowDurationV0
{
    public const int DenseHardPointCap = 2_000_000;
    public const int SmallGridMaterializationLimit = 250_000;
    public const string MaterializedSmallStorageMode = "materialized_small_v1";
    public const string CompactLargeStorageMode = "compact_large_v1";
    public const string Method = "grid_trapezoidal_time_integration_v1";
    public const string NumericalApproximationWarning =
        "Duration values are a grid/trapezoidal numerical approximation at the configured temporal interval.";

    private sealed class Component
    {
        internal readonly List<IReadOnlyList<Point2M>> Outers = new();
        internal readonly List<IReadOnlyList<Point2M>> Inners = new();
    }

    public static double IntegrateShadowStatesTrapezoidal(
        IReadOnlyList<int> states, IReadOnlyList<double> sampleMinutes)
    {
        if (states is null || sampleMinutes is null || states.Count != sampleMinutes.Count || states.Count < 2)
            throw new ArgumentException("States and sample minutes must have matching lengths of at least two.");
        double duration = 0;
        for (var index = 0; index < states.Count-1; index++)
        {
            var interval = sampleMinutes[index+1]-sampleMinutes[index];
            if (!ForwardGeometryV0.Finite(sampleMinutes[index]) ||
                !ForwardGeometryV0.Finite(sampleMinutes[index+1]) || interval <= 0)
                throw new ArgumentException("Sample minutes must be finite and strictly increasing.");
            duration += interval*(states[index]+states[index+1])/2.0;
        }
        return duration;
    }

    public static bool ContainsShadowPoint(
        IReadOnlyList<ForwardUnifiedShadowPolygonSnapshotV0>? polygons, double x, double y)
    {
        if (polygons is null) return false;
        var components = Compile(polygons);
        foreach (var component in components.Values)
        {
            var inOuter = false;
            foreach (var outer in component.Outers)
                if (InsideLoop(outer, x, y)) { inOuter = true; break; }
            if (!inOuter) continue;
            var inInner = false;
            foreach (var inner in component.Inners)
                if (InsideLoop(inner, x, y)) { inInner = true; break; }
            if (!inInner) return true;
        }
        return false;
    }

    public static ForwardShadowDurationResultV0 Build(
        ForwardUnifiedShadowSliceSnapshotV0? snapshot, ForwardShadowDurationSettingsV0? settings)
        => BuildCore(snapshot, settings, includeField: false).Result;

    public static ForwardShadowDurationBuildResultV0 BuildWithField(
        ForwardUnifiedShadowSliceSnapshotV0? snapshot, ForwardShadowDurationSettingsV0? settings)
        => BuildCore(snapshot, settings, includeField: true);

    public static string SelectFieldStorageMode(long gridPointCount)
    {
        if (gridPointCount < 0) throw new ArgumentOutOfRangeException(nameof(gridPointCount));
        return gridPointCount <= SmallGridMaterializationLimit
            ? MaterializedSmallStorageMode : CompactLargeStorageMode;
    }

    private static ForwardShadowDurationBuildResultV0 BuildCore(
        ForwardUnifiedShadowSliceSnapshotV0? snapshot, ForwardShadowDurationSettingsV0? settings,
        bool includeField)
    {
        var warnings = new List<string>();
        if (snapshot?.Warnings is not null) warnings.AddRange(snapshot.Warnings);
        if (!warnings.Contains(NumericalApproximationWarning)) warnings.Add(NumericalApproximationWarning);
        if (snapshot is null || !snapshot.Complete || snapshot.Slices is null || snapshot.Slices.Count == 0 ||
            HasIncompleteSlice(snapshot.Slices))
            return FailedBuild("complete_unified_shadow_slices_required", warnings);
        if (snapshot.Slices.Count < 2 || !ValidSettings(settings))
            return FailedBuild("invalid_duration_input_or_settings", warnings);

        var times = new List<double>(snapshot.Slices.Count);
        var compiled = new List<Dictionary<int, Component>>(snapshot.Slices.Count);
        var allPoints = new List<Point2M>();
        foreach (var slice in snapshot.Slices)
        {
            if (!ForwardGeometryV0.Finite(slice.TrueSolarMinutes) ||
                (times.Count > 0 && slice.TrueSolarMinutes <= times[times.Count-1]))
                return FailedBuild("invalid_duration_input_or_settings", warnings);
            times.Add(slice.TrueSolarMinutes);
            if (slice.Polygons is null) return FailedBuild("invalid_duration_input_or_settings", warnings);
            foreach (var polygon in slice.Polygons)
            {
                if (!ValidPolygon(polygon)) return FailedBuild("invalid_duration_input_or_settings", warnings);
                allPoints.AddRange(polygon.PointsM);
            }
            compiled.Add(Compile(slice.Polygons));
        }
        if (allPoints.Count == 0) return FailedBuild("invalid_duration_input_or_settings", warnings);

        var resolution = settings!.GridResolutionM;
        var minX = double.PositiveInfinity; var minY = double.PositiveInfinity;
        var maxX = double.NegativeInfinity; var maxY = double.NegativeInfinity;
        foreach (var point in allPoints)
        {
            minX = Math.Min(minX, point.X); minY = Math.Min(minY, point.Y);
            maxX = Math.Max(maxX, point.X); maxY = Math.Max(maxY, point.Y);
        }
        minX -= settings.AnalysisMarginM; minY -= settings.AnalysisMarginM;
        maxX += settings.AnalysisMarginM; maxY += settings.AnalysisMarginM;
        var xCountDouble = Math.Ceiling((maxX-minX)/resolution)+1;
        var yCountDouble = Math.Ceiling((maxY-minY)/resolution)+1;
        if (!ForwardGeometryV0.Finite(xCountDouble) || !ForwardGeometryV0.Finite(yCountDouble) ||
            xCountDouble < 1 || yCountDouble < 1 || xCountDouble > int.MaxValue || yCountDouble > int.MaxValue)
            return FailedBuild("invalid_duration_input_or_settings", warnings);
        var xCount = (int)xCountDouble; var yCount = (int)yCountDouble;
        var count = (long)xCount*yCount;
        if (count > DenseHardPointCap)
            return FailedBuild("large_grid_hard_point_cap_exceeded", warnings, count, settings.MaxGridPoints, resolution);
        if (count > settings.MaxGridPoints)
            return FailedBuild("max_duration_grid_points_exceeded", warnings, count, settings.MaxGridPoints, resolution);

        var materializeDurationValues = !includeField || count <= SmallGridMaterializationLimit;
        var values = materializeDurationValues
            ? new List<DurationPointV0>((int)count) : null;
        var scalarValues = includeField ? new List<double>((int)count) : null;
        double maximum = 0; var shadowed = 0;
        var states = new int[times.Count];
        for (var yIndex = 0; yIndex < yCount; yIndex++)
        for (var xIndex = 0; xIndex < xCount; xIndex++)
        {
            var x = minX+xIndex*resolution; var y = minY+yIndex*resolution;
            for (var sliceIndex = 0; sliceIndex < compiled.Count; sliceIndex++)
                states[sliceIndex] = Contains(compiled[sliceIndex], x, y) ? 1 : 0;
            var duration = IntegrateShadowStatesTrapezoidal(states, times);
            values?.Add(new DurationPointV0 { X = x, Y = y, ShadowDurationMinutes = duration });
            scalarValues?.Add(duration);
            if (duration > 0) shadowed++;
            maximum = Math.Max(maximum, duration);
        }
        var intervals = new double[times.Count-1];
        for (var index = 0; index < intervals.Length; index++) intervals[index] = times[index+1]-times[index];
        var uniform = true;
        for (var index = 1; index < intervals.Length; index++)
            if (Math.Abs(intervals[index]-intervals[0]) > 1e-9) { uniform = false; break; }
        var gridSpec = new GridSpecV0 { OriginXM = minX, OriginYM = minY, ResolutionM = resolution,
            XCount = xCount, YCount = yCount, MaxXM = minX+(xCount-1)*resolution,
            MaxYM = minY+(yCount-1)*resolution };
        var storageMode = includeField ? SelectFieldStorageMode(count) : string.Empty;
        var result = new ForwardShadowDurationResultV0 {
            Available = true, Complete = true, TemporalStepMinutes = uniform ? intervals[0] : null,
            SpatialResolutionM = resolution, GridPointCount = (int)count,
            RequestedGridPointCount = count, ConfiguredMaxGridPoints = settings.MaxGridPoints,
            MaximumShadowDurationMinutes = maximum, ShadowedPointCount = shadowed,
            GridSpec = gridSpec,
            DurationValues = values is null ? Array.Empty<DurationPointV0>() : values, Warnings = warnings,
            StorageMode = storageMode, DurationGridMaterialized = materializeDurationValues,
            ReadyForEqualTimeContourGeneration = true
        };
        return new ForwardShadowDurationBuildResultV0 { Result = result,
            Field = scalarValues is null ? null : new ForwardShadowDurationFieldV0 {
                Values = scalarValues, GridSpec = gridSpec, LogicalPointCount = (int)count },
            StorageMode = result.StorageMode,
            DurationGridMaterialized = result.DurationGridMaterialized };
    }

    private static bool ValidSettings(ForwardShadowDurationSettingsV0? settings) =>
        settings is not null && ForwardGeometryV0.Finite(settings.GridResolutionM) &&
        settings.GridResolutionM > 0 && ForwardGeometryV0.Finite(settings.AnalysisMarginM) &&
        settings.AnalysisMarginM >= 0 && settings.MaxGridPoints > 0;

    private static bool HasIncompleteSlice(IReadOnlyList<ForwardUnifiedShadowTimeSliceSnapshotV0> slices)
    {
        foreach (var slice in slices) if (slice is null || !slice.Complete) return true;
        return false;
    }

    private static bool ValidPolygon(ForwardUnifiedShadowPolygonSnapshotV0? polygon)
    {
        if (polygon?.PointsM is null || polygon.PointsM.Count < 3 ||
            (polygon.Role != "outer" && polygon.Role != "inner") || polygon.ComponentIndex < 0 ||
            !polygon.Closed || polygon.PointCount != polygon.PointsM.Count)
            return false;
        double twiceArea = 0;
        for (var index = 0; index < polygon.PointsM.Count; index++)
        {
            var point = polygon.PointsM[index];
            if (point is null || !ForwardGeometryV0.Finite(point.X) || !ForwardGeometryV0.Finite(point.Y))
                return false;
            var next = polygon.PointsM[(index+1)%polygon.PointsM.Count];
            if (next is null || !ForwardGeometryV0.Finite(next.X) || !ForwardGeometryV0.Finite(next.Y))
                return false;
            twiceArea += point.X*next.Y-next.X*point.Y;
        }
        return ForwardGeometryV0.Finite(twiceArea) && twiceArea != 0.0;
    }

    private static Dictionary<int, Component> Compile(IReadOnlyList<ForwardUnifiedShadowPolygonSnapshotV0> polygons)
    {
        var result = new Dictionary<int, Component>();
        foreach (var polygon in polygons)
        {
            if (!result.TryGetValue(polygon.ComponentIndex, out var component))
            {
                component = new Component(); result.Add(polygon.ComponentIndex, component);
            }
            if (polygon.Role == "outer") component.Outers.Add(polygon.PointsM);
            else if (polygon.Role == "inner") component.Inners.Add(polygon.PointsM);
        }
        return result;
    }

    private static bool Contains(Dictionary<int, Component> components, double x, double y)
    {
        foreach (var component in components.Values)
        {
            var inOuter = false;
            foreach (var outer in component.Outers)
                if (InsideLoop(outer, x, y)) { inOuter = true; break; }
            if (!inOuter) continue;
            var inInner = false;
            foreach (var inner in component.Inners)
                if (InsideLoop(inner, x, y)) { inInner = true; break; }
            if (!inInner) return true;
        }
        return false;
    }

    private static bool InsideLoop(IReadOnlyList<Point2M> points, double x, double y)
    {
        var inside = false;
        for (var index = 0; index < points.Count; index++)
        {
            var a = points[index]; var b = points[(index+1)%points.Count];
            if (ForwardGeometryV0.OnSegment(x, y, a, b)) return true;
            if ((a.Y > y) != (b.Y > y) && x < (b.X-a.X)*(y-a.Y)/(b.Y-a.Y)+a.X) inside = !inside;
        }
        return inside;
    }

    private static ForwardShadowDurationResultV0 Failed(
        string blocker, IReadOnlyList<string> warnings, long? requestedGridPointCount = null,
        int? configuredMaxGridPoints = null, double resolution = 0) => new() {
            Blockers = new[] { blocker }, Warnings = warnings,
            GridPointCount = requestedGridPointCount > int.MaxValue ? int.MaxValue :
                (int)(requestedGridPointCount ?? 0), RequestedGridPointCount = requestedGridPointCount,
            ConfiguredMaxGridPoints = configuredMaxGridPoints, SpatialResolutionM = resolution
        };

    private static ForwardShadowDurationBuildResultV0 FailedBuild(
        string blocker, IReadOnlyList<string> warnings, long? requestedGridPointCount = null,
        int? configuredMaxGridPoints = null, double resolution = 0) => new() {
            Result = Failed(blocker, warnings, requestedGridPointCount, configuredMaxGridPoints, resolution)
        };
}
