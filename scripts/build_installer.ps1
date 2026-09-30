[CmdletBinding()]
param(
    [string]$OutputDir = "$env:USERPROFILE\OneDrive\Desktop\Kira",
    [string]$SourceBranch = "speech2anywhere",
    [switch]$SkipWheelDownload,
    [switch]$AcceptUnpinnedHashes
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Get-Item (Join-Path $PSScriptRoot "..")).FullName
$BuildDir = Join-Path $RepoRoot "build"
$CacheDir = Join-Path $BuildDir "_cache"
$VenvPython = "$env:USERPROFILE\kira-venv\Scripts\python.exe"
$HashPinFile = Join-Path $RepoRoot "installer\build-inputs.sha256"

function Read-PinnedHash {
    param([string]$Filename)
    if (-not (Test-Path $HashPinFile)) {
        return $null
    }
    foreach ($line in (Get-Content $HashPinFile)) {
        $stripped = $line.Trim()
        if ($stripped.StartsWith('#') -or $stripped -eq '') { continue }
        $parts = $stripped -split '\s+', 2
        if ($parts.Length -eq 2 -and $parts[1].Trim() -eq $Filename) {
            return $parts[0].Trim().ToLower()
        }
    }
    return $null
}

function Append-PinnedHash {
    param([string]$Filename, [string]$Hash)
    $line = "$Hash  $Filename"
    if (-not (Test-Path $HashPinFile)) {
        New-Item -ItemType File -Force -Path $HashPinFile | Out-Null
    }
    Add-Content -Path $HashPinFile -Value $line -Encoding UTF8
}

function Verify-Or-Pin {
    param([string]$File, [string]$Filename)
    $actual = (Get-FileHash -Algorithm SHA256 $File).Hash.ToLower()
    $expected = Read-PinnedHash -Filename $Filename
    if ($expected) {
        if ($actual -ne $expected) {
            throw "SHA256 mismatch for $Filename`n  expected: $expected`n  actual:   $actual`nIf the upstream binary was legitimately updated, edit $HashPinFile and re-pin."
        }
        Write-Host "  sha256 OK ($Filename)"
    } else {
        if (-not $AcceptUnpinnedHashes) {
            throw @"
No SHA256 pin for $Filename in $HashPinFile.
Re-run with -AcceptUnpinnedHashes to auto-record the current hash, OR
edit $HashPinFile and add a line:
  $actual  $Filename
This is TOFU (trust-on-first-use). Pin only after a build you trust.
"@
        }
        Write-Warning "TOFU-pin: writing $Filename hash $actual to $HashPinFile (auto-pin via -AcceptUnpinnedHashes)"
        Append-PinnedHash -Filename $Filename -Hash $actual
    }
}

Write-Host "==> Kira installer build"
Write-Host "Repo:   $RepoRoot"
Write-Host "Build:  $BuildDir"
Write-Host "Cache:  $CacheDir"
Write-Host "Output: $OutputDir"

$pyproject = Get-Content (Join-Path $RepoRoot "pyproject.toml") -Raw
if ($pyproject -notmatch 'version\s*=\s*"([^"]+)"') {
    throw "Could not parse version from pyproject.toml"
}
$Version = $Matches[1]
Write-Host "Version: $Version"

$isccCmd = Get-Command iscc.exe -ErrorAction SilentlyContinue
if ($isccCmd) {
    $iscc = $isccCmd.Source
} else {
    $iscc = $null
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $iscc = $c; break }
    }
    if (-not $iscc) {
        throw "ISCC.exe not found in PATH or any of: $($candidates -join '; '). Open a fresh PowerShell (PATH refresh) or run: winget install JRSoftware.InnoSetup"
    }
}
Write-Host "ISCC:   $iscc"

if (-not (Test-Path $VenvPython)) {
    throw "Dev venv not found at $env:USERPROFILE\kira-venv. Run scripts/install_win.ps1 first."
}

