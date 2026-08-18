from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]


def _property_groups(project_path):
    root = ET.parse(project_path).getroot()
    return {group.get("Condition", ""): group for group in root.findall("PropertyGroup")}


def test_revit_framework_selection_is_local_to_enable_revit_api():
    groups = _property_groups(ROOT / "product/revit/RevitShadow.csproj")

    host_neutral = groups["'$(EnableRevitApi)' != 'true'"]
    assert host_neutral.findtext("TargetFrameworks") == "net8.0-windows;net10.0-windows"

    revit_enabled = groups["'$(EnableRevitApi)' == 'true'"]
    assert revit_enabled.findtext("TargetFramework") == "net8.0-windows"
    assert revit_enabled.find("TargetFrameworks") is None


def test_shadow_core_remains_host_independent_netstandard():
    groups = _property_groups(ROOT / "product/core/ShadowCore.csproj")
    assert groups[""].findtext("TargetFramework") == "netstandard2.0"
    assert groups[""].find("TargetFrameworks") is None


def test_smoke_package_does_not_override_framework_properties():
    script = (ROOT / "product/revit/build-smoke-package.ps1").read_text(encoding="utf-8")
    assert "--framework" not in script
    assert "TargetFramework=" not in script
    assert "TargetFrameworks=" not in script
