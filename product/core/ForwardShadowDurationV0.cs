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
    public ForwardShadowDurationEngineDiagnosticsV0? EngineDiagnostics { get; set; }
    public bool PermitReadyCertified => false;
}

/// <summary>Compact row-major scalar boundary for contour generation.</summary>
public sealed class ForwardShadowDurationFieldV0
{
    public IReadOnlyList<double> Values { get; set; } = Array.Empty<double>();
    public GridSpecV0 GridSpec { get; set; } = new();
    public int LogicalPointCount { get; set; }
    public ForwardShadowDurationActiveTileMetadataV0? ActiveTileMetadata { get; set; }
}

public sealed class ForwardShadowDurationExecutionOptionsV0
{
    public bool SparseTiles { get; set; } = true;
    public bool BboxPruning { get; set; } = true;
    public int TileSizeCells { get; set; } = ForwardShadowDurationV0.DefaultTileSizeCells;
    public long? AvailablePhysicalMemoryBytes { get; set; }
}

public sealed class ForwardShadowDurationTileV0
{
    public int TileX { get; set; }
    public int TileY { get; set; }
}

public sealed class ForwardShadowDurationActiveTileMetadataV0
{
    public int TileSizeCells { get; set; }
    public IReadOnlyList<ForwardShadowDurationTileV0> ActiveTiles { get; set; } = Array.Empty<ForwardShadowDurationTileV0>();
    public long ActiveEvaluationPointCount { get; set; }
}

public sealed class ForwardShadowDurationEngineDiagnosticsV0
{
    public string Engine { get; set; } = ForwardShadowDurationV0.Engine;
    public string LargeGridPreflightStatus { get; set; } = string.Empty;
    public long EstimatedWorkingMemoryBytes { get; set; }
    public long MemoryBudgetBytes { get; set; }
    public long EstimatedWork { get; set; }
    public long LargeGridHardWorkCap { get; set; } = ForwardShadowDurationV0.LargeGridHardWorkCap;
    public long ActiveEvaluationPointCount { get; set; }
    public long ImplicitZeroPointCount { get; set; }
    public int TileSizeCells { get; set; }
    public long TotalLogicalTileCount { get; set; }
    public int SelectedActiveTileCount { get; set; }
    public long SkippedTileCount { get; set; }
    public bool BboxPruningEnabled { get; set; }
    public long BboxRejectCount { get; set; }
    public long ContainmentEvaluationCount { get; set; }
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
    public const int DefaultTileSizeCells = 32;
    public const long LargeGridHardWorkCap = 100_000_000;
    public const long LargeGridFallbackMemoryBudgetBytes = 64L * 1024 * 1024;
    public const double BoundaryEpsilonM = 1e-9;
    public const string Engine = "safe_duration_engine_v2_a";
    public const string MaterializedSmallStorageMode = "materialized_small_v1";
    public const string CompactLargeStorageMode = "compact_large_v1";
    public const string Method = "grid_trapezoidal_time_integration_v1";
    public const string NumericalApproximationWarning =
        "Duration values are a grid/trapezoidal numerical approximation at the configured temporal interval.";

