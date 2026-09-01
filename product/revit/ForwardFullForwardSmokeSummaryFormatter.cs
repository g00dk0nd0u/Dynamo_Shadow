using System;
using System.Collections.Generic;
using System.Linq;

namespace RevitShadow;

/// <summary>Autodesk-free compact formatter for the development Full Forward smoke command.</summary>
public static class ForwardFullForwardSmokeSummaryFormatter
{
    public static string Format(ForwardRevitFullForwardSummaryV0 summary)
    {
        if (summary is null) throw new ArgumentNullException(nameof(summary));

        return string.Join(Environment.NewLine, new[]
        {
            $"available: {Bool(summary.Available)}",
            $"complete: {Bool(summary.Complete)}",
            $"final completed stage: {summary.FinalCompletedStage}",
            $"blocker stage: {summary.BlockerStage ?? "none"}",
            $"duration grid point count: {summary.DurationGridPointCount}",
            $"contour count: {summary.ContourCount}",
            $"blockers: {Join(summary.Blockers)}",
            $"warnings: {Join(summary.Warnings.Select(FormatWarning))}",
            $"permit_ready_certified = {Bool(summary.PermitReadyCertified)}"
        });
    }

    private static string FormatWarning(ForwardRevitStageWarningV0 warning) =>
        warning.SampleIndex.HasValue
            ? $"{warning.Stage}[{warning.SampleIndex.Value}]:{warning.Code}"
            : $"{warning.Stage}:{warning.Code}";

    private static string Join(IEnumerable<string> values)
    {
        var items = values.ToArray();
        return items.Length == 0 ? "none" : string.Join(", ", items);
    }

    private static string Bool(bool value) => value ? "true" : "false";
}
