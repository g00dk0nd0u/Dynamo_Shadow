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