    private readonly struct Bounds
    {
        internal Bounds(double minX, double minY, double maxX, double maxY)
        { MinX=minX; MinY=minY; MaxX=maxX; MaxY=maxY; }
        internal double MinX { get; } internal double MinY { get; }
        internal double MaxX { get; } internal double MaxY { get; }
        internal bool Contains(double x,double y) => MinX<=x && x<=MaxX && MinY<=y && y<=MaxY;
    }
    private sealed class CompiledLoop
    {
        internal CompiledLoop(IReadOnlyList<Point2M> points)
        {
            Points=points; var minX=double.PositiveInfinity;var minY=double.PositiveInfinity;
            var maxX=double.NegativeInfinity;var maxY=double.NegativeInfinity;
            foreach(var p in points){minX=Math.Min(minX,p.X);minY=Math.Min(minY,p.Y);maxX=Math.Max(maxX,p.X);maxY=Math.Max(maxY,p.Y);}
            Bounds=new Bounds(minX-BoundaryEpsilonM,minY-BoundaryEpsilonM,maxX+BoundaryEpsilonM,maxY+BoundaryEpsilonM);
        }
        internal IReadOnlyList<Point2M> Points { get; }
        internal Bounds Bounds { get; }
    }
    private sealed class Component
    {
        internal readonly List<CompiledLoop> Outers = new();
        internal readonly List<CompiledLoop> Inners = new();
    }
    private sealed class ActiveTilePlan
    {
        internal ActiveTilePlan(int xCount, int yCount, long totalCount, bool allSelected, ulong[]? selected)
        { XCount=xCount; YCount=yCount; TotalCount=totalCount; AllSelected=allSelected; Selected=selected; }
        internal int XCount { get; }
        internal int YCount { get; }
        internal long TotalCount { get; }
        internal bool AllSelected { get; }
        internal ulong[]? Selected { get; }
        internal int SelectedCount { get; set; }
        internal long ActivePointCount { get; set; }
        internal bool IsSelected(long id) => AllSelected || (Selected![(int)(id >> 6)] & (1UL << (int)(id & 63))) != 0;
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
        return Contains(components,x,y);
    }

    public static ForwardShadowDurationResultV0 Build(
        ForwardUnifiedShadowSliceSnapshotV0? snapshot, ForwardShadowDurationSettingsV0? settings)
        => BuildCore(snapshot, settings, includeField: false).Result;

    public static ForwardShadowDurationBuildResultV0 BuildWithField(
        ForwardUnifiedShadowSliceSnapshotV0? snapshot, ForwardShadowDurationSettingsV0? settings)
        => BuildWithField(snapshot, settings, new ForwardShadowDurationExecutionOptionsV0());

    public static ForwardShadowDurationBuildResultV0 BuildWithField(
        ForwardUnifiedShadowSliceSnapshotV0? snapshot, ForwardShadowDurationSettingsV0? settings,
        ForwardShadowDurationExecutionOptionsV0? options)
        => BuildCore(snapshot, settings, includeField: true, options ?? new ForwardShadowDurationExecutionOptionsV0());

    public static string SelectFieldStorageMode(long gridPointCount)
    {
        if (gridPointCount < 0) throw new ArgumentOutOfRangeException(nameof(gridPointCount));
        return gridPointCount <= SmallGridMaterializationLimit
            ? MaterializedSmallStorageMode : CompactLargeStorageMode;
    }

