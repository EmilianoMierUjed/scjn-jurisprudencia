@echo off
echo ========================================
echo   Actualizando Base de Datos SCJN...
echo ========================================
echo.
echo Esto puede tardar varios minutos.
echo No cierres esta ventana.
echo.

cd /d "C:\scjn-tool\updater"
python actualizar_bd.py

echo.
if %ERRORLEVEL% EQU 0 (
    echo Actualizacion completada exitosamente.
) else (
    echo HUBO UN ERROR durante la actualizacion.
    echo Verifica tu conexion a internet e intenta de nuevo.
    echo Si el error persiste, contacta a soporte.
)

echo.
echo Puedes cerrar esta ventana.
pause
