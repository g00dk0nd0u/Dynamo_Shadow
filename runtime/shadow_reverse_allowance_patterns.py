"""Zone-common Reverse v3 shadow-allowance pattern generation (pure Python)."""
import math

from shadow_duration import integrate_shadow_states_trapezoidal


METHOD = "reverse_shadow_allowance_patterns_v1"
MAX_REVERSE_ALLOWANCE_PATTERN_CANDIDATES = 50000
_DURATION_TOLERANCE_MINUTES = 1e-9


def build_trapezoidal_sample_ownership_cells(sample_minutes):
    """Partition a sampled window into the cells owned by trapezoidal states."""
    samples = [float(value) for value in sample_minutes]
    if len(samples) < 2 or any(not math.isfinite(value) for value in samples) or any(
            samples[index + 1] <= samples[index] for index in range(len(samples) - 1)):
        raise ValueError("invalid_reverse_shadow_sample_minutes")
    boundaries = [samples[0]] + [
        (samples[index] + samples[index + 1]) / 2.0
        for index in range(len(samples) - 1)] + [samples[-1]]
    return [{"sample_index": index, "start_minutes": boundaries[index],
             "end_minutes": boundaries[index + 1],
             "duration_minutes": boundaries[index + 1] - boundaries[index],
             "semantics": "trapezoidal_sample_ownership_cell"}
            for index in range(len(samples))]


GEOMETRY_MAPPING_PRESERVE_V2_EXACT = "preserve_v2_exact"
GEOMETRY_MAPPING_SAMPLE_OWNERSHIP = "sample_ownership"


def map_pattern_to_geometric_constraints(pattern, mode=GEOMETRY_MAPPING_PRESERVE_V2_EXACT):
    """Purely map a mask using explicit exact-v2 or ownership-cell semantics."""
    if mode not in (GEOMETRY_MAPPING_PRESERVE_V2_EXACT, GEOMETRY_MAPPING_SAMPLE_OWNERSHIP):
        raise ValueError("invalid_reverse_shadow_geometry_mapping_mode")
    mapped = dict(pattern)
    source = pattern.get("source_continuous_sunlight_interval")
    if source is not None and mode == GEOMETRY_MAPPING_PRESERVE_V2_EXACT:
        intervals = [{"start_minutes": float(source["start_minutes"]),
                      "end_minutes": float(source["end_minutes"]),
                      "source_start_sample_index": None, "source_end_sample_index": None,
                      "semantics": "v2_exact_continuous_sunlight_interval"}]
    else:
        cells = build_trapezoidal_sample_ownership_cells(pattern["sample_minutes"])
        indices = [index for index, required in enumerate(pattern["sunlight_required_states"]) if required]
        intervals = []
        if indices:
            first = previous = indices[0]
            for index in indices[1:] + [None]:
                if index is not None and index == previous + 1:
                    previous = index
                    continue
                intervals.append({"start_minutes": cells[first]["start_minutes"],
                                  "end_minutes": cells[previous]["end_minutes"],
                                  "source_start_sample_index": first,
                                  "source_end_sample_index": previous,
                                  "semantics": "trapezoidal_sample_ownership_cell_union"})
                if index is not None:
                    first = previous = index
    mapped["geometric_constraint_intervals"] = intervals
    mapped["geometry_constraint_ready"] = True
    return mapped


def _timeline(start_minutes, end_minutes, step_minutes):
    start, end, step = map(float, (start_minutes, end_minutes, step_minutes))
    if not all(math.isfinite(value) for value in (start, end, step)) or end <= start or step <= 0:
        raise ValueError("invalid_reverse_shadow_allowance_pattern_timeline")
    values = [start]
    value = start
    while value + step < end - _DURATION_TOLERANCE_MINUTES:
        value += step
        values.append(value)
    if values[-1] < end - _DURATION_TOLERANCE_MINUTES:
        values.append(end)
    return values


def _states_for_intervals(sample_minutes, intervals):
    return [any(first - _DURATION_TOLERANCE_MINUTES <= minute <= last + _DURATION_TOLERANCE_MINUTES
                for first, last in intervals) for minute in sample_minutes]


