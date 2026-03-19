[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$IncludeUserData
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

function Remove-PathSafe {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    if (-not (Test-Path $Path)) {
        Write-Host "[skip] ${Label}: $Path"
        return
    }

    if ($PSCmdlet.ShouldProcess($Path, "Remove $Label")) {
        try {
            Remove-Item -Recurse -Force $Path
            Write-Host "[done] ${Label}: $Path"
        }
        catch {
            throw "Failed to remove ${Label}: $Path`n$($_.Exception.Message)"
        }
    }
}

function Get-UserAppRoot {
    $localAppData = $env:LOCALAPPDATA
    if ([string]::IsNullOrWhiteSpace($localAppData)) {
        $localAppData = $env:APPDATA
    }
    if ([string]::IsNullOrWhiteSpace($localAppData)) {
        throw "Cannot resolve LOCALAPPDATA or APPDATA."
    }
    return Join-Path $localAppData "anan_subtitle"
}

function Get-PackagedAppProcesses {
    $distRoot = (Join-Path $ProjectRoot "dist\anan_subtitle").ToLowerInvariant()
    Get-Process -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -and $_.Path.ToLowerInvariant().StartsWith($distRoot) }
}

function Stop-PackagedAppProcesses {
    $processes = @(Get-PackagedAppProcesses)
    if ($processes.Count -eq 0) {
        return
    }

    foreach ($process in $processes) {
        $target = "PID=$($process.Id) $($process.ProcessName)"
        if ($PSCmdlet.ShouldProcess($target, "Stop packaged app process")) {
            Stop-Process -Id $process.Id -Force
            Write-Host "[done] stopped packaged app process: $target"
        }
    }
}

Remove-PathSafe -Path (Join-Path $ProjectRoot "build") -Label "build artifacts"
Stop-PackagedAppProcesses
Remove-PathSafe -Path (Join-Path $ProjectRoot "dist") -Label "packaged output"
Remove-PathSafe -Path (Join-Path $ProjectRoot "tests/.tmp") -Label "tests/.tmp"

$ScanRoots = @(
    (Join-Path $ProjectRoot "src"),
    (Join-Path $ProjectRoot "tests"),
    (Join-Path $ProjectRoot "scripts")
)

foreach ($scanRoot in $ScanRoots) {
    if (-not (Test-Path $scanRoot)) {
        continue
    }

    Get-ChildItem -Path $scanRoot -Recurse -Directory -Force -Filter "__pycache__" -ErrorAction SilentlyContinue |
        ForEach-Object {
            Remove-PathSafe -Path $_.FullName -Label "__pycache__"
        }

    Get-ChildItem -Path $scanRoot -Recurse -File -Force -Include "*.pyc" -ErrorAction SilentlyContinue |
        ForEach-Object {
            if ($PSCmdlet.ShouldProcess($_.FullName, "Remove pyc file")) {
                Remove-Item -Force $_.FullName
                Write-Host "[done] pyc file: $($_.FullName)"
            }
        }
}

Get-ChildItem -Path (Join-Path $ProjectRoot "tests") -Directory -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like "tmp_*" } |
    ForEach-Object {
        Remove-PathSafe -Path $_.FullName -Label "test temp directory"
    }

if ($IncludeUserData) {
    $userAppRoot = Get-UserAppRoot
    Remove-PathSafe -Path $userAppRoot -Label "user runtime data"
    Write-Host "[info] User runtime data cleared. Packaged app will run first-start setup again."
} else {
    Write-Host "[info] User runtime data was preserved."
    Write-Host "[info] Use -IncludeUserData to remove %LOCALAPPDATA%\\anan_subtitle and reset packaged first-start state."
}
