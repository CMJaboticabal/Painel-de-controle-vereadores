# Publica/atualiza a release v1.7.8 no GitHub (descricao + instalador).
$ErrorActionPreference = "Stop"
$repo = "CMJaboticabal/Painel-de-controle-vereadores"
$tag = "v1.7.8"
$installer = Join-Path $PSScriptRoot "Output\Instalador_PainelTribuna_v1.7.8.exe"
$notes = Join-Path $PSScriptRoot "RELEASE_v1.7.8.md"

if (-not (Test-Path $installer)) {
    throw "Instalador nao encontrado: $installer"
}
if (-not (Test-Path $notes)) {
    throw "Arquivo de notas nao encontrado: $notes"
}

$gh = Get-Command gh -ErrorAction SilentlyContinue
if (-not $gh) {
    throw "GitHub CLI (gh) nao encontrado. Instale: winget install GitHub.cli"
}

if (-not $env:GH_TOKEN) {
    $credOut = @"
protocol=https
host=github.com

"@ | & git credential fill 2>$null
    $token = ($credOut | Where-Object { $_ -match '^password=' }) -replace '^password=',''
    if ($token) { $env:GH_TOKEN = $token }
}

gh auth status 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0 -and -not $env:GH_TOKEN) {
    Write-Host "Execute: gh auth login"
    exit 1
}

$release = $null
try {
    $releaseJson = gh api "repos/$repo/releases/tags/$tag" 2>$null
    if ($LASTEXITCODE -eq 0 -and $releaseJson) {
        $release = $releaseJson | ConvertFrom-Json
    }
} catch { }

if ($release) {
    Write-Host "Atualizando release $tag (id $($release.id))..."
    gh release edit $tag --repo $repo --title "v1.7.8" --notes-file $notes
    $hasAsset = $false
    try {
        $assets = gh api "repos/$repo/releases/$($release.id)/assets" --jq ".[].name"
        $hasAsset = ($assets -contains "Instalador_PainelTribuna_v1.7.8.exe")
    } catch { }
    if (-not $hasAsset) {
        Write-Host "Enviando instalador..."
        gh release upload $tag $installer --repo $repo --clobber
    } else {
        Write-Host "Substituindo asset do instalador..."
        gh release upload $tag $installer --repo $repo --clobber
    }
} else {
    Write-Host "Criando release $tag (tag existe, release ainda nao)..."
    gh release create $tag $installer --repo $repo --title "v1.7.8" --notes-file $notes --target master
}

Write-Host ""
Write-Host "OK: https://github.com/$repo/releases/tag/$tag"
