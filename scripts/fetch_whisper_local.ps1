param(
    [string]$Repo   = "Systran/faster-whisper-large-v3",
    [string]$Target = "$env:USERPROFILE\models\faster-whisper-large-v3"
)

$ErrorActionPreference = "Stop"

$Files = @("config.json", "preprocessor_config.json", "tokenizer.json", "vocabulary.json", "model.bin")
$Base  = "https://huggingface.co/$Repo/resolve/main"

New-Item -ItemType Directory -Force -Path $Target | Out-Null
Write-Host "==> Target: $Target"
Write-Host "==> Repo:   $Repo`n"

foreach ($f in $Files) {
    $dst = Join-Path $Target $f
    if (Test-Path $dst) {
        $size = (Get-Item $dst).Length
        Write-Host ("--> $f already exists ({0:N1} MB), skipping" -f ($size / 1MB))
        continue
    }
    Write-Host "==> Downloading $f"
    & curl.exe -L --fail --retry 3 --retry-delay 5 -o $dst "$Base/$f"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "curl failed for $f (exit $LASTEXITCODE)"
        exit 1
    }
}

Write-Host "`n==> Done. Files:"
Get-ChildItem $Target | Select-Object Name, @{N="MB";E={[math]::Round($_.Length/1MB,1)}}

Write-Host "`nNext step: set in %APPDATA%\Kira\config.yaml:"
Write-Host "  whisper:"
Write-Host "    model: $($Target -replace '\\','/')"
