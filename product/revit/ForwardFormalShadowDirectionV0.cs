using System;

namespace RevitShadow;

/// <summary>Host-neutral copy of the formal projection direction contract.</summary>
public sealed class ForwardFormalShadowDirectionV0
{
    private ForwardFormalShadowDirectionV0() { }

    public bool Valid { get; private set; }
    public bool ContractPassed { get; private set; }
    public double PhysicalX { get; private set; }
    public double PhysicalY { get; private set; }
    public double PhysicalZ { get; private set; }
    public double AnalyzerX { get; private set; }
    public double AnalyzerY { get; private set; }
    public double AnalyzerZ { get; private set; }
    public double ShadowLengthFactor { get; private set; }
    public string? FailureCode { get; private set; }

    public static ForwardFormalShadowDirectionV0 Create(
        double modelX, double modelY, double shadowLengthFactor, double maximumFactor = 100.0)
    {
        if (!double.IsFinite(modelX) || !double.IsFinite(modelY)
            || !double.IsFinite(shadowLengthFactor) || !double.IsFinite(maximumFactor)
            || shadowLengthFactor <= 0.0)
        {
            return Invalid("invalid_shadow_direction_model_or_factor");
        }
        if (shadowLengthFactor > maximumFactor)
        {
            return Invalid("shadow_length_factor_exceeds_guard");
        }

        var x = modelX * shadowLengthFactor;
        var y = modelY * shadowLengthFactor;
        var length = Math.Sqrt(x * x + y * y + 1.0);
        if (!double.IsFinite(length) || length <= 0.0)
        {
            return Invalid("invalid_shadow_direction_vector");
        }

        x /= length;
        y /= length;
        var z = -1.0 / length;
        var analyzerX = -x;
        var analyzerY = -y;
        var analyzerZ = -z;
        var antiparallel = Math.Abs(x + analyzerX) <= 1e-9
            && Math.Abs(y + analyzerY) <= 1e-9
            && Math.Abs(z + analyzerZ) <= 1e-9;
        var analyticalFactor = Math.Sqrt(x * x + y * y) / Math.Abs(z);
        var contractPassed = z < 0.0 && analyzerZ > 0.0 && antiparallel
            && Math.Abs(analyticalFactor - shadowLengthFactor)
                <= Math.Max(1e-9, Math.Abs(shadowLengthFactor) * 1e-9);
        return new ForwardFormalShadowDirectionV0
        {
            Valid = true,
            ContractPassed = contractPassed,
            PhysicalX = x,
            PhysicalY = y,
            PhysicalZ = z,
            // This is the sole sign conversion: ExtrusionAnalyzer grows from the
            // measurement plane toward the source, opposite the physical ray.
            AnalyzerX = analyzerX,
            AnalyzerY = analyzerY,
            AnalyzerZ = analyzerZ,
            ShadowLengthFactor = shadowLengthFactor,
        };
    }

    private static ForwardFormalShadowDirectionV0 Invalid(string code) => new()
    {
        Valid = false,
        FailureCode = code,
    };
}
