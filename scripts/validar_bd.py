"""
Healthcheck de la base de datos SCJN.

Verifica que la BD esté íntegra y consistente. Pensado para correr:
  1. Después de cualquier ALTER/DROP/VACUUM (refactores).
  2. Como último paso del actualizador semanal — si algún check falla,
     deja el log para que el cliente sepa que algo se rompió.
  3. Cuando un cliente reporta resultados raros y queremos descartar
     corrupción de la BD antes de mirar la lógica.

Checks:
  1. Existe el archivo y abre como SQLite válido.
  2. PRAGMA integrity_check (corrupción a nivel páginas).
  3. PRAGMA foreign_key_check (FKs colgantes — la BD no las usa, pero
     vale gratis).
  4. La tabla `tesis` existe y tiene registros.
  5. Schema esperado (columnas mínimas — sin `json_completo`).
  6. La tabla virtual `tesis_fts` existe.
  7. Integridad interna del índice FTS5 (`INSERT … 'integrity-check'`).
  8. Drift entre `tesis` y `tesis_fts` — mismos rowcount.
  9. Existen los 3 triggers de sincronización (insert/update/delete).
 10. Sanity check de búsqueda: una query FTS común devuelve resultados.

Output:
  ✓ check ok
  ✗ check FALLA con mensaje
  • info adicional

Exit code:
  0 si todos los checks pasaron.
  1 si al menos uno falló.

Uso:
  python scripts/validar_bd.py
  python scripts/validar_bd.py --db /ruta/alterna.db
  python scripts/validar_bd.py --json   # output máquina-friendly
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scjn_core.config import DB_PATH


# Columnas que esperamos en `tesis` después de v1.2 (sin `json_completo`).
COLUMNAS_ESPERADAS = {
    "id_tesis", "rubro", "epoca", "instancia", "organo_juris",
    "fuente", "tipo_tesis", "anio", "mes", "materias", "tesis_codigo",
    "huella_digital", "texto", "precedentes", "fecha_descarga",
}

TRIGGERS_ESPERADOS = {
    "tesis_fts_insert", "tesis_fts_update", "tesis_fts_delete",
}


# ── Acumulador de resultados ─────────────────────────────────────────────
class Reporte:
    def __init__(self):
        self.checks: list[dict] = []

    def ok(self, nombre: str, detalle: str = "") -> None:
        self.checks.append({"nombre": nombre, "estado": "ok", "detalle": detalle})

    def fallo(self, nombre: str, detalle: str) -> None:
        self.checks.append({"nombre": nombre, "estado": "fallo", "detalle": detalle})

    def info(self, nombre: str, detalle: str) -> None:
        self.checks.append({"nombre": nombre, "estado": "info", "detalle": detalle})

    @property
    def hay_fallos(self) -> bool:
        return any(c["estado"] == "fallo" for c in self.checks)

    def imprimir(self) -> None:
        for c in self.checks:
            simbolo = {"ok": "✓", "fallo": "✗", "info": "•"}[c["estado"]]
            linea = f"  {simbolo} {c['nombre']}"
            if c["detalle"]:
                linea += f" — {c['detalle']}"
            print(linea)
        print()
        if self.hay_fallos:
            n = sum(1 for c in self.checks if c["estado"] == "fallo")
            print(f"RESULTADO: {n} check(s) FALLARON ✗", file=sys.stderr)
        else:
            print("RESULTADO: todos los checks pasaron ✓")


# ── Checks individuales ──────────────────────────────────────────────────

def check_archivo(rep: Reporte, db_path: Path) -> bool:
    if not db_path.exists():
        rep.fallo("archivo existe", f"No existe {db_path}")
        return False
    rep.ok("archivo existe", f"{db_path}")
    rep.info("tamaño", f"{db_path.stat().st_size / (1024**2):.1f} MB")
    return True


def check_abre_sqlite(rep: Reporte, db_path: Path) -> sqlite3.Connection | None:
    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute("SELECT 1")
        rep.ok("abre como SQLite")
        return conn
    except sqlite3.DatabaseError as e:
        rep.fallo("abre como SQLite", str(e))
        return None


def check_integrity(rep: Reporte, conn: sqlite3.Connection) -> None:
    try:
        resultado = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if resultado == "ok":
            rep.ok("integrity_check")
        else:
            rep.fallo("integrity_check", resultado)
    except Exception as e:
        rep.fallo("integrity_check", str(e))


def check_foreign_keys(rep: Reporte, conn: sqlite3.Connection) -> None:
    try:
        problemas = conn.execute("PRAGMA foreign_key_check").fetchall()
        if not problemas:
            rep.ok("foreign_key_check")
        else:
            rep.fallo("foreign_key_check", f"{len(problemas)} fila(s) huérfanas")
    except Exception as e:
        rep.fallo("foreign_key_check", str(e))


def check_tabla_tesis(rep: Reporte, conn: sqlite3.Connection) -> int:
    try:
        n = conn.execute("SELECT COUNT(*) FROM tesis").fetchone()[0]
        if n == 0:
            rep.fallo("tabla tesis", "0 registros")
            return 0
        rep.ok("tabla tesis", f"{n:,} registros")
        return n
    except sqlite3.OperationalError as e:
        rep.fallo("tabla tesis", str(e))
        return 0


def check_schema(rep: Reporte, conn: sqlite3.Connection) -> None:
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(tesis)").fetchall()}
        faltantes = COLUMNAS_ESPERADAS - cols
        if faltantes:
            rep.fallo("schema mínimo", f"faltan columnas: {sorted(faltantes)}")
            return
        rep.ok("schema mínimo")
        if "json_completo" in cols:
            rep.info(
                "json_completo",
                "todavía presente — corre scripts/eliminar_json_completo.py --ejecutar",
            )
    except Exception as e:
        rep.fallo("schema mínimo", str(e))


def check_tabla_fts(rep: Reporte, conn: sqlite3.Connection) -> bool:
    try:
        existe = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tesis_fts'"
        ).fetchone()
        if not existe:
            rep.fallo("tesis_fts existe", "tabla no encontrada — corre install/setup_fts.py")
            return False
        rep.ok("tesis_fts existe")
        return True
    except Exception as e:
        rep.fallo("tesis_fts existe", str(e))
        return False


def check_fts_integrity(rep: Reporte, conn: sqlite3.Connection) -> None:
    try:
        # FTS5 expone un comando interno: insertar 'integrity-check' en la
        # propia tabla virtual lanza la verificación interna del índice.
        conn.execute("INSERT INTO tesis_fts(tesis_fts) VALUES('integrity-check')")
        rep.ok("FTS5 integrity-check")
    except sqlite3.DatabaseError as e:
        rep.fallo("FTS5 integrity-check", str(e))


def check_drift(rep: Reporte, conn: sqlite3.Connection, n_tesis: int) -> None:
    try:
        n_fts = conn.execute("SELECT COUNT(*) FROM tesis_fts").fetchone()[0]
        if n_fts == n_tesis:
            rep.ok("sin drift tesis ↔ tesis_fts", f"{n_fts:,} filas")
        else:
            diff = n_tesis - n_fts
            rep.fallo(
                "sin drift tesis ↔ tesis_fts",
                f"tesis={n_tesis:,} fts={n_fts:,} (diff {diff:+,})",
            )
    except Exception as e:
        rep.fallo("sin drift tesis ↔ tesis_fts", str(e))


def check_triggers(rep: Reporte, conn: sqlite3.Connection) -> None:
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        ).fetchall()
        encontrados = {r[0] for r in rows}
        faltantes = TRIGGERS_ESPERADOS - encontrados
        if faltantes:
            rep.fallo(
                "triggers de sincronización FTS",
                f"faltan: {sorted(faltantes)}",
            )
        else:
            rep.ok("triggers de sincronización FTS", "los 3 presentes")
    except Exception as e:
        rep.fallo("triggers de sincronización FTS", str(e))


def check_busqueda_real(rep: Reporte, conn: sqlite3.Connection) -> None:
    """Una búsqueda FTS común debe devolver resultados — descarta que el
    índice esté vacío aunque exista."""
    try:
        n = conn.execute(
            "SELECT COUNT(*) FROM tesis_fts WHERE tesis_fts MATCH ?",
            ["amparo"],
        ).fetchone()[0]
        if n == 0:
            rep.fallo("búsqueda FTS sanity", "0 hits para 'amparo'")
        else:
            rep.ok("búsqueda FTS sanity", f"{n:,} hits para 'amparo'")
    except Exception as e:
        rep.fallo("búsqueda FTS sanity", str(e))


# ── Main ─────────────────────────────────────────────────────────────────

def correr_checks(db_path: Path) -> Reporte:
    rep = Reporte()

    if not check_archivo(rep, db_path):
        return rep

    conn = check_abre_sqlite(rep, db_path)
    if conn is None:
        return rep

    try:
        check_integrity(rep, conn)
        check_foreign_keys(rep, conn)
        n_tesis = check_tabla_tesis(rep, conn)
        check_schema(rep, conn)

        if check_tabla_fts(rep, conn):
            check_fts_integrity(rep, conn)
            if n_tesis > 0:
                check_drift(rep, conn, n_tesis)
            check_busqueda_real(rep, conn)

        check_triggers(rep, conn)
    finally:
        conn.close()

    return rep


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Healthcheck de la BD SCJN.",
    )
    parser.add_argument(
        "--db", default=DB_PATH,
        help=f"Ruta a la BD (default: {DB_PATH})",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Imprime los resultados en JSON (para automatizaciones).",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    rep = correr_checks(db_path)

    if args.json:
        print(json.dumps({
            "db": str(db_path),
            "ok": not rep.hay_fallos,
            "checks": rep.checks,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"Validando: {db_path}\n")
        rep.imprimir()

    sys.exit(1 if rep.hay_fallos else 0)


if __name__ == "__main__":
    main()