    private static ForwardShadowDurationBuildResultV0 BuildCore(
        ForwardUnifiedShadowSliceSnapshotV0? snapshot, ForwardShadowDurationSettingsV0? settings,
        bool includeField, ForwardShadowDurationExecutionOptionsV0? executionOptions = null)
    {
        var warnings = new List<string>();
        if (snapshot?.Warnings is not null) warnings.AddRange(snapshot.Warnings);
        if (!warnings.Contains(NumericalApproximationWarning)) warnings.Add(NumericalApproximationWarning);
        if (snapshot is null || !snapshot.Complete || snapshot.Slices is null || snapshot.Slices.Count == 0 ||
            HasIncompleteSlice(snapshot.Slices))
            return FailedBuild("complete_unified_shadow_slices_required", warnings);
        if (snapshot.Slices.Count < 2 || !ValidSettings(settings))
            return FailedBuild("invalid_duration_input_or_settings", warnings);
        if (includeField && (executionOptions is null || executionOptions.TileSizeCells <= 0 ||
            executionOptions.AvailablePhysicalMemoryBytes < 0))
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

        var gridSpec = new GridSpecV0 { OriginXM = minX, OriginYM = minY, ResolutionM = resolution,
            XCount = xCount, YCount = yCount, MaxXM = minX+(xCount-1)*resolution,
            MaxYM = minY+(yCount-1)*resolution };
        var activeTilePlan = includeField ? PlanActiveTiles(compiled, gridSpec, executionOptions!) : null;
        var activeCount = includeField ? activeTilePlan!.ActivePointCount : count;
        var diagnostics = includeField ? CreateDiagnostics(count, activeCount, activeTilePlan!,
            snapshot.Slices.Count, executionOptions!) : null;
        if (includeField && count > SmallGridMaterializationLimit)
        {
            if (diagnostics!.EstimatedWorkingMemoryBytes > diagnostics.MemoryBudgetBytes)
            {
                diagnostics.LargeGridPreflightStatus="blocked_memory";
                return FailedBuild("large_grid_memory_budget_exceeded", warnings, count,
                    settings.MaxGridPoints, resolution, diagnostics);
            }
            if (diagnostics.EstimatedWork > LargeGridHardWorkCap)
            {
                diagnostics.LargeGridPreflightStatus="blocked_work";
                return FailedBuild("large_grid_work_budget_exceeded", warnings, count,
                    settings.MaxGridPoints, resolution, diagnostics);
            }
        }
        var activeTiles = includeField ? MaterializeActiveTiles(activeTilePlan!) : null;
        var materializeDurationValues = !includeField || count <= SmallGridMaterializationLimit;
        var values = materializeDurationValues
            ? new List<DurationPointV0>((int)count) : null;
        var scalarValues = includeField ? new double[(int)count] : null;
        double maximum = 0; var shadowed = 0;
        var states = new int[times.Count];
        IEnumerable<ForwardShadowDurationTileV0> tiles = includeField ? activeTiles! :
            new[]{new ForwardShadowDurationTileV0{TileX=0,TileY=0}};
        var tileSize = includeField ? executionOptions!.TileSizeCells : Math.Max(xCount,yCount);
        foreach(var tile in tiles)
        for (var yIndex = TileStart(tile.TileY,tileSize); yIndex < TileEnd(tile.TileY,tileSize,yCount); yIndex++)
        for (var xIndex = TileStart(tile.TileX,tileSize); xIndex < TileEnd(tile.TileX,tileSize,xCount); xIndex++)
        {
            var x = minX+xIndex*resolution; var y = minY+yIndex*resolution;
            for (var sliceIndex = 0; sliceIndex < compiled.Count; sliceIndex++)
                states[sliceIndex] = Contains(compiled[sliceIndex], x, y,
                    includeField && executionOptions!.BboxPruning, diagnostics) ? 1 : 0;
            var duration = IntegrateShadowStatesTrapezoidal(states, times);
            if(!includeField) values?.Add(new DurationPointV0 { X = x, Y = y, ShadowDurationMinutes = duration });
            if(scalarValues is not null) scalarValues[yIndex*xCount+xIndex]=duration;
            if (duration > 0) shadowed++;
            maximum = Math.Max(maximum, duration);
        }
        if(includeField && values is not null && scalarValues is not null)
            for(var yIndex=0;yIndex<yCount;yIndex++)for(var xIndex=0;xIndex<xCount;xIndex++)
                values.Add(new DurationPointV0{X=minX+xIndex*resolution,Y=minY+yIndex*resolution,
                    ShadowDurationMinutes=scalarValues[yIndex*xCount+xIndex]});
        var intervals = new double[times.Count-1];
        for (var index = 0; index < intervals.Length; index++) intervals[index] = times[index+1]-times[index];
        var uniform = true;
        for (var index = 1; index < intervals.Length; index++)
            if (Math.Abs(intervals[index]-intervals[0]) > 1e-9) { uniform = false; break; }
        var storageMode = includeField ? SelectFieldStorageMode(count) : string.Empty;
        var result = new ForwardShadowDurationResultV0 {
            Available = true, Complete = true, TemporalStepMinutes = uniform ? intervals[0] : null,
            SpatialResolutionM = resolution, GridPointCount = (int)count,
            RequestedGridPointCount = count, ConfiguredMaxGridPoints = settings.MaxGridPoints,
            MaximumShadowDurationMinutes = maximum, ShadowedPointCount = shadowed,
            GridSpec = gridSpec,
            DurationValues = values is null ? Array.Empty<DurationPointV0>() : values, Warnings = warnings,
            StorageMode = storageMode, DurationGridMaterialized = materializeDurationValues,
            ReadyForEqualTimeContourGeneration = true, EngineDiagnostics=diagnostics
        };
        return new ForwardShadowDurationBuildResultV0 { Result = result,
            Field = scalarValues is null ? null : new ForwardShadowDurationFieldV0 {
                Values = scalarValues, GridSpec = gridSpec, LogicalPointCount = (int)count,
                ActiveTileMetadata = new ForwardShadowDurationActiveTileMetadataV0 {
                    TileSizeCells=executionOptions!.TileSizeCells,ActiveTiles=activeTiles!,
                    ActiveEvaluationPointCount=activeCount} },
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
            if (polygon.Role == "outer") component.Outers.Add(new CompiledLoop(polygon.PointsM));
            else if (polygon.Role == "inner") component.Inners.Add(new CompiledLoop(polygon.PointsM));
        }
        return result;
    }

