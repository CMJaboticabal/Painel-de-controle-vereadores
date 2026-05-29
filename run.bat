@echo off
chcp 65001 > nul
set PYTHONUTF8=1

:: Gerar ID de Sessão Único para Logs
set PAINEL_SESSION_ID=%DATE:~6,4%-%DATE:~3,2%-%DATE:~0,2%_%TIME:~0,2%-%TIME:~3,2%-%TIME:~6,2%
set PAINEL_SESSION_ID=%PAINEL_SESSION_ID: =0%

cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo [ERRO] Ambiente virtual nao encontrado!
    echo Execute install.bat primeiro.
    pause
    exit /b 1
)

echo.
echo ========================================================
echo   SISTEMA DE CONTROLE DE TRIBUNA
echo ========================================================
echo.
echo Iniciando aplicacao...
echo Session ID: %PAINEL_SESSION_ID%
echo.

python main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERRO] O sistema fechou com erro.
    pause
) else (
    echo.
    echo [OK] Sistema finalizado
    pause
)
