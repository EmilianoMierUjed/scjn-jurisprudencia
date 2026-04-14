"""
Actualizador / Descargador inicial de la Base de Datos SCJN
Descarga tesis desde la API oficial del Semanario Judicial de la Federación.

Sirve para DOS casos de uso:
  1. Descarga inicial (BD vacía): crea la BD y descarga los ~311,000 criterios
     desde cero. Tarda entre 4 y 6 horas. No requiere ningún archivo previo.
  2. Actualización incremental: salta los IDs que ya están en la BD y sólo
     descarga los nuevos. Ideal para correr semanalmente.

Ejecutar:
  - Descarga inicial o incremental: python updater/actualizar_bd.py
  - Automático en Windows: Task Scheduler (cada lunes 6:00 AM)
  - Manual en Windows: doble clic en "Actualizar BD SCJN.bat"
"""

import json
import sqlite3
import sys
import time
import logging
from datetime import datetime
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── Configuración ────────────────────────────────────────────────────────

# API de la SCJN
BASE_URL = "https://bicentenario.scjn.gob.mx/repositorio-scjn"
ENDPOINT_COUNT = "/api/v1/tesis/count"
ENDPOINT_IDS = "/api/v1/tesis/ids"
ENDPOINT_TESIS = "/api/v1/tesis/{id_tesis}"

# Rutas
SCRIPT_DIR = Path(__file__).parent.resolve()
BASE_DIR = SCRIPT_DIR.parent
DB_PATH = BASE_DIR / "data" / "scjn_tesis.db"
LOG_PATH = BASE_DIR / "data" / "ultimo_update.log"
HISTORY_LOG = BASE_DIR / "data" / "update_history.log"

# Parámetros de descarga
PAUSA_SEGUNDOS = 0.05
RETRY_INTENTOS = 3
RETRY_BACKOFF = 1.0
COMMIT_CADA = 50

# ── Logging ──────────────────────────────────────────────────────────────

LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(str(HISTORY_LOG), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("scjn-updater")


# ── HTTP ─────────────────────────────────────────────────────────────────

def crear_sesion_http():
    sesion = requests.Session()
    reintentos = Retry(
        total=RETRY_INTENTOS,
        backoff_factor=RETRY_BACKOFF,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    sesion.mount("https://", HTTPAdapter(max_retries=reintentos))
    return sesion


SESION = crear_sesion_http()


def pedir_json(url, timeout=30):
    try:
        resp = SESION.get(url, timeout=timeout)
        if resp.status_code != 200:
            logger.warning(f"{url} respondio con codigo {resp.status_code}")
            return None
        return resp.json()
    except requests.exceptions.RequestException as e:
        logger.warning(f"Error de conexion en {url}: {e}")
        return None
    except ValueError:
        logger.warning(f"Respuesta no es JSON valido: {url}")
        return None


# ── API SCJN ─────────────────────────────────────────────────────────────

def normalizar_lista_ids(payload):
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for clave in ["data", "ids", "resultados", "results", "items"]:
            valor = payload.get(clave)
            if isinstance(valor, list):
                return valor
    return []


def obtener_total_tesis():
    url = f"{BASE_URL}{ENDPOINT_COUNT}"
    payload = pedir_json(url)
    if isinstance(payload, int):
        return payload
    if isinstance(payload, str) and payload.isdigit():
        return int(payload)
    return None


def obtener_ids_pagina(pagina):
    url = f"{BASE_URL}{ENDPOINT_IDS}?page={pagina}"
    payload = pedir_json(url)
    return normalizar_lista_ids(payload)


def obtener_tesis(id_tesis):
    url = f"{BASE_URL}{ENDPOINT_TESIS.format(id_tesis=id_tesis)}"
    return pedir_json(url)


# ── SQLite ───────────────────────────────────────────────────────────────

def crear_esquema(conn):
    """Crea la tabla tesis, el índice FTS5 y los triggers si no existen."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tesis (
            id_tesis       TEXT PRIMARY KEY,
            rubro          TEXT,
            epoca          TEXT,
            instancia      TEXT,
            organo_juris   TEXT,
            fuente         TEXT,
            tipo_tesis     TEXT,
            anio           INTEGER,
            mes            TEXT,
            materias       TEXT,
            tesis_codigo   TEXT,
            huella_digital TEXT,
            texto          TEXT,
            precedentes    TEXT,
            fecha_descarga TEXT DEFAULT (datetime('now'))
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS tesis_fts USING fts5(
            rubro, texto, precedentes, materias,
            content='tesis',
            content_rowid='rowid',
            tokenize='unicode61 remove_diacritics 2'
        );

        CREATE TRIGGER IF NOT EXISTS tesis_fts_insert
            AFTER INSERT ON tesis BEGIN
            INSERT INTO tesis_fts(rowid, rubro, texto, precedentes, materias)
            VALUES (new.rowid, new.rubro, new.texto, new.precedentes, new.materias);
        END;

        CREATE TRIGGER IF NOT EXISTS tesis_fts_update
            AFTER UPDATE ON tesis BEGIN
            UPDATE tesis_fts SET
                rubro=new.rubro, texto=new.texto,
                precedentes=new.precedentes, materias=new.materias
            WHERE rowid=old.rowid;
        END;

        CREATE TRIGGER IF NOT EXISTS tesis_fts_delete
            AFTER DELETE ON tesis BEGIN
            DELETE FROM tesis_fts WHERE rowid=old.rowid;
        END;
    """)
    conn.commit()


def obtener_ids_existentes(conn):
    cursor = conn.execute("SELECT id_tesis FROM tesis")
    return {fila[0] for fila in cursor.fetchall()}


def insertar_tesis(conn, tesis, id_tesis):
    materias = tesis.get("materias", [])
    if isinstance(materias, list):
        materias_texto = ", ".join(materias)
    else:
        materias_texto = str(materias)

    # v1.2: ya no guardamos json_completo. La columna ocupaba ~612 MB sin
    # ningún consumidor en runtime. Si alguna vez se necesita el JSON original,
    # se puede regenerar desde la API SCJN con el id_tesis.
    conn.execute(
        """
        INSERT OR REPLACE INTO tesis (
            id_tesis, rubro, epoca, instancia, organo_juris, fuente,
            tipo_tesis, anio, mes, materias, tesis_codigo, huella_digital,
            texto, precedentes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(tesis.get("idTesis", id_tesis)),
            tesis.get("rubro", ""),
            tesis.get("epoca", ""),
            tesis.get("instancia", ""),
            tesis.get("organoJuris", ""),
            tesis.get("fuente", ""),
            tesis.get("tipoTesis", ""),
            tesis.get("anio", None),
            tesis.get("mes", ""),
            materias_texto,
            tesis.get("tesis", ""),
            tesis.get("huellaDigital", ""),
            tesis.get("texto", ""),
            tesis.get("precedentes", ""),
        ),
    )


# ── Descarga principal ───────────────────────────────────────────────────

def escribir_log_status(mensaje, nuevas=0, errores=0, total=0):
    contenido = (
        f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Estado: {mensaje}\n"
        f"Tesis nuevas descargadas: {nuevas}\n"
        f"Total en base de datos: {total}\n"
        f"Errores: {errores}\n"
    )
    LOG_PATH.write_text(contenido, encoding="utf-8")


def actualizar():
    logger.info("=" * 50)
    logger.info("Iniciando actualizacion de BD SCJN")
    logger.info(f"BD: {DB_PATH}")

    descarga_inicial = not DB_PATH.exists()
    if descarga_inicial:
        logger.info("Base de datos no encontrada — iniciando descarga inicial.")
        logger.info(f"  Destino: {DB_PATH}")
        logger.info("  Esto puede tardar entre 4 y 6 horas (~311,000 criterios).")
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    else:
        logger.info(f"BD existente encontrada en {DB_PATH}")

    # Verificar conectividad
    total_api = obtener_total_tesis()
    if total_api is not None:
        logger.info(f"Total reportado por la API: {total_api}")
    else:
        logger.warning("No se pudo obtener el total de la API (sin conexion?)")

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")

    if descarga_inicial:
        logger.info("Creando esquema (tabla, FTS5, triggers)...")
        crear_esquema(conn)

    ids_existentes = obtener_ids_existentes(conn)
    antes = len(ids_existentes)
    logger.info(f"Tesis ya en BD: {antes:,}")

    nuevas = 0
    errores = 0
    inicio = time.time()
    pagina = 1
    paginas_vacias_consecutivas = 0

    while True:
        ids = obtener_ids_pagina(pagina)

        if not ids:
            paginas_vacias_consecutivas += 1
            if paginas_vacias_consecutivas >= 3:
                logger.info("3 paginas vacias consecutivas, finalizando.")
                break
            pagina += 1
            continue

        paginas_vacias_consecutivas = 0

        # Filtrar IDs que ya tenemos
        ids_nuevos = [str(i) for i in ids if str(i) not in ids_existentes]

        if not ids_nuevos:
            # Toda la página ya estaba descargada
            pagina += 1
            continue

        logger.info(
            f"Pagina {pagina}: {len(ids_nuevos)} nuevas de {len(ids)} IDs"
        )

        for id_tesis in ids_nuevos:
            tesis = obtener_tesis(id_tesis)

            if not isinstance(tesis, dict):
                errores += 1
                continue

            insertar_tesis(conn, tesis, id_tesis)
            ids_existentes.add(id_tesis)
            nuevas += 1

            if nuevas % COMMIT_CADA == 0:
                conn.commit()

            if nuevas % 100 == 0:
                elapsed = time.time() - inicio
                vel = nuevas / elapsed if elapsed > 0 else 0
                logger.info(f"  {nuevas} nuevas descargadas ({vel:.1f}/seg)")

            time.sleep(PAUSA_SEGUNDOS)

        pagina += 1

    conn.commit()
    total_final = conn.execute("SELECT COUNT(*) FROM tesis").fetchone()[0]
    conn.close()

    elapsed = time.time() - inicio
    minutos = int(elapsed // 60)

    logger.info(f"Actualizacion finalizada.")
    logger.info(f"  Nuevas: {nuevas}")
    logger.info(f"  Errores: {errores}")
    logger.info(f"  Total en BD: {total_final:,}")
    logger.info(f"  Tiempo: {minutos} min")

    if errores > 0:
        mensaje = f"Completado con {errores} error(es) - {nuevas} nuevas"
    elif nuevas > 0:
        mensaje = f"Exito - {nuevas} tesis nuevas descargadas"
    else:
        mensaje = "Base de datos ya actualizada (sin tesis nuevas)"

    escribir_log_status(mensaje, nuevas, errores, total_final)


if __name__ == "__main__":
    try:
        actualizar()
    except Exception as e:
        logger.error(f"Error fatal: {e}")
        escribir_log_status(f"ERROR FATAL: {e}", 0, 1)
        sys.exit(1)
