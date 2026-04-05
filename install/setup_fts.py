"""
Configuración de la BD SCJN para búsquedas rápidas.

Crea:
1. Tabla FTS5 (índice de texto completo) sobre rubro, texto, precedentes, materias
2. Triggers para mantener el índice sincronizado automáticamente
3. Índices secundarios para filtros rápidos (tipo_tesis, epoca, anio, instancia)

Se ejecuta UNA VEZ durante la instalación. Si se ejecuta de nuevo,
detecta lo que ya existe y solo crea lo que falta.

Tiempo estimado: 2-5 minutos en ~300,000 registros.
"""

import sqlite3
import sys
import time
from pathlib import Path


def get_db_path():
    """Determina la ruta de la BD según el contexto."""
    # Si se pasa como argumento
    if len(sys.argv) > 1:
        return sys.argv[1]

    # Ruta Windows del producto
    win_path = Path(r"C:\scjn-tool\data\scjn_tesis.db")
    if win_path.exists():
        return str(win_path)

    # Ruta relativa (desarrollo)
    local = Path(__file__).parent.parent / "scjn_tesis.db"
    if local.exists():
        return str(local)

    local_data = Path(__file__).parent.parent / "data" / "scjn_tesis.db"
    if local_data.exists():
        return str(local_data)

    print("ERROR: No se encontro scjn_tesis.db")
    print("Uso: python setup_fts.py [ruta_a_scjn_tesis.db]")
    sys.exit(1)


def table_exists(conn, name):
    cur = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type IN ('table','view') AND name=?",
        (name,),
    )
    return cur.fetchone()[0] > 0


def index_exists(conn, name):
    cur = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name=?",
        (name,),
    )
    return cur.fetchone()[0] > 0


def trigger_exists(conn, name):
    cur = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND name=?",
        (name,),
    )
    return cur.fetchone()[0] > 0


def crear_fts5(conn):
    """Crea la tabla FTS5 y la pobla con los datos existentes."""
    if table_exists(conn, "tesis_fts"):
        print("  FTS5 ya existe, omitiendo creacion.")
        return

    total = conn.execute("SELECT COUNT(*) FROM tesis").fetchone()[0]
    print(f"  Creando tabla FTS5 para {total:,} registros...")

    conn.execute("""
        CREATE VIRTUAL TABLE tesis_fts USING fts5(
            rubro,
            texto,
            precedentes,
            materias,
            content='tesis',
            content_rowid='rowid',
            tokenize='unicode61 remove_diacritics 2'
        )
    """)

    print("  Poblando indice FTS5 (esto tarda 2-5 minutos)...")
    inicio = time.time()

    conn.execute("""
        INSERT INTO tesis_fts(rowid, rubro, texto, precedentes, materias)
        SELECT rowid,
               COALESCE(rubro, ''),
               COALESCE(texto, ''),
               COALESCE(precedentes, ''),
               COALESCE(materias, '')
        FROM tesis
    """)
    conn.commit()

    elapsed = time.time() - inicio
    print(f"  FTS5 poblado en {elapsed:.0f} segundos.")


def crear_triggers(conn):
    """Crea triggers para mantener FTS5 sincronizado con INSERT/UPDATE/DELETE."""

    triggers = {
        "tesis_fts_insert": """
            CREATE TRIGGER tesis_fts_insert AFTER INSERT ON tesis BEGIN
                INSERT INTO tesis_fts(rowid, rubro, texto, precedentes, materias)
                VALUES (new.rowid,
                        COALESCE(new.rubro, ''),
                        COALESCE(new.texto, ''),
                        COALESCE(new.precedentes, ''),
                        COALESCE(new.materias, ''));
            END
        """,
        "tesis_fts_delete": """
            CREATE TRIGGER tesis_fts_delete AFTER DELETE ON tesis BEGIN
                INSERT INTO tesis_fts(tesis_fts, rowid, rubro, texto, precedentes, materias)
                VALUES ('delete', old.rowid,
                        COALESCE(old.rubro, ''),
                        COALESCE(old.texto, ''),
                        COALESCE(old.precedentes, ''),
                        COALESCE(old.materias, ''));
            END
        """,
        "tesis_fts_update": """
            CREATE TRIGGER tesis_fts_update AFTER UPDATE ON tesis BEGIN
                INSERT INTO tesis_fts(tesis_fts, rowid, rubro, texto, precedentes, materias)
                VALUES ('delete', old.rowid,
                        COALESCE(old.rubro, ''),
                        COALESCE(old.texto, ''),
                        COALESCE(old.precedentes, ''),
                        COALESCE(old.materias, ''));
                INSERT INTO tesis_fts(rowid, rubro, texto, precedentes, materias)
                VALUES (new.rowid,
                        COALESCE(new.rubro, ''),
                        COALESCE(new.texto, ''),
                        COALESCE(new.precedentes, ''),
                        COALESCE(new.materias, ''));
            END
        """,
    }

    for name, sql in triggers.items():
        if trigger_exists(conn, name):
            print(f"  Trigger {name} ya existe, omitiendo.")
        else:
            conn.execute(sql)
            print(f"  Trigger {name} creado.")

    conn.commit()


def crear_indices(conn):
    """Crea índices secundarios para filtros rápidos."""
    indices = {
        "idx_tipo_tesis": "CREATE INDEX idx_tipo_tesis ON tesis(tipo_tesis)",
        "idx_epoca": "CREATE INDEX idx_epoca ON tesis(epoca)",
        "idx_anio": "CREATE INDEX idx_anio ON tesis(anio)",
        "idx_instancia": "CREATE INDEX idx_instancia ON tesis(instancia)",
        "idx_tesis_codigo": "CREATE INDEX idx_tesis_codigo ON tesis(tesis_codigo)",
    }

    for name, sql in indices.items():
        if index_exists(conn, name):
            print(f"  Indice {name} ya existe, omitiendo.")
        else:
            conn.execute(sql)
            print(f"  Indice {name} creado.")

    conn.commit()


def main():
    db_path = get_db_path()
    print(f"Base de datos: {db_path}")
    print(f"Tamano: {Path(db_path).stat().st_size / (1024**3):.2f} GB")
    print()

    conn = sqlite3.connect(db_path)

    # Optimizaciones para la escritura masiva
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-512000")  # 512 MB de cache

    print("[1/3] Creando indice FTS5 (texto completo)...")
    crear_fts5(conn)
    print()

    print("[2/3] Creando triggers de sincronizacion...")
    crear_triggers(conn)
    print()

    print("[3/3] Creando indices secundarios...")
    crear_indices(conn)
    print()

    # Verificación
    total = conn.execute("SELECT COUNT(*) FROM tesis").fetchone()[0]
    fts_count = conn.execute(
        "SELECT COUNT(*) FROM tesis_fts"
    ).fetchone()[0]
    print(f"Verificacion: {total:,} registros en tesis, {fts_count:,} en FTS5")

    if total == fts_count:
        print("OK: Los conteos coinciden.")
    else:
        print(f"ADVERTENCIA: Diferencia de {abs(total - fts_count):,} registros.")
        print("Puedes reconstruir el indice eliminando tesis_fts y ejecutando de nuevo.")

    new_size = Path(db_path).stat().st_size / (1024**3)
    print(f"\nTamano final de la BD: {new_size:.2f} GB")
    print("Configuracion completada.")

    conn.close()


if __name__ == "__main__":
    main()
