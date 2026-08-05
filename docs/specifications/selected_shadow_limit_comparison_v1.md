# Selected shadow limit comparison v1

## Purpose

This specification defines a pure-Python numerical comparison between the maximum shadow durations measured in boundary-distance masks and the near/far limits from the Dynamo Player selected regulatory preset.

This is the first stage of Issue #38. It is not a legal judgement, ordinance applicability certification, permit certification, or confirmation-application result.

## Selected preset comparison vs. legal judgement

Selected preset comparison only compares numbers selected by the user in Dynamo Player:

- `near_limit_minutes`
- `far_limit_minutes`

Legal judgement remains unavailable because the repository does not yet implement a traceable local ordinance applicability schema, municipality metadata, zoning conditions, or permit-ready report flow.

## Zones

- `near`: points more than 5 m and up to 10 m from the site boundary (`5m_to_10m`).
- `far`: points more than 10 m from the site boundary (`over_10m`).

## All presets

`standard_all` and `hokkaido_all` are contour candidate sets. They do not select a unique near/far pair, so comparison status is `undetermined` with blocker `regulatory_limit_pair_not_selected`.

## Formula and equality

For each zone:

```text
observed = measurement_masks.<zone>.maximum_shadow_duration_minutes
allowed = resolved_regulatory_preset.<zone>_limit_minutes
within_selected_limit when observed <= allowed + comparison_epsilon_minutes
exceeds_selected_limit otherwise
```

Equality is treated as within the selected limit. Decisions use internal floating point values, not rounded display values.

The output also reports:

- `difference_minutes = observed - allowed`
- `excess_minutes = max(0, observed - allowed)`
- `remaining_margin_minutes = allowed - observed`

## Numerical approximation

The comparison is based on the current duration grid and trapezoidal time integration prototype. The output records spatial resolution, temporal step, duration method, and comparison epsilon for review.

## Legal and permit status

Ordinance applicability is not certified. Legal judgement status is always `undetermined`, and permit certification is not generated.

## Future connection

A later legal profile schema can connect selected comparison results to traceable municipality / ordinance metadata, zoning applicability, Article 56-2 measurement-height rules, and reporting. This v1 output is designed as an optional upstream numerical stage only.
