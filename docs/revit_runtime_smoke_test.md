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
