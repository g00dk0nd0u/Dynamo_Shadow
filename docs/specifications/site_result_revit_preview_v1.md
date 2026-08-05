# Site result Revit preview v1

This specification describes an optional Revit Adapter preview stage for existing site result outputs.

## Scope

The preview displays only existing core output data:

- `site_distance_contours.contours` for the fixed 5 m and 10 m distance contours.
- `measurement_masks.near.point` and `measurement_masks.far.point` for maximum-duration locations.

The preview does not recalculate distance contours, maximum points, shadow durations, selected limits, or any legal judgement.

## Mode

No new Dynamo Player input or settings key is added. The stage reuses `equal_time_contour_preview_mode`:

- `off`: do not access Revit API, create elements, or delete elements.
- `replace`: delete only elements owned by `Dynamo_Shadow.SiteResultPreview`, then create new preview curves.
- `clear`: delete only elements owned by `Dynamo_Shadow.SiteResultPreview`; source outputs and measurement plane are not required.

## Ownership

Preview elements use `DirectShape.ApplicationId == "Dynamo_Shadow.SiteResultPreview"`. Cleanup uses exact ApplicationId ownership and must not delete formal shadow previews, equal-time contour previews, user Generic Models, other DirectShapes, source Areas, or source building elements.

## Geometry

All geometry is `Autodesk.Revit.DB.DirectShape` Curve geometry in `OST_GenericModel`.

- 5 m contours are grouped into one DirectShape named `Dynamo_Shadow_SiteDistance_05m`.
- 10 m contours are grouped into one DirectShape named `Dynamo_Shadow_SiteDistance_10m`.
- Multiple polylines for the same distance are combined into that distance's DirectShape.
- Existing `points_m` are used as-is: no smoothing, splines, offsets, corner rounding, or coordinate re-rounding.
- Closed contours receive a closing segment.
- Zero-length and Revit short-tolerance segments are excluded.

Near and far maximum-duration points are displayed as X markers:

- Names: `Dynamo_Shadow_MaxPoint_Near` and `Dynamo_Shadow_MaxPoint_Far`.
- Each marker has two diagonal Line curves.
- `MARKER_HALF_SIZE_M = 0.5`, so the marker is 1 m across.
- Metadata may include zone, maximum duration, selected-limit status, selected limit minutes, and excess minutes.

All curves are placed exactly on `measurement_plane.elevation_m` with no vertical offset.

## Styling semantics

Colors and line weights distinguish output kinds only. They do not indicate legal pass/fail, compliance, or non-compliance. This version intentionally does not implement red/green selected-limit exceedance styling.

## Not implemented

This preview does not create labels, TextNotes, dimensions, Filled Regions, reports, legal OK/NG results, ordinance certification, permit certification, reverse shadow outputs, or a C# add-in.
