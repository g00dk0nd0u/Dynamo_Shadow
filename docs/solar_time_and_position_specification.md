# Solar Time and Sun Position Specification v1

## 1. Scope

`jp_shadow_solar_v1` defines the reproducible formal technical solar calculation consumed by the native formal-shadow pipeline. It is a regulatory-reference calculation, not permit-certified legal output.

## 2. Regulatory reference

Japanese shadow review uses winter-solstice conditions, true solar time, ordinarily 08:00–16:00 (09:00–15:00 in Hokkaido), and true rather than magnetic north. This project records those requirements using published government guidance, including [Setagaya's shadow-regulation guide](https://www.city.setagaya.lg.jp/documents/3853/4-10_nitieikiseinoaramasi.pdf) and [Kagoshima Prefecture's guide](https://www.pref.kagoshima.jp/ah12/documents/83382_20200903211213-1.pdf). Authority/checker verification remains necessary before submission use.

## 3. Winter-solstice interpretation

`regulatory_winter_solstice_v1` fixes declination at **-23.439 degrees**. This is the v1 computational reference constant, not a claim that astronomical solstice declination is identical every year. It is independent of execution date and year.

## 4. True solar time

In `true_solar_time`, the supplied time is already local apparent solar time and noon has hour angle zero. Longitude and equation of time may be metadata but do not alter it.

## 5. JST conversion equation

Longitude is east-positive:

```text
longitude_correction_minutes = 4 * (site_longitude_deg - standard_meridian_deg)
true_solar_minutes = jst_minutes + longitude_correction_minutes + equation_of_time_minutes
```

Intermediate minutes are not rounded. Normalization reports `day_offset`, including positive and negative date rollovers.

## 6. Standard meridian 135°E

The default Japanese standard meridian is 135.0°E. It is a civil-time reference, not a default site location.

## 7. Equation-of-time sign convention

The equation-of-time input is the signed number of minutes **added** in the equation above; positive values advance true solar time. It is applied only to JST input.

## 8. Latitude/longitude sign convention

Latitude is north-positive in `[-90, 90]`; longitude is east-positive in `[-180, 180]`. Site latitude affects solar position. Longitude affects only JST conversion.

## 9. Solar altitude and azimuth convention

World axes are +X east, +Y north, +Z up. Altitude is positive above the horizon. Azimuth is clockwise from true north (`0/90/180/270 = N/E/S/W`). Atmospheric refraction is not applied.

## 10. Shadow direction convention

Shadow direction is the unit horizontal direction away from the sun. At or below the horizon no vector or length factor is emitted; the slice is blocked rather than assigned a fabricated direction. The raw astronomical factor is `1/tan(altitude)` and is not clipped in this layer.

## 11. Revit model-axis / true-north convention

Model +X/+Y are Revit model axes. `true_north_deg` is the clockwise rotation from model +Y toward true north under the Dynamo_Shadow settings convention. Thus `model_azimuth = (true_north_azimuth + true_north_deg) mod 360`. `shadow_direction_model` remains the sole formal-projection input. `true_north_deg` is currently supplied through settings; automatic extraction from Revit `ActiveProjectLocation` is a separate future adapter and is not implemented.

## 12. Profile definitions

| Profile | Region scope | Basis | Window | Computational step | Reference shape interval |
|---|---|---|---:|---:|---:|
| `standard_8_16` | Japan excluding Hokkaido-specific time window | true solar | 08:00–16:00 | 30 min | 60 min |
| `hokkaido_9_15` | Hokkaido | true solar | 09:00–15:00 | 30 min | 60 min |

The 60-minute interval describes reference individual legal shadow shapes. The prototype's 30-minute sampling supports future duration work; it does not by itself create a permit-ready equal-time diagram.

## 13. Numerical precision and rounding

Python float precision is retained through hour angle, trigonometry, vectors, normalization, and length-factor calculation. JSON-safe diagnostics round display scalars to six decimal places; rounded output is never fed back into formal geometry.

## 14. Atmospheric refraction policy

No atmospheric-refraction correction is applied in any v1 mode.

## 15. External-reference validation

The transparent daily equations in `date_derived_noaa_v1` follow [NOAA's General Solar Position Calculations](https://gml.noaa.gov/grad/solcalc/solareqns.PDF) only as an engineering reference. The [NREL Solar Position Algorithm report](https://www.nrel.gov/docs/fy08osti/34302.pdf) is a high-accuracy independent technical reference; no SPA source code is copied or redistributed. Deterministic analytical identities, symmetry, rotation, rollover, mode-separation, profile, and stable-serialization tests are the v1 local reference-validation basis.

NOAA/NREL references do not certify this implementation for Japanese confirmation applications. The current provisional external fixture is not claimed as independently reproduced SPA validation.

## 16. Certification limitations

`permit_ready_certified` and `legal_judgement_ready` are always false. No municipality ordinance lookup, union, duration accumulation, contours, boundary clipping, 5m/10m lines, or legal OK/NG result is provided. Authority/checker verification is required before submission use.

## 17. Backward compatibility

Modes never switch because a date happens to be present. `explicit` remains the expert mode; `date_derived_noaa_v1` requires an explicit mode and date. Legacy settings that omit the mode but provide true solar time and `solar_declination_deg=-23.439` remain `explicit`, preserve numerical results, and report `regulatory_winter_solstice_v1` as recommended.

## 18. Worked Tokyo example

For latitude 35.6812°N, declination -23.439°, true north 0°, no refraction, and true solar time:

| Time | Altitude | Solar azimuth | Shadow azimuth | Length factor | Model direction (x, y) |
|---|---:|---:|---:|---:|---:|
| 08:00 | 8.083379° | 126.626834° | 306.626834° | 7.041008 | (-0.802538, 0.596601) |
| 12:00 | 30.879800° | 180.000000° | 0.000000° | 1.672216 | (0.000000, 1.000000) |
| 16:00 | 8.083379° | 233.373166° | 53.373166° | 7.041008 | (0.802538, 0.596601) |

These are reproducible technical values, not a permit judgement.
