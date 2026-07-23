# Research: Japanese shadow diagram time and solar position assumptions

## Purpose

This note records time-reference and solar-position assumptions before implementing true solar time, sun vectors, shadow projection, or equal-time shadow contours in this repository.
It is a research note only; it does not define permit-ready calculation behavior.

## Public references checked

- Setagaya City, `4-10 日影規制のあらまし` states that regulated shadows are evaluated on the winter solstice from 8:00 to 16:00 in true solar time, and explains true solar time as a time basis where solar noon is 12:00. It also notes that central standard time differs from this, and that Tokyo solar noon is about 20 minutes earlier than Akashi.
  <https://www.city.setagaya.lg.jp/documents/3853/4-10_nitieikiseinoaramasi.pdf>
- Kagoshima Prefecture, `日影規制の手引き` gives an example for finding solar noon in Kagoshima by comparing the site longitude with 135°E. The worked explanation treats 135°E as the standard meridian reference and applies a longitude correction because Kagoshima is west of 135°E.
  <https://www.pref.kagoshima.jp/ah12/documents/83382_20200903211213-1.pdf>
- Kozo System / PIVOT, `日影規制に関する条件・用語の解説` states that shadow regulation generally uses the winter-solstice period 8:00 to 16:00 in true solar time, with some regions using central standard time.
  <https://www.pivot.co.jp/post/regulation-sunshadow-keyword.html>
- Nagoya City environmental assessment appendix, `日影計算に用いた理論式`, shows solar altitude and azimuth formulas using the project-site latitude `φ`, solar declination `δ`, and hour angle `t`.
  <https://www.city.nagoya.jp/_res/projects/default_project/_page_/001/008/456/52jhyoka_shiryo_11.pdf>
- EPCOT / ADS-win product page describes ADS-win as producing time-specific shadow diagrams and equal-time shadow diagrams, including mesh and proprietary tracing methods, but the public product page does not disclose its internal solar-time or solar-position formulas.
  <https://www.epcot.co.jp/products/ads10.php>
- A public ADS-BT for Vectorworks tutorial snippet shows a shadow-calculation settings dialog including solar declination, calculation range, latitude/longitude, and orientation. This is useful as evidence that ADS-style software exposes latitude/longitude settings, but it is not documentation of internal calculation formulas.
  <https://www.youtube.com/watch?v=T7MoKrhY6BA>
- Vectorworks Japan's ADS function page describes time-specific shadow and equal-time shadow calculation features, including mesh and proprietary tracing methods, but does not disclose the internal solar-time or solar-position assumptions.
  <https://www.vectorworks.co.jp/products/ADS/func.html>

## Confirmed facts

### Akashi / 135°E is a time reference, not a nationwide project location

Japan Standard Time is tied to the standard meridian at 135°E, commonly associated with Akashi.
For shadow diagrams, this does **not** mean every project should be treated as if it were located at Akashi, nor does it provide a nationwide latitude.
A project in Tokyo, Kagoshima, Hokkaido, or any other location keeps its own site latitude and site longitude.

### Site latitude controls solar altitude

Solar altitude depends on the observer latitude, solar declination, and hour angle.
The Nagoya City formula explicitly uses the project-site latitude `φ` when computing solar altitude.
Therefore, replacing the site latitude with Akashi latitude would be a physical error unless the actual project site is Akashi.

### 135°E is likely used for time correction from Japan Standard Time

135°E is the Japan Standard Time meridian.
When a workflow starts from Japan Standard Time or central standard time, site longitude is needed to correct the time relationship between the standard meridian and the project site.
A site east of 135°E reaches solar noon earlier than the standard meridian; a site west of 135°E reaches solar noon later.
Kagoshima Prefecture's example uses exactly this relationship by comparing Kagoshima longitude with 135°E.

### True solar time is not the same as Japan Standard Time

Public municipal explanations describe regulated shadow time as true solar time in common cases.
True solar time uses the local apparent solar-noon condition: the sun crossing the local meridian is treated as 12:00.
Japan Standard Time is civil clock time based on the 135°E standard meridian.
Those two time bases can differ because of both site longitude and the equation of time.

### ADS-style public materials support feature expectations, not internal formulas

Public ADS / ADS-style pages confirm that commercial tools produce time-specific and equal-time shadow diagrams, and public tutorial material indicates settings such as latitude/longitude and orientation.
However, the public pages checked here do not disclose enough detail to claim ADS internal formulas, time-basis conversion rules, equation-of-time handling, or validation tolerances.
This repository should avoid claiming ADS-equivalent internals unless a primary manual or vendor technical specification is available.