if (Test-Path $BuildDir) {
    Get-ChildItem $BuildDir -Exclude "_cache" | Remove-Item -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $BuildDir, $CacheDir | Out-Null

Write-Host ""
Write-Host "==> 1/7 git archive source"
$sourceZip = Join-Path $BuildDir "kira-source.zip"
& git -c safe.directory='*' -C $RepoRoot archive `
    --format=zip --output=$sourceZip $SourceBranch -- `
    kira/ prompts/ assets/icon.ico assets/icon-branded.ico assets/digitalroots-logo.png assets/kira-splash.png assets/wordlist-de.txt pyproject.toml README.md
if ($LASTEXITCODE -ne 0) { throw "git archive failed (exit $LASTEXITCODE)" }
$sourceDir = Join-Path $BuildDir "kira-source"
New-Item -ItemType Directory -Force -Path $sourceDir | Out-Null
Expand-Archive -Path $sourceZip -DestinationPath $sourceDir -Force
Remove-Item $sourceZip

Write-Host ""
Write-Host "==> 2/7 Python 3.12 embedded"
$pyEmbedZip = Join-Path $CacheDir "python-3.12-embed-amd64.zip"
if (-not (Test-Path $pyEmbedZip)) {
    Write-Host "Downloading python-3.12.10-embed-amd64.zip..."
    & curl.exe -L --fail --retry 3 --retry-delay 5 -o $pyEmbedZip `
        "https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip"
    if ($LASTEXITCODE -ne 0) { throw "Failed to download Python embedded" }
}
Verify-Or-Pin -File $pyEmbedZip -Filename "python-3.12.10-embed-amd64.zip"
$pyDir = Join-Path $BuildDir "python"
New-Item -ItemType Directory -Force -Path $pyDir | Out-Null
Expand-Archive -Path $pyEmbedZip -DestinationPath $pyDir -Force
$pthFile = Get-ChildItem $pyDir -Filter "python3*._pth" | Select-Object -First 1
if ($pthFile) {
    (Get-Content $pthFile.FullName) -replace '^#import site', 'import site' |
        Set-Content $pthFile.FullName
}
$getPip = Join-Path $CacheDir "get-pip.py"
if (-not (Test-Path $getPip)) {
    & curl.exe -L --fail --retry 3 --retry-delay 5 -o $getPip "https://bootstrap.pypa.io/get-pip.py"
    if ($LASTEXITCODE -ne 0) { throw "Failed to download get-pip.py" }
}
Verify-Or-Pin -File $getPip -Filename "get-pip.py"
& "$pyDir\python.exe" $getPip --no-warn-script-location
if ($LASTEXITCODE -ne 0) { throw "get-pip.py failed in embedded python" }

Write-Host ""
Write-Host "==> 3/7 wheels"
$wheelDir = Join-Path $BuildDir "wheels"
New-Item -ItemType Directory -Force -Path $wheelDir | Out-Null
if ($SkipWheelDownload) {
    Write-Host "skipped (-SkipWheelDownload)"
} else {
    & "$pyDir\python.exe" -m pip download `
        -d $wheelDir `
        -r (Join-Path $RepoRoot "installer\requirements-bundle.txt") `
        --platform win_amd64 `
        --python-version 3.12 `
        --implementation cp `
        --only-binary=:all:
    if ($LASTEXITCODE -ne 0) { throw "pip download failed" }
}

Write-Host ""
Write-Host "==> 3b/7 build kira wheel"
& {
    $ErrorActionPreference = "Continue"
    & "$pyDir\python.exe" -m pip install --no-index --find-links $wheelDir --no-warn-script-location hatchling pluggy editables pathspec trove-classifiers 2>&1 | Out-Host
}
if ($LASTEXITCODE -ne 0) { throw "hatchling install in embedded Python failed" }
& {
    $ErrorActionPreference = "Continue"
    & "$pyDir\python.exe" -m pip wheel "$RepoRoot" --no-deps --no-build-isolation -w $wheelDir 2>&1 | Out-Host
}
if ($LASTEXITCODE -ne 0) { throw "pip wheel for kira failed" }
$kiraWheels = Get-ChildItem $wheelDir -Filter "kira-*.whl"
if ($kiraWheels.Count -eq 0) { throw "kira wheel was not produced" }
Write-Host "  built: $($kiraWheels[0].Name)"

& {
    $ErrorActionPreference = "Continue"
    & "$pyDir\python.exe" -m pip uninstall -y hatchling pluggy editables pathspec trove-classifiers 2>&1 | Out-Host
}

Write-Host ""
Write-Host "==> 4/7 OllamaSetup.exe"
$OllamaSetupPath = Join-Path $RepoRoot "installer\embedded\OllamaSetup.exe"
$OllamaUrl = "https://ollama.com/download/OllamaSetup.exe"
$NeedsPull = $true
if (Test-Path $OllamaSetupPath) {
    $existingSize = (Get-Item $OllamaSetupPath).Length
    $age = (Get-Date) - (Get-Item $OllamaSetupPath).LastWriteTime
    if ($existingSize -gt 1.0GB -and $age.TotalDays -lt 30) {
        $NeedsPull = $false
        Write-Host "  cached ($([math]::Round($age.TotalDays,1)) days old, $([math]::Round($existingSize/1MB,1)) MB)"
    } elseif ($existingSize -lt 1.5GB) {
        Write-Host "  cached file too small ($([math]::Round($existingSize/1MB,1)) MB) -- re-pulling"
    }
}
if ($NeedsPull) {
    Write-Host "  pulling fresh from $OllamaUrl..."
    New-Item -ItemType Directory -Force -Path (Split-Path $OllamaSetupPath) | Out-Null
    & curl.exe -L --fail --retry 3 --retry-delay 5 --continue-at - -o $OllamaSetupPath $OllamaUrl
    if ($LASTEXITCODE -ne 0) { throw "Failed to download OllamaSetup.exe" }
}
$OllamaSetupSize = (Get-Item $OllamaSetupPath).Length
Write-Host "  size: $([math]::Round($OllamaSetupSize/1MB, 1)) MB"
if ($OllamaSetupSize -lt 100MB -or $OllamaSetupSize -gt 3GB) {
    throw "OllamaSetup.exe size sanity-check failed: $OllamaSetupSize bytes (expected 100 MB to 3 GB)"
}

$sig = Get-AuthenticodeSignature $OllamaSetupPath
if ($sig.Status -ne "Valid") {
    throw "OllamaSetup.exe Authenticode-Signature is invalid: $($sig.Status)"
}
$signerSubject = $sig.SignerCertificate.Subject
if ($signerSubject -notlike "*Ollama*" -and $signerSubject -notlike "*Meta Platforms*") {
    throw "OllamaSetup.exe is signed by unexpected subject: $signerSubject"
}
Write-Host "  authenticode: $($sig.Status), signer: $signerSubject"
Verify-Or-Pin -File $OllamaSetupPath -Filename "OllamaSetup.exe"

Write-Host ""
Write-Host "==> 5/7 rcedit"
$rcedit = Join-Path $CacheDir "rcedit-x64.exe"
if (-not (Test-Path $rcedit)) {
    & curl.exe -L --fail --retry 3 --retry-delay 5 -o $rcedit `
        "https://github.com/electron/rcedit/releases/download/v2.0.0/rcedit-x64.exe"
    if ($LASTEXITCODE -ne 0) { throw "Failed to download rcedit" }
}
Verify-Or-Pin -File $rcedit -Filename "rcedit-x64.exe"
Copy-Item $rcedit $BuildDir

Write-Host ""
Write-Host "==> 6/7 ISCC compile"
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
& $iscc `
    "/DVersion=$Version" `
    "/DBuildDir=$BuildDir" `
    "/DOutputDir=$OutputDir" `
    (Join-Path $RepoRoot "installer\kira.iss")
if ($LASTEXITCODE -ne 0) { throw "ISCC compile failed" }

Write-Host ""
Write-Host "==> 7/7 SHA256SUMS.txt"
$sumsFile = Join-Path $OutputDir "SHA256SUMS.txt"
$artifacts = Get-ChildItem $OutputDir -Filter "Kira-Setup-v$Version*"
$sumLines = $artifacts | ForEach-Object {
    $h = (Get-FileHash -Algorithm SHA256 $_.FullName).Hash.ToLower()
    "$h  $($_.Name)"
}
$sumsText = ($sumLines -join "`n") + "`n"
[System.IO.File]::WriteAllText($sumsFile, $sumsText, (New-Object System.Text.UTF8Encoding($false)))
$sumLines | ForEach-Object { Write-Host "  $_" }
Write-Host "Wrote $sumsFile"

Write-Host ""
Write-Host "==> done"
$setupExe = Join-Path $OutputDir "Kira-Setup-v$Version.exe"
if (Test-Path $setupExe) {
    $sizeMB = [math]::Round((Get-Item $setupExe).Length / 1MB, 1)
    Write-Host "Setup: $setupExe ($sizeMB MB)"
}
$splits = Get-ChildItem $OutputDir -Filter "Kira-Setup-v$Version-*.bin" -ErrorAction SilentlyContinue
if ($splits) {
    Write-Host "Disk-spanning splits:"
    foreach ($s in $splits) {
        $smb = [math]::Round($s.Length / 1MB, 1)
        Write-Host "  $($s.Name) ($smb MB)"
    }
}
Write-Host ""
Write-Host "Next steps:"
Write-Host "  gh release create v$Version $OutputDir\Kira-Setup-v$Version.exe \"
Write-Host "    $OutputDir\SHA256SUMS.txt \"
Write-Host "    --title 'Kira v$Version' --notes 'Release notes...'"