    private static bool Contains(Dictionary<int, Component> components, double x, double y,
        bool bboxPruning=false, ForwardShadowDurationEngineDiagnosticsV0? diagnostics=null)
    {
        foreach (var component in components.Values)
        {
            var inOuter = false;
            foreach (var outer in component.Outers)
            {
                if(bboxPruning && !outer.Bounds.Contains(x,y)){if(diagnostics is not null)diagnostics.BboxRejectCount++;continue;}
                if(diagnostics is not null)diagnostics.ContainmentEvaluationCount++;
                if (InsideLoop(outer.Points, x, y)) { inOuter = true; break; }
            }
            if (!inOuter) continue;
            var inInner = false;
            foreach (var inner in component.Inners)
            {
                if(bboxPruning && !inner.Bounds.Contains(x,y)){if(diagnostics is not null)diagnostics.BboxRejectCount++;continue;}
                if(diagnostics is not null)diagnostics.ContainmentEvaluationCount++;
                if (InsideLoop(inner.Points, x, y)) { inInner = true; break; }
            }
            if (!inInner) return true;
        }
        return false;
    }

    private static ActiveTilePlan PlanActiveTiles(
        IReadOnlyList<Dictionary<int,Component>> slices, GridSpecV0 grid,
        ForwardShadowDurationExecutionOptionsV0 options)
    {
        var txCount=CeilingDivide(grid.XCount,options.TileSizeCells);
        var tyCount=CeilingDivide(grid.YCount,options.TileSizeCells);
        var totalCount=checked((long)txCount*tyCount);
        var plan=new ActiveTilePlan(txCount,tyCount,totalCount,!options.SparseTiles,
            options.SparseTiles ? new ulong[checked((int)((totalCount+63)/64))] : null);
        if(!options.SparseTiles)
        {
            plan.SelectedCount=checked((int)totalCount);
            plan.ActivePointCount=(long)grid.XCount*grid.YCount;
        }
        else foreach(var slice in slices)foreach(var component in slice.Values)
            foreach(var loop in EnumerateLoops(component))
            {
                var ix0=Math.Max(0,(int)Math.Floor((loop.Bounds.MinX-grid.OriginXM)/grid.ResolutionM));
                var iy0=Math.Max(0,(int)Math.Floor((loop.Bounds.MinY-grid.OriginYM)/grid.ResolutionM));
                var ix1=Math.Min(grid.XCount-1,(int)Math.Ceiling((loop.Bounds.MaxX-grid.OriginXM)/grid.ResolutionM));
                var iy1=Math.Min(grid.YCount-1,(int)Math.Ceiling((loop.Bounds.MaxY-grid.OriginYM)/grid.ResolutionM));
                if(ix0>ix1||iy0>iy1)continue;
                for(var ty=iy0/options.TileSizeCells;ty<=iy1/options.TileSizeCells;ty++)
                for(var tx=ix0/options.TileSizeCells;tx<=ix1/options.TileSizeCells;tx++)
                    SelectTile(plan,tx,ty,grid,options.TileSizeCells);
            }
        return plan;
    }

    private static void SelectTile(ActiveTilePlan plan,int tx,int ty,GridSpecV0 grid,int size)
    {
        var id=(long)ty*plan.XCount+tx;
        var word=(int)(id >> 6);var mask=1UL << (int)(id & 63);
        if((plan.Selected![word]&mask)!=0)return;
        plan.Selected[word]|=mask;plan.SelectedCount++;
        plan.ActivePointCount+=(long)(TileEnd(tx,size,grid.XCount)-TileStart(tx,size))*
            (TileEnd(ty,size,grid.YCount)-TileStart(ty,size));
    }

