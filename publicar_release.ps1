# Publica/atualiza release no GitHub (descricao + instalador).
param(
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"
$repo = "CMJaboticabal/Painel-de-controle-vereadores"
$root = $PSScriptRoot

if (-not $Version) {
    $configPath = Join-Path $root "config.py"
    if ($configPath -match 'VERSION = "([^"]+)"' -or (Get-Content $configPath -Raw) -match 'VERSION = "([^"]+)"') {
        $Version = $Matches[1]
    }
}
if (-not $Version) {
    throw "Versao nao encontrada em config.py"
}

$tag = "v$Version"
$installer = Join-Path $root "Output\Instalador_PainelTribuna_v$Version.exe"
$notes = Join-Path $root "RELEASE_v$Version.md"

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

$assetName = [System.IO.Path]::GetFileName($installer)

if ($release) {
    Write-Host "Atualizando release $tag (id $($release.id))..."
    gh release edit $tag --repo $repo --title $tag --notes-file $notes
    Write-Host "Enviando instalador..."
    gh release upload $tag $installer --repo $repo --clobber
} else {
    Write-Host "Criando release $tag..."
    gh release create $tag $installer --repo $repo --title $tag --notes-file $notes --target master
}

Write-Host ""
Write-Host "OK: https://github.com/$repo/releases/tag/$tag"
