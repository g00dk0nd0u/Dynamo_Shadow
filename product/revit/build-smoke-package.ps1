[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RevitApiDir,

    [Parameter(Mandatory = $true)]
    [ValidateSet(2025, 2026)]
    [int]$RevitYear,

    [string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'
$projectDirectory = $PSScriptRoot
$repositoryRoot = (Resolve-Path (Join-Path $projectDirectory '../..')).Path
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $repositoryRoot "dist/RevitShadow/$RevitYear-test"
}
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$OutputDirectory = (Resolve-Path -LiteralPath $OutputDirectory).Path
$apiDirectory = (Resolve-Path -LiteralPath $RevitApiDir).Path

dotnet build (Join-Path $projectDirectory 'RevitShadow.csproj') `
    --configuration Release `
    -p:EnableRevitApi=true `
    "-p:RevitApiDir=$apiDirectory"
if ($LASTEXITCODE -ne 0) { throw "Revit-enabled build failed with exit code $LASTEXITCODE." }

$buildDirectory = Join-Path $projectDirectory 'bin/Release/net8.0-windows'
Copy-Item (Join-Path $buildDirectory 'RevitShadow.dll') $OutputDirectory -Force
Copy-Item (Join-Path $buildDirectory 'ShadowCore.dll') $OutputDirectory -Force

$assemblyPath = Join-Path $OutputDirectory 'RevitShadow.dll'
$escapedAssemblyPath = $assemblyPath -replace '&', '&amp;' -replace '<', '&lt;' -replace '>', '&gt;'
$template = Get-Content (Join-Path $projectDirectory 'RevitShadow.addin.template') -Raw
$manifest = $template.Replace('__REVIT_SHADOW_ASSEMBLY__', $escapedAssemblyPath)
Set-Content (Join-Path $OutputDirectory 'RevitShadow.addin') $manifest -Encoding utf8

Write-Host "Development smoke package created at: $OutputDirectory"
Write-Host "Copy RevitShadow.addin to C:\ProgramData\Autodesk\Revit\Addins\$RevitYear\ and keep both DLLs at the packaged path."
