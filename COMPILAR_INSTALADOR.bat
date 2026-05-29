@echo off
echo Compilando Instalador...
echo.

if exist "C:\Program Files (x86)\Inno Setup 6\iscc.exe" (
    "C:\Program Files (x86)\Inno Setup 6\iscc.exe" setup_script.iss
) else (
    if exist "C:\Program Files\Inno Setup 6\iscc.exe" (
        "C:\Program Files\Inno Setup 6\iscc.exe" setup_script.iss
    ) else (
        echo COMPILADOR NAO ENCONTRADO nos caminhos padrao. 
        echo Tentando comando global 'iscc'...
        iscc setup_script.iss
    )
)

if %errorlevel% neq 0 (
    echo.
    echo ERRO na compilacao! Verifique as mensagens acima.
) else (
    echo.
    echo SUCESSO! Instalador gerado na pasta Output.
)
pause
