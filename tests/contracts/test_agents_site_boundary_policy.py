from pathlib import Path


def test_agents_site_boundary_policy_is_area_based():
    text = Path("AGENTS.md").read_text(encoding="utf-8")
    section = text.split("## Site boundary input rules", 1)[1].split("## Pull request checklist", 1)[0]
    assert "one placed Revit Area" in section or "配置済みRevit Area 1個" in section
    assert "Area Boundary lines must not be exposed as a multiple-selection formal input" in section
    assert "Property Line / Site Property / Model Lines are not formal site boundary inputs" in section
    assert "legacy diagnostic-only" in section
    assert "Legal judgement is not implemented" in section
    assert "Permit certification is not implemented" in section
