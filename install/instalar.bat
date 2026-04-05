@echo off
setlocal EnableDelayedExpansion

set INSTALL_DIR=C:\scjn-tool

echo.
echo ===============================================
echo   Instalacion - SCJN Jurisprudencia Tool
echo ===============================================
echo.

:: ── 1. Verificar Python ──────────────────────────────────────────────

echo [1/6] Verificando Python...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Python no esta instalado o no esta en el PATH.
    echo.
    echo Instrucciones:
    echo   1. Descarga Python desde https://python.org
    echo   2. Al instalar, MARCA la casilla "Add Python to PATH"
    echo   3. Reinicia y ejecuta este instalador de nuevo.
    echo.
    pause
    exit /b 1
)

:: Verificar version 3.10+
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
for /f "tokens=1,2 delims=." %%a in ("!PYVER!") do (
    set PYMAJOR=%%a
    set PYMINOR=%%b
)
if !PYMAJOR! LSS 3 (
    echo ERROR: Se requiere Python 3.10+. Tienes Python !PYVER!
    pause
    exit /b 1
)
if !PYMAJOR! EQU 3 if !PYMINOR! LSS 10 (
    echo ERROR: Se requiere Python 3.10+. Tienes Python !PYVER!
    pause
    exit /b 1
)

echo      Python !PYVER! detectado correctamente.

:: Obtener ruta absoluta de python.exe (Claude Desktop no hereda PATH)
for /f "tokens=*" %%i in ('where python') do (
    set PYTHON_PATH=%%i
    goto :found_python
)
:found_python
echo      Ruta: !PYTHON_PATH!
echo.

:: ── 2. Verificar que la BD existe ────────────────────────────────────

echo [2/6] Verificando base de datos...
if not exist "%INSTALL_DIR%\data\scjn_tesis.db" (
    echo.
    echo ERROR: No se encontro la base de datos.
    echo   Esperada en: %INSTALL_DIR%\data\scjn_tesis.db
    echo.
    echo   Copia el archivo scjn_tesis.db a %INSTALL_DIR%\data\
    echo   antes de ejecutar este instalador.
    echo.
    pause
    exit /b 1
)
echo      Base de datos encontrada.
echo.

:: ── 3. Instalar dependencias ─────────────────────────────────────────

echo [3/6] Instalando dependencias...
pip install -q -r "%INSTALL_DIR%\server\requirements.txt" 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR al instalar dependencias del MCP server.
    echo Intentando con --user...
    pip install --user -q -r "%INSTALL_DIR%\server\requirements.txt" 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo ERROR: No se pudieron instalar dependencias.
        pause
        exit /b 1
    )
)
pip install -q -r "%INSTALL_DIR%\updater\requirements.txt" 2>&1
if %ERRORLEVEL% NEQ 0 (
    pip install --user -q -r "%INSTALL_DIR%\updater\requirements.txt" 2>&1
)
echo      Dependencias instaladas correctamente.
echo.

:: ── 4. Construir indice FTS5 ─────────────────────────────────────────

echo [4/6] Construyendo indice de busqueda rapida (FTS5)...
echo      Esto puede tardar 2-5 minutos. No cierres esta ventana.
echo.
python "%INSTALL_DIR%\install\setup_fts.py" "%INSTALL_DIR%\data\scjn_tesis.db"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ADVERTENCIA: No se pudo crear el indice FTS5.
    echo El sistema funcionara pero las busquedas seran mas lentas.
    echo.
)
echo.

:: ── 5. Configurar Claude Desktop ─────────────────────────────────────

echo [5/6] Configurando Claude Desktop...
set CLAUDE_CONFIG=%APPDATA%\Claude
if not exist "!CLAUDE_CONFIG!" mkdir "!CLAUDE_CONFIG!"

set CONFIG_FILE=!CLAUDE_CONFIG!\claude_desktop_config.json

:: Escapar backslashes para JSON
set PYTHON_JSON=!PYTHON_PATH:\=\\!
set SERVER_JSON=%INSTALL_DIR:\=\\%\\server\\server.py
set DB_JSON=%INSTALL_DIR:\=\\%\\data\\scjn_tesis.db

if exist "!CONFIG_FILE!" (
    echo      Ya existe claude_desktop_config.json
    echo      Creando respaldo...
    copy "!CONFIG_FILE!" "!CONFIG_FILE!.backup" >nul 2>&1

    :: Intentar merge con Python (preservar otros MCPs)
    python -c "import json,sys; f=open(r'!CONFIG_FILE!','r',encoding='utf-8'); c=json.load(f); f.close(); c.setdefault('mcpServers',{}); c['mcpServers']['scjn-jurisprudencia']={'command':'!PYTHON_JSON!','args':['!SERVER_JSON!'],'env':{'DB_PATH':'!DB_JSON!'}}; f=open(r'!CONFIG_FILE!','w',encoding='utf-8'); json.dump(c,f,indent=2,ensure_ascii=False); f.close(); print('      Configuracion actualizada (merge con MCPs existentes).')" 2>nul
    if %ERRORLEVEL% NEQ 0 (
        echo      No se pudo hacer merge. Sobrescribiendo...
        goto :write_fresh_config
    )
    goto :config_done
)

:write_fresh_config
:: Escribir config desde cero con ruta absoluta de python.exe
(
echo {
echo   "mcpServers": {
echo     "scjn-jurisprudencia": {
echo       "command": "!PYTHON_JSON!",
echo       "args": ["!SERVER_JSON!"],
echo       "env": {
echo         "DB_PATH": "!DB_JSON!"
echo       }
echo     }
echo   }
echo }
) > "!CONFIG_FILE!"
echo      Configuracion de Claude Desktop creada.

:config_done
echo.

:: ── 6. Crear tarea programada ────────────────────────────────────────

echo [6/6] Configurando actualizacion automatica semanal...
schtasks /create /tn "SCJN_Actualizar_BD" /tr "\"!PYTHON_PATH!\" \"%INSTALL_DIR%\updater\actualizar_bd.py\"" /sc weekly /d MON /st 06:00 /f >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo      Tarea programada: Cada lunes a las 6:00 AM
) else (
    echo      AVISO: No se pudo crear tarea programada.
    echo      Requiere permisos de administrador.
    echo      Puedes actualizar manualmente con scripts\actualizar_scjn.bat
)

echo.
echo ===============================================
echo   Instalacion completada exitosamente.
echo ===============================================
echo.
echo   Siguiente paso:
echo     1. Cierra Claude Desktop COMPLETAMENTE
echo        (clic derecho en bandeja del sistema - Quit)
echo     2. Abre Claude Desktop de nuevo
echo     3. Deberias ver el icono de herramientas MCP
echo     4. Prueba: "Cuantos criterios tiene la base de datos?"
echo.
echo   Para actualizar la BD manualmente:
echo     Doble clic en scripts\actualizar_scjn.bat
echo.
echo ===============================================
echo.
pause
