# Reverse shadow allowance patterns v1

Reverse v2 reserves one continuous sunlight interval. That is deliberately conservative, but it cannot represent every cumulative-shadow result accepted by Forward's selected limit. Stage 1 therefore introduces a pure-Python description of a **zone-common** shadow allowance pattern without changing the production Reverse v2 envelope.

## Safety model

One canonical `shadow_allowed_states` mask applies to every measurement point in a near or far zone and is the Stage 1 canonical numerical contract. Allowing each XY point to choose an independent mask could combine mutually incompatible times into an envelope that no single building satisfies, so point-specific patterns are excluded. `sunlight_required_states` is derived as the boolean complement and is retained only as JSON-safe diagnostic output.

Allowed shadow duration is always calculated by `shadow_duration.integrate_shadow_states_trapezoidal`, including half-interval endpoint contributions. Candidate safety is not inferred from the number of shadow samples. A candidate is retained only when its trapezoidal duration is at most the selected zone limit (within numerical tolerance).

## Bounded candidate family

The generator deterministically enumerates one or two non-overlapping, ordered, contiguous **sunlight-required sample blocks**. Two-block means two sunlight sample blocks, not two shadow blocks. A `sunlight_required_sample_blocks` start or end is the first or last true sample; it is not a continuous geometric interval boundary and must not be passed directly to a sun-ray fan. It does not enumerate arbitrary binary masks, avoiding a `2^N` search. Duplicate masks are removed, results have an explicit stable sort key, and a fixed candidate-count guard returns a blocker without automatic accuracy fallback.

The exact endpoint, stepped, and centered continuous intervals produced by Reverse v2 are converted into the same representation before general candidates. This keeps the centered v2 baseline in the candidate set and gives v2-derived masks deterministic deduplication priority. Only v2-derived patterns preserve their original exact interval as `source_continuous_sunlight_interval`; this metadata remains distinct from the sample run.

## Scope

`reverse_shadow_allowance_patterns_v1` is not connected to the production Reverse algorithm in this stage. General patterns explicitly remain `geometry_constraint_ready: false`: mapping a sample mask to safe geometric constraints is the next PR's responsibility. Reverse v2, its height field, and its envelope outputs remain unchanged. Stage 1 alone makes no production Reverse safety claim. A later PR will connect these zone-common candidates to volume scoring and retain final Forward equal-time validation. These patterns do not perform legal judgement, ordinance selection, or permit certification.
