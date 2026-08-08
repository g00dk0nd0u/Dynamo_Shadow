# Reverse-shadow constraint-count preflight

`tools/benchmark_reverse_constraint_counts.py` records count-only, pure-Python
preflight data for representative rectangular sites using Reverse Standard and
the `standard_3_2` interval durations. It does not run the candidate height
solver and therefore remains suitable for the normal test suite.

| Site | Inside height points | Near measurement points | Far measurement points | Near candidates | Far candidates | Raw constraint pairs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 50 m × 50 m | 2,601 | 232 | 263 | 13 | 9 | 14,001,183 |
| 100 m × 100 m | 10,201 | 432 | 463 | 13 | 9 | 99,796,383 |
| 150 m × 200 m | 30,351 | 732 | 763 | 13 | 9 | 497,240,433 |

These figures explain why the former 25-million *theoretical-pair* preflight
rejected ordinary 1 m sites before useful work. The limit remains 25 million,
but now applies to facet evaluations after an exact candidate-azimuth exclusion.
Candidate fan angles and ordering are compiled once. Directions outside that
closed fan range are mathematically unable to select a facet and are skipped;
no approximate spatial pruning, coarsening, fallback, or concurrency is used.

Run the preflight with:

```text
python tools/benchmark_reverse_constraint_counts.py
```