def _pattern(sample_minutes, sunlight_states, blocks, selected_limit_minutes,
             generation_family, pattern_id=None, v2_baseline=False,
             source_continuous_sunlight_interval=None):
    shadow_states = [not value for value in sunlight_states]
    allowed = integrate_shadow_states_trapezoidal(shadow_states, sample_minutes)
    if allowed > selected_limit_minutes + _DURATION_TOLERANCE_MINUTES:
        return None
    block_data = [{"start_sample_index": first, "end_sample_index": last,
                   "start_sample_minutes": sample_minutes[first],
                   "end_sample_minutes": sample_minutes[last],
                   "semantics": "contiguous_required_sample_run"}
                  for first, last in blocks]
    return {
        "pattern_id": pattern_id,
        "sample_minutes": list(sample_minutes),
        "shadow_allowed_states": shadow_states,
        "sunlight_required_states": list(sunlight_states),
        "allowed_shadow_duration_minutes": allowed,
        "selected_limit_minutes": selected_limit_minutes,
        "within_selected_limit": True,
        "sunlight_required_sample_blocks": block_data,
        "sunlight_required_block_count": len(blocks),
        "source_continuous_sunlight_interval": source_continuous_sunlight_interval,
        "geometric_constraint_intervals": None,
        "geometry_constraint_ready": False,
        "generation_family": generation_family,
        "v2_baseline": bool(v2_baseline),
        "permit_ready_certified": False,
    }


def build_pattern_from_continuous_sunlight_interval(
        regulation_start_minutes, regulation_end_minutes, sunlight_start_minutes,
        sunlight_end_minutes, step_minutes, selected_limit_minutes, pattern_id=None,
        generation_family="v2_baseline", v2_baseline=False):
    """Convert an exact v2 continuous-sunlight interval to a canonical sample mask."""
    samples = _timeline(regulation_start_minutes, regulation_end_minutes, step_minutes)
    sunlight_start, sunlight_end, limit = map(
        float, (sunlight_start_minutes, sunlight_end_minutes, selected_limit_minutes))
    if (not math.isfinite(limit) or limit < 0 or sunlight_start < samples[0] or
            sunlight_end > samples[-1] or sunlight_end <= sunlight_start):
        raise ValueError("invalid_reverse_shadow_continuous_sunlight_interval")
    # A sampled state represents its following interval. At the regulation-window
    # end there is no following interval, so use the preceding endpoint instead.
    if abs(sunlight_end - samples[-1]) <= _DURATION_TOLERANCE_MINUTES:
        sunlight = [sunlight_start < minute <= sunlight_end for minute in samples]
    else:
        sunlight = [sunlight_start <= minute < sunlight_end for minute in samples]
    indices = [index for index, required in enumerate(sunlight) if required]
    source_interval = {"start_minutes": sunlight_start, "end_minutes": sunlight_end}
    return _pattern(samples, sunlight, [(indices[0], indices[-1])], limit,
                    generation_family, pattern_id, v2_baseline, source_interval)


def _sort_key(pattern):
    blocks = pattern["sunlight_required_sample_blocks"]
    padded = [(item["start_sample_index"], item["end_sample_index"])
              for item in blocks] + [(-1, -1)] * (2-len(blocks))
    required_duration = integrate_shadow_states_trapezoidal(
        pattern["sunlight_required_states"], pattern["sample_minutes"])
    return (pattern["sunlight_required_block_count"], required_duration,
            padded[0][0], padded[0][1], padded[1][0], padded[1][1],
            tuple(pattern["shadow_allowed_states"]))


