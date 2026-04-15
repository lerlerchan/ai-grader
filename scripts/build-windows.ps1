Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptRoot
$distDir = Join-Path $repoRoot "dist"
$archivePath = Join-Path $distDir "AI-Grader-windows.zip"

Push-Location $repoRoot
try {
    python -m pip install -e ".[release]"
    pyinstaller --noconfirm --clean release/windows/ai-grader-gui.spec

    if (Test-Path $archivePath) {
        Remove-Item $archivePath -Force
    }

    Compress-Archive -Path (Join-Path $distDir "AI-Grader\*") -DestinationPath $archivePath

    Write-Host ""
    Write-Host "Windows release built successfully."
    Write-Host "Folder : $distDir\AI-Grader"
    Write-Host "Archive: $archivePath"
}
finally {
    Pop-Location
}