    private static List<ForwardShadowDurationTileV0> MaterializeActiveTiles(ActiveTilePlan plan)
    {
        var result=new List<ForwardShadowDurationTileV0>(plan.SelectedCount);
        for(long id=0;id<plan.TotalCount;id++)if(plan.IsSelected(id))
            result.Add(new ForwardShadowDurationTileV0{TileX=(int)(id%plan.XCount),TileY=(int)(id/plan.XCount)});
        return result;
    }

    private static IEnumerable<CompiledLoop> EnumerateLoops(Component component)
    { foreach(var loop in component.Outers)yield return loop;foreach(var loop in component.Inners)yield return loop; }

    private static int CeilingDivide(int value,int divisor) => checked((int)(((long)value+divisor-1)/divisor));
    private static int TileStart(int index,int size) => checked((int)((long)index*size));
    private static int TileEnd(int index,int size,int limit) => (int)Math.Min(limit,((long)index+1)*size);

    public static ForwardShadowDurationEngineDiagnosticsV0 PlanResourcePreflight(
        long logicalGridPointCount,long activeEvaluationPointCount,int selectedActiveTileCount,
        long totalLogicalTileCount,int sliceCount,int tileSizeCells,long? availablePhysicalMemoryBytes,
        bool largeGrid)
    {
        if(logicalGridPointCount<0||activeEvaluationPointCount<0||activeEvaluationPointCount>logicalGridPointCount||selectedActiveTileCount<0||
            totalLogicalTileCount<0||sliceCount<0||tileSizeCells<=0||availablePhysicalMemoryBytes<0)
            throw new ArgumentOutOfRangeException();
        var compact=checked(logicalGridPointCount*8L);
        var estimatedMemory=checked(checked(compact+activeEvaluationPointCount/8)+checked((long)selectedActiveTileCount*32));
        var work=checked(activeEvaluationPointCount*(long)sliceCount);
        var budget=availablePhysicalMemoryBytes.HasValue?
            Math.Min(LargeGridFallbackMemoryBudgetBytes,(long)Math.Floor(availablePhysicalMemoryBytes.Value*.25)):
            LargeGridFallbackMemoryBudgetBytes;
        var status=!largeGrid?"not_required_small":estimatedMemory>budget?"blocked_memory":
            work>LargeGridHardWorkCap?"blocked_work":"passed";
        return new ForwardShadowDurationEngineDiagnosticsV0{
            LargeGridPreflightStatus=status,
            EstimatedWorkingMemoryBytes=estimatedMemory,MemoryBudgetBytes=budget,EstimatedWork=work,
            ActiveEvaluationPointCount=activeEvaluationPointCount,
            ImplicitZeroPointCount=logicalGridPointCount-activeEvaluationPointCount,TileSizeCells=tileSizeCells,
            TotalLogicalTileCount=totalLogicalTileCount,SelectedActiveTileCount=selectedActiveTileCount,
            SkippedTileCount=totalLogicalTileCount-selectedActiveTileCount};
    }

    private static ForwardShadowDurationEngineDiagnosticsV0 CreateDiagnostics(long logical,long active,ActiveTilePlan plan,
        int sliceCount,ForwardShadowDurationExecutionOptionsV0 options)
    {
        var d=PlanResourcePreflight(logical,active,plan.SelectedCount,plan.TotalCount,sliceCount,
            options.TileSizeCells,options.AvailablePhysicalMemoryBytes,logical>SmallGridMaterializationLimit);
        d.BboxPruningEnabled=options.BboxPruning;return d;
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
        int? configuredMaxGridPoints = null, double resolution = 0,
        ForwardShadowDurationEngineDiagnosticsV0? diagnostics=null)
    {
        var result=Failed(blocker,warnings,requestedGridPointCount,configuredMaxGridPoints,resolution);
        result.EngineDiagnostics=diagnostics;
        return new ForwardShadowDurationBuildResultV0{Result=result,Field=null};
    }
}
