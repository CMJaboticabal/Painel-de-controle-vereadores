@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo Publicando release v1.7.8 no GitHub...
echo.

where gh >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] GitHub CLI nao encontrado. Instale: winget install GitHub.cli
    pause
    exit /b 1
)

gh auth status >nul 2>&1
if %errorlevel% neq 0 (
    echo Faca login no GitHub:
    gh auth login
    if %errorlevel% neq 0 exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0publicar_release.ps1"
if %errorlevel% neq 0 (
    echo.
    echo [ERRO] Falha ao publicar release.
    pause
    exit /b 1
)

echo.
echo Release publicada com sucesso.
pause