## Terminology for future implementation

### `site_latitude_deg`

The project-site latitude in degrees.
It is required for solar altitude and azimuth calculation.
It is site-specific and must not be replaced by Akashi latitude unless the site is actually in Akashi.

### `site_longitude_deg`

The project-site longitude in degrees east.
It is required when converting between a clock/standard-meridian time basis and local solar time.
It may also be retained for diagnostics even if the user directly supplies true solar time samples.

### Japan Standard Time

The civil clock time used in Japan.
It is based on the 135°E standard meridian.
It should not be confused with local true solar time at the project site.

### `standard_meridian_deg = 135.0`

The standard meridian for Japan Standard Time.
This is a time-reference meridian, not a default project longitude and not a default latitude.
Future settings should keep it explicit so that time correction is auditable.

### Mean solar time

A smoothed solar-time basis using a fictitious mean sun.
Japan Standard Time can be understood as standard-meridian mean solar time, adjusted into a uniform civil clock system.
Mean solar time does not include the day-to-day apparent-sun variation captured by the equation of time.

### True solar time

A local apparent-solar time basis in which local apparent solar noon is 12:00.
Japanese shadow-regulation explanations commonly refer to winter-solstice true solar time for the regulated period.
If future implementation accepts true solar time directly, it still needs site latitude for sun altitude and azimuth, but it may not need longitude for the hour angle itself because the time has already been localized to the apparent sun.

### Equation of time

The correction between mean solar time and apparent/true solar time caused by Earth's orbital eccentricity and axial tilt.
When converting Japan Standard Time to local true solar time, future implementation likely needs both:

1. longitude correction between `site_longitude_deg` and `standard_meridian_deg`; and
2. equation-of-time correction for the selected `date`.

The exact sign convention and formula should be specified and tested before code is implemented.

### `true_north_deg`

The rotation between the model coordinate system and true north.
It affects the direction in which a computed solar azimuth is projected into Revit/Dynamo model coordinates.
It does not change the physical solar altitude or the legal time basis.

## Expected future inputs

Future solar-position implementation should require explicit, reviewable inputs rather than hidden legal defaults:

```text
site_latitude_deg
site_longitude_deg
standard_meridian_deg = 135.0
time_basis
date
true_north_deg
```

Suggested `time_basis` values for a later design discussion:

- `true_solar_time`: input times are already local apparent solar times at the project site.
- `japan_standard_time`: input times are JST clock times and must be converted using the standard meridian, site longitude, and equation of time.
- `central_standard_time`: if used by a specific jurisdiction or reference, define explicitly whether this means JST/135°E mean time and whether apparent-time correction is still required.

## Reasonable assumptions for this repository

- The default legal-analysis path should be designed around winter-solstice true solar time because multiple public Japanese references describe the regulated period that way.
- `standard_meridian_deg` should default to `135.0` for Japan-specific profiles, but it should be treated as a named time-reference constant, not as project location data.
- `site_latitude_deg` and `site_longitude_deg` should remain explicit settings for future solar-position diagnostics.
- The implementation should report the selected `time_basis` and any derived time corrections so reviewers can distinguish JST clock times from true solar times.
- Public ADS-style pages are enough to justify keeping latitude/longitude/orientation settings in our future configuration, but not enough to duplicate or assert ADS proprietary internals.

## Unresolved questions before implementation

- Which exact legal/administrative source should be treated as authoritative for time basis in each supported municipality or prefecture?
- How should jurisdictions that allow or describe central standard time be represented without mixing them with true solar time?
- Which equation-of-time formula and sign convention should be used, and what tolerance should tests allow?
- Should the future `date` input be a literal winter-solstice date for a year, or a profile value such as `winter_solstice` with a documented solar declination model?
- How should leap-year and year-specific solar declination differences be handled for conceptual studies versus permit-oriented checks?
- What primary ADS or ADS-BT technical manual, if any, can be cited for software-specific behavior beyond public product descriptions?

## Implementation guardrails

- Do not implement sun position, true solar time conversion, shadow projection, measurement-grid accumulation, legal masks, 5m/10m lines, or equal-time contours from this note alone.
- Do not treat Akashi / 135°E as a nationwide project latitude or default project location.
- Do not infer ADS internal algorithms from marketing pages or short tutorial snippets.
- Keep future diagnostics explicit about the difference between site location, civil time, standard-meridian time, and true solar time.