def generate_shadow_allowance_patterns(start_minutes, end_minutes,
                                       selected_limit_minutes, step_minutes,
                                       maximum_candidate_count=MAX_REVERSE_ALLOWANCE_PATTERN_CANDIDATES):
    """Enumerate deterministic one/two sunlight-block masks, never arbitrary masks."""
    from shadow_reverse_low_rise import build_sunlight_interval_candidates
    base = {
        "available": False, "complete": False, "method": METHOD,
        "regulation_window_start_minutes": start_minutes,
        "regulation_window_end_minutes": end_minutes,
        "sun_time_step_minutes": step_minutes,
        "selected_limit_minutes": selected_limit_minutes,
        "sample_minutes": [], "candidate_count": 0,
        "one_block_candidate_count": 0, "two_block_candidate_count": 0,
        "v2_baseline_pattern_id": None, "candidates": [],
        "maximum_candidate_count": maximum_candidate_count,
        "automatic_accuracy_fallback_used": False, "blockers": [], "warnings": [],
        "legal_judgement_generated": False, "ordinance_selection_certified": False,
        "permit_ready_certified": False,
    }
    try:
        samples = _timeline(start_minutes, end_minutes, step_minutes)
        limit = float(selected_limit_minutes)
        maximum = int(maximum_candidate_count)
        if not math.isfinite(limit) or limit < 0 or maximum <= 0:
            raise ValueError()
    except (TypeError, ValueError, OverflowError):
        base["blockers"].append({"failure_code": "reverse_shadow_invalid_allowance_pattern_input"})
        return base
    base["sample_minutes"] = samples
    candidates = {}

    def add(candidate, priority):
        if candidate is None:
            return True
        key = tuple(candidate["shadow_allowed_states"])
        previous = candidates.get(key)
        if previous is None or priority < previous[0]:
            candidates[key] = (priority, candidate)
        return len(candidates) <= maximum

    v2 = build_sunlight_interval_candidates(start_minutes, end_minutes, limit, step_minutes)
    if not v2.get("complete"):
        base["blockers"].extend(v2.get("blockers") or [])
        return base
    centered = (v2["sunlight_start_minutes"], v2["sunlight_end_minutes"])
    for index, interval in enumerate(v2["candidates"]):
        pair = (interval["sunlight_start_minutes"], interval["sunlight_end_minutes"])
        is_centered = pair == centered
        candidate = build_pattern_from_continuous_sunlight_interval(
            start_minutes, end_minutes, pair[0], pair[1], step_minutes, limit,
            "v2-baseline" if is_centered else "v2-continuous-%03d" % index,
            "v2_baseline", is_centered)
        if not add(candidate, 0):
            break

    count = len(samples)
    if len(candidates) <= maximum:
        for first in range(count):
            for last in range(first, count):
                sunlight = [first <= index <= last for index in range(count)]
                if not add(_pattern(samples, sunlight, [(first, last)], limit, "one_block"), 1):
                    break
            if len(candidates) > maximum:
                break
    if len(candidates) <= maximum:
        for first_start in range(count):
            for first_end in range(first_start, count):
                for second_start in range(first_end + 2, count):
                    for second_end in range(second_start, count):
                        sunlight = [first_start <= index <= first_end or second_start <= index <= second_end
                                    for index in range(count)]
                        if not add(_pattern(samples, sunlight,
                                            [(first_start, first_end), (second_start, second_end)],
                                            limit, "two_block"), 2):
                            break
                    if len(candidates) > maximum:
                        break
                if len(candidates) > maximum:
                    break
            if len(candidates) > maximum:
                break
    if len(candidates) > maximum:
        base["blockers"].append({
            "failure_code": "reverse_shadow_allowance_pattern_candidate_limit_exceeded",
            "requested_candidate_count_lower_bound": len(candidates),
            "maximum_candidate_count": maximum,
            "automatic_accuracy_fallback_used": False,
        })
        return base

    ordered = [map_pattern_to_geometric_constraints(item)
               for item in sorted((item[1] for item in candidates.values()), key=_sort_key)]
    for index, candidate in enumerate(ordered):
        if candidate["pattern_id"] is None:
            candidate["pattern_id"] = "allowance-%05d" % index
    baseline = next((item for item in ordered if item["v2_baseline"]), None)
    base.update({
        "available": True, "complete": True, "candidate_count": len(ordered),
        "one_block_candidate_count": sum(item["sunlight_required_block_count"] == 1 for item in ordered),
        "two_block_candidate_count": sum(item["sunlight_required_block_count"] == 2 for item in ordered),
        "v2_baseline_pattern_id": baseline["pattern_id"] if baseline else None,
        "candidates": ordered,
    })
    return base
