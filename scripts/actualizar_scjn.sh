#!/bin/bash
# ============================================
# Script de actualización automática de la BD SCJN
# Se ejecuta vía cron cada viernes a las 3:00 AM
# ============================================

DIRECTORIO="/home/emilianomier/Escritorio/Base de datos SCJN/Base_Datos_SCJN"
LOG="/home/emilianomier/Escritorio/Base de datos SCJN/Base_Datos_SCJN/log_actualizacion.txt"
PYTHON="/usr/bin/python3"

echo "========================================" >> "$LOG"
echo "Inicio: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG"

# Verificar conexión a internet antes de empezar
if ! ping -c 1 bicentenario.scjn.gob.mx &> /dev/null; then
    echo "ERROR: No hay conexión a bicentenario.scjn.gob.mx" >> "$LOG"
    echo "========================================" >> "$LOG"
    exit 1
fi

cd "$DIRECTORIO"

# Contar tesis ANTES de actualizar
ANTES=$($PYTHON -c "import sqlite3; c=sqlite3.connect('scjn_tesis.db'); print(c.execute('SELECT COUNT(*) FROM tesis').fetchone()[0]); c.close()")

# Ejecutar el actualizador
$PYTHON updater/actualizar_bd.py >> "$LOG" 2>&1

# Contar tesis DESPUÉS de actualizar
DESPUES=$($PYTHON -c "import sqlite3; c=sqlite3.connect('scjn_tesis.db'); print(c.execute('SELECT COUNT(*) FROM tesis').fetchone()[0]); c.close()")

NUEVAS=$((DESPUES - ANTES))

echo "Tesis antes: $ANTES" >> "$LOG"
echo "Tesis después: $DESPUES" >> "$LOG"
echo "Tesis nuevas: $NUEVAS" >> "$LOG"
echo "Fin: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG"
echo "========================================" >> "$LOG"

# Guardar fecha de última actualización en archivo simple
echo "Última actualización: $(date '+%Y-%m-%d %H:%M:%S') | Total: $DESPUES tesis | Nuevas: $NUEVAS" > "$DIRECTORIO/ultima_actualizacion.txt"
