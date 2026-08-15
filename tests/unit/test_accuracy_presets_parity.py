import json
from pathlib import Path

from shadow_accuracy_presets import ACCURACY_PRESETS


def test_accuracy_presets_match_shared_python_csharp_parity_fixture():
    fixture_path = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "parity"
        / "accuracy_presets.json"
    )
    with fixture_path.open(encoding="utf-8") as fixture_file:
        expected_presets = json.load(fixture_file)

    assert ACCURACY_PRESETS == expected_presets