## Diagnostic implementation v1: true-solar-time time slices

This repository now includes a diagnostic-only sun position table for inputs that are already expressed as local `true_solar_time`.
It does not convert Japan Standard Time or any other civil clock time into true solar time.
It does not apply an equation-of-time correction.
The 135°E Japan standard meridian is documented only as a future time-conversion reference and is not used in this diagnostic calculation.

Required explicit settings for this v1 diagnostic are:

```text
site_latitude_deg
solar_declination_deg
```

The standard diagnostic window uses 30-minute slices from 08:00 through 16:00 true solar time unless a future settings profile changes the window.
For each slice, the hour angle is computed as:

```text
hour_angle_deg = 15 * (true_solar_hour - 12)
```

Solar altitude uses:

```text
sin(altitude) = sin(latitude) * sin(declination)
              + cos(latitude) * cos(declination) * cos(hour_angle)
```

Solar azimuth is reported in degrees clockwise from true north:

```text
0 = north, 90 = east, 180 = south, 270 = west
```

The diagnostic azimuth formula is:

```text
azimuth_deg = atan2(
    sin(hour_angle),
    cos(hour_angle) * sin(latitude) - tan(declination) * cos(latitude)
) + 180 degrees
```

`shadow_length_factor` is `1 / tan(solar_altitude)` when the sun is above the horizon.
`shadow_direction_vector` is a unit horizontal vector pointing away from the sun in true-north axes:

```text
x_east = sin(solar_azimuth_deg + 180 degrees)
y_north = cos(solar_azimuth_deg + 180 degrees)
z_up = 0
```

This diagnostic does not create Revit elements, project shadow polygons, generate 5m / 10m legal masks, generate equal-time contours, or make legal OK/NG judgements.

## Issue #33 implementation: explicit JST / true-solar-time contract

`solar_calculation_v1` accepts exactly two `time_basis` values:

- `true_solar_time`: input times are already local apparent solar times.
- `japan_standard_time`: input times are Japan Standard Time clock times and must be converted to local true solar time before deriving the hour angle.

Unknown or missing `time_basis` values are blockers for the formal `solar_calculation_v1` result. They are not silently treated as `true_solar_time`.

For `japan_standard_time`, east longitude is positive and the conversion is:

```text
longitude_correction_minutes = 4.0 * (site_longitude_deg - standard_meridian_deg)
true_solar_time_minutes = japan_standard_time_minutes
                        + longitude_correction_minutes
                        + equation_of_time_minutes
```

The Japanese standard meridian default used only for this computational setting is `135.0` degrees east and is recorded in `defaults_applied` when omitted. Sites east of 135°E produce a positive longitude correction; sites west of 135°E produce a negative correction. `equation_of_time_minutes` is defined as the signed value added in the formula above. This implementation normalizes converted minutes into the 0–1440 minute day and reports `day_offset` when the converted true solar time crosses midnight.

For `true_solar_time`, input times are used directly as true solar time. Longitude correction and equation-of-time correction are not applied, and `site_longitude_deg` is not used for hour-angle calculation even if it is present.

The hour angle is always derived from converted or directly supplied true solar time:

```text
hour_angle_deg = 15.0 * (true_solar_hour - 12.0)
```

Date-based calculation of `solar_declination_deg` and `equation_of_time_minutes` is not implemented. Both values must be explicit when needed by the selected time basis. Atmospheric refraction correction is not applied.

`true_north_deg` is defined as the angle measured clockwise from the model coordinate +Y axis to the true-north direction:

- `0`: model +Y is true north.
- `90`: model +X is true north.
- `-90`: model -X is true north.

A true-north-referenced azimuth `A` is converted to model coordinates as:

```text
model_azimuth_deg = (A + true_north_deg) % 360
x_model = sin(model_azimuth_deg)
y_model = cos(model_azimuth_deg)
```

This PR does not read Revit `ProjectLocation` or `ProjectPosition` to infer true north. It uses only the explicit `settings.true_north_deg` value.

The implementation is diagnostic and research-oriented. It is not permit-ready certification, does not reproduce ADS internal specifications, and does not implement formal shadow polygons, Boolean union, time accumulation, equal-time contours, site-boundary processing, 5m/10m legal ranges, legal OK/NG judgement, or Revit element generation.
