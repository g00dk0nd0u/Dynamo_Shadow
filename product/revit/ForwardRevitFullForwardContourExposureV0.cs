using ShadowCore;

namespace RevitShadow;

/// <summary>Preserves whether the post-union contour stage was actually executed.</summary>
public static class ForwardRevitFullForwardContourExposureV0
{
    public static ForwardEqualTimeContourResultV0? Select(
        ForwardShadowDurationResultV0 duration,
        ForwardShadowDurationFieldV0? durationField,
        ForwardEqualTimeContourResultV0 equalTimeContours) =>
        duration.Complete && durationField is not null ? equalTimeContours : null;
}
