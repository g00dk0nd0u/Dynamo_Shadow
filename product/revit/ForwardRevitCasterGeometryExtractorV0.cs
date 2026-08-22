#if REVIT_API
using System;
using System.Collections.Generic;
using Autodesk.Revit.DB;

namespace RevitShadow;

/// <summary>
/// Read-only native geometry boundary for already-resolved Mass and Generic Model elements.
/// </summary>
public static class ForwardRevitCasterGeometryExtractorV0
{
    public static ForwardRevitCasterGeometryResultV0 Extract(IEnumerable<Element>? elements)
    {
        var solids = new List<Solid>();
        var warnings = new List<string>();
        var inputCount = 0;
        var supportedCount = 0;
        var instanceCount = 0;
        var ignoredCount = 0;
        var meshEncountered = false;

        if (elements is not null)
        {
            foreach (var element in elements)
            {
                inputCount++;
                if (element is null || !IsSupportedCaster(element))
                {
                    continue;
                }

                supportedCount++;
                try
                {
                    // No View is assigned, references and non-visible objects are not requested.
                    // Fine detail is explicit so extraction is deterministic and not active-view-dependent.
                    var options = new Options
                    {
                        ComputeReferences = false,
                        IncludeNonVisibleObjects = false,
                        DetailLevel = ViewDetailLevel.Fine,
                    };
                    var geometry = element.get_Geometry(options);
                    if (geometry is null)
                    {
                        warnings.Add("caster_element_geometry_unavailable");
                        continue;
                    }

                    Traverse(geometry, solids, ref instanceCount, ref ignoredCount, ref meshEncountered);
                }
                catch (Exception)
                {
                    // One malformed element must not prevent other supported casters from being read.
                    warnings.Add("caster_element_geometry_read_failed");
                }
            }
        }

        if (meshEncountered)
        {
            warnings.Add("mesh_geometry_ignored");
        }

        var summary = ForwardRevitCasterGeometrySummaryV0.Create(
            inputCount, supportedCount, solids.Count, instanceCount, ignoredCount, warnings);
        return new ForwardRevitCasterGeometryResultV0(solids, summary);
    }

    private static bool IsSupportedCaster(Element element)
    {
        var category = element.Category;
        if (category is null)
        {
            return false;
        }

        var categoryId = category.Id.Value;
        return categoryId == (long)BuiltInCategory.OST_Mass
            || categoryId == (long)BuiltInCategory.OST_GenericModel;
    }

    private static void Traverse(
        GeometryElement geometry,
        List<Solid> solids,
        ref int instanceCount,
        ref int ignoredCount,
        ref bool meshEncountered)
    {
        foreach (var geometryObject in geometry)
        {
            if (geometryObject is Solid solid)
            {
                // Structural native geometry is required; volume alone can be fragile for invalid solids.
                if (solid.Faces.Size > 0 && solid.Edges.Size > 0)
                {
                    solids.Add(solid);
                }
                else
                {
                    ignoredCount++;
                }
            }
            else if (geometryObject is GeometryInstance instance)
            {
                instanceCount++;
                // GetInstanceGeometry returns model-coordinate copies. Recurse only this path and do not
                // also inspect symbol geometry or manually reapply the instance transform.
                var instanceGeometry = instance.GetInstanceGeometry();
                if (instanceGeometry is null)
                {
                    ignoredCount++;
                }
                else
                {
                    Traverse(instanceGeometry, solids, ref instanceCount, ref ignoredCount, ref meshEncountered);
                }
            }
            else
            {
                ignoredCount++;
                meshEncountered |= geometryObject is Mesh;
            }
        }
    }
}
#endif
