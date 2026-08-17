using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;

namespace RevitShadow;

/// <summary>Formats the JSON-safe Phase 5B diagnostic contract for a compact smoke-test dialog.</summary>
public static class ForwardProjectContextDiagnosticFormatterV0
{
    private static readonly string[] Keys =
    {
        "available",
        "complete",
        "average_ground_level_elevation_m",
        "average_ground_level_source",
        "measurement_height_m",
        "measurement_plane_elevation_m",
        "true_north_deg",
        "latitude_deg",
        "blockers",
        "warnings",
        "permit_ready_certified",
    };

    public static string Format(IReadOnlyDictionary<string, object?> diagnostic) =>
        string.Join(Environment.NewLine, Keys.Select(key => $"{key}: {FormatValue(diagnostic[key])}"));

    private static string FormatValue(object? value) => value switch
    {
        null => "null",
        bool boolean => boolean ? "true" : "false",
        string text => text,
        IEnumerable<string> values => values.Any() ? string.Join(", ", values) : "(none)",
        IFormattable formattable => formattable.ToString(null, CultureInfo.InvariantCulture),
        _ => value.ToString() ?? "null",
    };
}
