# Revit Runtime Smoke Test

Run this checklist before treating the current technical prototypes as validated. This repository is not permit-certified.

## Environment

- Revit 2024.3
- Dynamo 3.3
- CPython3
- A simple Mass or Generic Model shadow caster

## Player UI

Confirm that:

- the settings JSON is not displayed in Dynamo Player;
- **Regulatory Shadow Preset** is displayed;
- **Site Latitude** is displayed as a Number input; and
- **Site Longitude** is displayed as a Number input.

## Preset tests

### `standard_all`

- Generated levels are `[120, 150, 180, 240, 300]` minutes.
- Five equal-time contour DirectShape levels are created.

### `standard_4_2_5`

- Generated levels are `[150, 240]` minutes.
- Two equal-time contour DirectShape levels are created.

### `hokkaido_2_1_5`

- The selected profile is `hokkaido_9_15`.
- Generated levels are `[90, 120]` minutes.
- The calculation window is 09:00–15:00 true solar time.

## Preview tests

Confirm that:

- rerunning in `replace` mode does not increase the number of owned elements;
- the time-shadow preview and equal-time contour preview coexist;
- `clear` deletes only elements with the preview's target `ApplicationId`;
- `blockers` is empty;
- `success` is `true`; and
- `permit_ready_certified` remains `false`.

## Known warning

When the Plan representation is unavailable, preview creation falls back to the DirectShape Default Curve representation. Record the warning and visually verify the fallback; it does not certify calculation correctness.

## Site Boundary Area distance mask smoke tests / 敷地境界エリア距離マスク実機確認

Preparation: create a dedicated Area Scheme (`Shadow Analysis / 日影検討`), an Area Plan at the site level, a roughly 20m x 20m rectangular Area with four straight Area Boundary segments, and place the Area.

- Test A valid rectangle: select the Area body once; expect `site_boundary_area_extraction.complete=true`, `site_boundary_geometry.complete=true`, `vertex_count=4`, polygon `area_m2` roughly matching Revit Area, `measurement_masks.complete=true`, non-negative near/far counts, and `legal_judgement_generated=false`.
- Test B no Area selected: `None` site_boundary should allow shadow duration and equal-time contours to continue; `measurement_masks.available=false` and no fatal failure.
- Test C unbounded Area: expect `site_boundary_area_unplaced_or_unbounded` or `site_boundary_area_boundary_missing`; core shadow calculation continues.
- Test D curved boundary: expect `unsupported_site_boundary_curve_type`; endpoints are not silently straightened; core shadow calculation continues.
- Test E Area with opening / inner loop: expect `site_boundary_area_multiple_loops_unsupported`; the largest loop is not adopted automatically.
- Test F duration bounds: Area bounds expanded by 10m are included in duration bounds; outside-site shadows remain; equal-time contours are not clipped by the Area.

Player optional-input check: because `Site Boundary Area / 敷地境界エリア` is a `hostSelection` Player input, confirm in Revit whether Run remains enabled when it is unselected. If Run is disabled, record that Dynamo Player requires Area selection for this UI while Python still handles `None` as optional for API/test execution; do not add dummy ElementIds.

## Site result preview v1 pending checks

These checks require a real Revit 2024.3 + Dynamo 3.3 runtime and are not a PR creation prerequisite.

A. `replace`
- Confirm one 5 m SiteResultPreview distance group is displayed.
- Confirm one 10 m SiteResultPreview distance group is displayed.
- Confirm the near maximum-duration X marker is displayed.
- Confirm the far maximum-duration X marker is displayed.

B. Rerun
- Confirm repeated runs do not multiply the same SiteResultPreview elements.
- Confirm only previous `Dynamo_Shadow.SiteResultPreview` elements are replaced.

C. Ownership
- Confirm equal-time contour preview elements are not deleted.
- Confirm formal shadow preview elements are not deleted.

D. `clear`
- Confirm SiteResultPreview elements are deleted.
- Confirm the source Area and source building elements are not deleted.

E. All preset
- Confirm near and far markers are displayed.
- Confirm selected-limit status remains `undetermined`.
- Confirm the preview does not fail because comparison status is undetermined.

F. No Area selected
- Confirm core shadow calculation continues.
- Confirm site result preview is skipped.
- Confirm old SiteResultPreview elements are not accidentally deleted.

## Self-contained renamed bundle smoke test (pending)

These checks are required before or after merge on Revit 2024.3 with Dynamo 3.3, but are not a PR creation prerequisite. The verification has not yet been performed.

1. Run the repository copy at `runtime/Shadow.dyn`.
2. Copy the complete `runtime/` directory to another location.
3. Rename the copied directory to `日影図 社内試用版`.
4. Run the renamed copy's `Shadow.dyn` from Dynamo Player.
5. Confirm no `script.py not found` error is reported.
6. Confirm no local shadow-module import error is reported.
7. Confirm the forward-shadow calculation completes as before.
8. Confirm equal-time contours are displayed.
9. Confirm the 5 m and 10 m contours are displayed.
10. Confirm the near and far maximum-point markers are displayed.
11. Rerun and confirm preview elements do not multiply.

Record the Revit machine, Dynamo version, model, results, and any warnings separately. Until that record exists, Revit runtime verification remains pending.
