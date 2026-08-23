using System;
using System.Collections.Generic;

namespace RevitShadow;

/// <summary>A host-neutral summary of the Phase 5F-A single-slice stage sequence.</summary>
public sealed class ForwardRevitSingleSliceIntegrationSummaryV0
{
    public bool Available { get; private set; }
    public bool Complete { get; private set; }
    public string CompletedStage { get; private set; } = "none";
    public bool ProjectContextComplete { get; private set; }
    public bool CasterExtractionComplete { get; private set; }
    public bool ProjectionComplete { get; private set; }
    public bool UnionComplete { get; private set; }
    public string? BlockerStage { get; private set; }
    public IReadOnlyList<string> Blockers { get; private set; } = Array.Empty<string>();
    public IReadOnlyList<string> Warnings { get; private set; } = Array.Empty<string>();
    public bool PermitReadyCertified => false;

    public static ForwardRevitSingleSliceIntegrationSummaryV0 Create(
        ForwardRevitProjectContextResultV0 projectContext,
        ForwardRevitCasterGeometrySummaryV0? casterExtraction = null,
        ForwardRevitFormalShadowSummaryV0? projection = null,
        ForwardRevitFormalShadowUnionSummaryV0? union = null,
        string? boundaryBlocker = null)
    {
        if (projectContext is null) throw new ArgumentNullException(nameof(projectContext));

        var blockers = new List<string>();
        var warnings = new List<string>(projectContext.Warnings);
        var completedStage = "none";
        string? blockerStage = null;

        if (!projectContext.Complete)
        {
            blockers.AddRange(projectContext.Blockers);
            blockerStage = "project_context";
        }
        else
        {
            completedStage = "project_context";
            if (casterExtraction is null)
            {
                if (boundaryBlocker is not null) blockers.Add(boundaryBlocker);
                blockerStage = "caster_extraction";
            }
            else
            {
                warnings.AddRange(casterExtraction.Warnings);
                if (!casterExtraction.Complete)
                {
                    blockers.AddRange(casterExtraction.Blockers);
                    blockerStage = "caster_extraction";
                }
                else
                {
                    completedStage = "caster_extraction";
                    if (projection is null)
                    {
                        if (boundaryBlocker is not null) blockers.Add(boundaryBlocker);
                        blockerStage = "projection";
                    }
                    else
                    {
                        warnings.AddRange(projection.Warnings);
                        if (!projection.Complete)
                        {
                            blockers.AddRange(projection.Blockers);
                            blockerStage = "projection";
                        }
                        else
                        {
                            completedStage = "projection";
                            if (union is null)
                            {
                                if (boundaryBlocker is not null) blockers.Add(boundaryBlocker);
                                blockerStage = "union";
                            }
                            else
                            {
                                warnings.AddRange(union.Warnings);
                                if (!union.Complete)
                                {
                                    blockers.AddRange(union.Blockers);
                                    blockerStage = "union";
                                }
                                else completedStage = "union";
                            }
                        }
                    }
                }
            }
        }

        var complete = union?.Complete == true && blockerStage is null;
        return new ForwardRevitSingleSliceIntegrationSummaryV0
        {
            Available = union?.Available == true,
            Complete = complete,
            CompletedStage = completedStage,
            ProjectContextComplete = projectContext.Complete,
            CasterExtractionComplete = casterExtraction?.Complete == true,
            ProjectionComplete = projection?.Complete == true,
            UnionComplete = union?.Complete == true,
            BlockerStage = blockerStage,
            Blockers = blockers,
            Warnings = warnings,
        };
    }
}
