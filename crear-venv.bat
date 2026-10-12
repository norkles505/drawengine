@echo off
setlocal
cd /d "%~dp0"

echo === Creando el entorno virtual de DrawEngine ===

REM Busca Python: primero "py -3.13", si no existe usa "python"
set "PY="
py -3.13 --version >nul 2>&1 && set "PY=py -3.13"
if not defined PY (
    python --version >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo ERROR: No se encontro Python. Instala Python 3.13 y abre una consola nueva.
    pause
    exit /b 1
)

if exist "venv" (
    echo Ya existe la carpeta venv. Borrandola para recrearla limpia...
    rmdir /s /q "venv"
)

%PY% -m venv venv
if errorlevel 1 (
    echo ERROR: No se pudo crear el venv.
    pause
    exit /b 1
)

echo.
echo === Instalando dependencias (requirements.txt) ===
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Fallo la instalacion de dependencias.
    pause
    exit /b 1
)

echo.
echo Listo. Ahora puedes abrir DrawEngine con compilar.bat
pause
endlocal
