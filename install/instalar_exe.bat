@echo off
setlocal EnableDelayedExpansion

:: ════════════════════════════════════════════════════════════════════════
::  Instalador "modo .exe" — para clientes que NO tienen Python.
::
::  Asume que en la carpeta `bin\` viven:
::    bin\scjn-mcp-server.exe
::    bin\scjn-cli.exe                (opcional, para el modo API)
::
::  Y que en `data\` está la BD:
::    data\scjn_tesis.db
::
::  Si tienes Python y prefieres correr el .py directamente, usa el
::  instalador clásico `instalar.bat` en lugar de este.
:: ════════════════════════════════════════════════════════════════════════

set INSTALL_DIR=C:\scjn-tool
set EXE_PATH=%INSTALL_DIR%\bin\scjn-mcp-server.exe
set DB_PATH=%INSTALL_DIR%\data\scjn_tesis.db

echo.
echo ===============================================
echo   Instalacion - SCJN Jurisprudencia Tool (.exe)
echo ===============================================
echo.

:: ── 1. Verificar que el .exe existe ──────────────────────────────────

echo [1/4] Verificando ejecutable...
if not exist "%EXE_PATH%" (
    echo.
    echo ERROR: No se encontro %EXE_PATH%
    echo.
    echo   Copia scjn-mcp-server.exe a %INSTALL_DIR%\bin\
    echo   antes de ejecutar este instalador.
    echo.
    pause
    exit /b 1
)
echo      Ejecutable encontrado.
echo.

:: ── 2. Verificar la base de datos ────────────────────────────────────

echo [2/4] Verificando base de datos...
if not exist "%DB_PATH%" (
    echo.
    echo ERROR: No se encontro la base de datos.
    echo   Esperada en: %DB_PATH%
    echo.
    echo   Copia el archivo scjn_tesis.db a %INSTALL_DIR%\data\
    echo   antes de ejecutar este instalador.
    echo.
    pause
    exit /b 1
)
echo      Base de datos encontrada.
echo.

:: ── 3. Configurar Claude Desktop ─────────────────────────────────────

echo [3/4] Configurando Claude Desktop...
set CLAUDE_CONFIG=%APPDATA%\Claude
if not exist "!CLAUDE_CONFIG!" mkdir "!CLAUDE_CONFIG!"
set CONFIG_FILE=!CLAUDE_CONFIG!\claude_desktop_config.json

:: Escapar backslashes para JSON
set EXE_JSON=%EXE_PATH:\=\\%
set DB_JSON=%DB_PATH:\=\\%

if exist "!CONFIG_FILE!" (
    echo      Ya existe claude_desktop_config.json — creando respaldo.
    copy "!CONFIG_FILE!" "!CONFIG_FILE!.backup" >nul 2>&1
    :: Merge con Python si está disponible (preserva otros MCPs)
    where python >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        python -c "import json; f=open(r'!CONFIG_FILE!','r',encoding='utf-8'); c=json.load(f); f.close(); c.setdefault('mcpServers',{}); c['mcpServers']['scjn-jurisprudencia']={'command':'!EXE_JSON!','env':{'DB_PATH':'!DB_JSON!'}}; f=open(r'!CONFIG_FILE!','w',encoding='utf-8'); json.dump(c,f,indent=2,ensure_ascii=False); f.close(); print('      Configuracion fusionada con MCPs existentes.')" 2>nul
        if !ERRORLEVEL! EQU 0 goto :config_done
    )
    echo      Sin Python para hacer merge — sobrescribiendo.
)

:: Escribir config desde cero
(
echo {
echo   "mcpServers": {
echo     "scjn-jurisprudencia": {
echo       "command": "!EXE_JSON!",
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

:: ── 4. Tarea programada para actualizacion (opcional) ────────────────

echo [4/4] Configurando actualizacion automatica semanal...
:: El updater todavia es Python; si no hay Python instalado se omite.
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo      AVISO: Python no esta instalado, se omite la tarea programada.
    echo      Para actualizar la BD, descarga la ultima version manualmente.
    goto :done
)
schtasks /create /tn "SCJN_Actualizar_BD" /tr "python \"%INSTALL_DIR%\updater\actualizar_bd.py\"" /sc weekly /d MON /st 06:00 /f >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo      Tarea programada: cada lunes a las 6:00 AM.
) else (
    echo      AVISO: no se pudo crear la tarea (requiere admin^).
)

:done
echo.
echo ===============================================
echo   Instalacion completada.
echo ===============================================
echo.
echo   Siguiente paso:
echo     1. Cierra Claude Desktop COMPLETAMENTE.
echo     2. Abrelo de nuevo.
echo     3. Verifica que aparezca el icono de herramientas MCP.
echo     4. Prueba: "Cuantos criterios tiene la base de datos?"
echo.
echo ===============================================
echo.
pause
