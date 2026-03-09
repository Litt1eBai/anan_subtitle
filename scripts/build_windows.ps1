$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Python virtual environment not found at .venv\Scripts\python.exe"
}

& $Python -c "import PyInstaller" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is not installed. Run: .\.venv\Scripts\python.exe -m pip install -r requirements-build.txt"
}

& $Python -m PyInstaller --noconfirm --clean pyinstaller.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

$DistRoot = Join-Path $ProjectRoot "dist\anan_subtitle"
Copy-Item LICENSE (Join-Path $DistRoot "LICENSE") -Force
Copy-Item README.md (Join-Path $DistRoot "README.md") -Force
if (Test-Path "docs\SMOKE_TEST.md") {
    Copy-Item "docs\SMOKE_TEST.md" (Join-Path $DistRoot "SMOKE_TEST.md") -Force
}
if (Test-Path "docs\MODEL_SOURCES.md") {
    Copy-Item "docs\MODEL_SOURCES.md" (Join-Path $DistRoot "MODEL_SOURCES.md") -Force
}
if (Test-Path "docs\THIRD_PARTY_NOTICES.md") {
    Copy-Item "docs\THIRD_PARTY_NOTICES.md" (Join-Path $DistRoot "THIRD_PARTY_NOTICES.md") -Force
}
if (Test-Path "docs\PYSIDE6_LGPL_NOTICE.md") {
    Copy-Item "docs\PYSIDE6_LGPL_NOTICE.md" (Join-Path $DistRoot "PYSIDE6_LGPL_NOTICE.md") -Force
}

Write-Host "Build completed: $DistRoot"
