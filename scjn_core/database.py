"""
Acceso a la BD SQLite y detección de FTS5.

Las funciones de scjn_core.search reciben una conexión ya abierta como
primer argumento (inyección de dependencia) — esto las hace testeables sin
tocar la BD real. Este módulo es lo único que sabe dónde vive la BD.
"""

import sqlite3
from pathlib import Path

from .config import DB_PATH, get_logger

logger = get_logger("scjn.database")

# Cache del estado de FTS5 — solo lo verificamos una vez por proceso.
_fts_available: bool | None = None


def connect(db_path: str | None = None) -> sqlite3.Connection:
    """Abre conexión a la BD SQLite. Lanza FileNotFoundError si no existe."""
    path = db_path or DB_PATH
    if not Path(path).exists():
        raise FileNotFoundError(
            f"No se encontró la base de datos en: {path}\n"
            f"Verifica que scjn_tesis.db esté en esa ruta."
        )
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def has_fts(conn: sqlite3.Connection | None = None) -> bool:
    """Verifica si la tabla FTS5 existe y responde queries."""
    global _fts_available
    if _fts_available is not None:
        return _fts_available

    cerrar = False
    if conn is None:
        try:
            conn = connect()
            cerrar = True
        except Exception:
            _fts_available = False
            return False

    try:
        conn.execute("SELECT COUNT(*) FROM tesis_fts WHERE tesis_fts MATCH 'test'")
        _fts_available = True
        logger.info("FTS5 disponible — búsquedas rápidas activadas")
    except Exception:
        _fts_available = False
        logger.warning("FTS5 NO disponible — usando LIKE (más lento)")
    finally:
        if cerrar:
            conn.close()

    return _fts_available


def reset_fts_cache() -> None:
    """Permite forzar una nueva detección de FTS5 (útil en tests)."""
    global _fts_available
    _fts_available = None


def rows_to_dicts(rows: list) -> list[dict]:
    """Convierte filas sqlite3.Row a dicts puros."""
    return [dict(row) for row in rows]
