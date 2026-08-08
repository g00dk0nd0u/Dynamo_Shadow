import json
from pathlib import Path
from shadow_forward_reverse_validation import build_forward_reverse_validation

def test_frozen_forward_within_reverse_outside_mismatch():
    fixture=json.loads((Path(__file__).parents[1]/'fixtures/forward_reverse_validation/centered_mismatch.json').read_text())
    result=build_forward_reverse_validation(fixture)
    assert result['forward_equivalent']['near_max_minutes']==90.0
    assert result['forward_equivalent']['far_max_minutes']==52.5
    assert result['delta_summary']['mismatch_classification']=='forward_within_reverse_outside'
    assert result['reverse_v2']['envelope_fit']['maximum_height_excess_m']==0.5
    assert result['legal_judgement_generated'] is result['ordinance_selection_certified'] is result['permit_ready_certified'] is False
