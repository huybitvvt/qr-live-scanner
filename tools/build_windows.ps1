$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$buildPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $buildPython)) { throw 'Create .venv and install requirements-build.txt first.' }
& $buildPython tools\prepare_assets.py
if ($LASTEXITCODE -ne 0) { throw 'Asset preparation failed.' }
& $buildPython -m PyInstaller --noconfirm packaging\QRLiveScanner.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }
$compilerCandidates = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
$compiler = $compilerCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $compiler) { throw 'Inno Setup 6 compiler is required for the installer.' }
& $compiler packaging\QRLiveScanner.iss
if ($LASTEXITCODE -ne 0) { throw 'Installer build failed.' }
$versioned = Join-Path $projectRoot 'dist\installer\QRLiveScanner-Setup-1.0.0.exe'
$generic = Join-Path $projectRoot 'dist\installer\QRLiveScanner-Setup.exe'
Copy-Item -LiteralPath $versioned -Destination $generic -Force
$checksum = (Get-FileHash -LiteralPath $versioned -Algorithm SHA256).Hash.ToLowerInvariant()
@("$checksum  QRLiveScanner-Setup-1.0.0.exe", "$checksum  QRLiveScanner-Setup.exe") |
    Set-Content -LiteralPath 'dist\installer\SHA256SUMS.txt' -Encoding ascii
Write-Output "Installer: $versioned"
exit 0
