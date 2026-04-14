"""
Elimina la columna `json_completo` de la tabla `tesis` y compacta la BD.

Por qué:
- La columna guarda el JSON original de la API SCJN como string.
- Pesa ~612 MB de los 1.7 GB de la BD.
- En runtime nadie la lee — se decidió en v1.0 conservarla "por si acaso",
  pero el "por si acaso" no llegó.
- Quitándola, la BD queda en ~1.07 GB → distribución más fácil, FTS5 más
  rápido en cache.

Si alguna vez se necesita el JSON original, se puede regenerar desde la API
con el id_tesis.

Uso:
    python scripts/eliminar_json_completo.py [--ejecutar]

Sin --ejecutar imprime un dry-run con los tamaños esperados. Con --ejecutar
hace backup, ALTER TABLE DROP COLUMN, VACUUM, y reporta el ahorro real.
"""

import argparse
import shutil
import sqlite3
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scjn_core.config import DB_PATH


def humano(bytes_: int) -> str:
    for unidad in ("B", "KB", "MB", "GB"):
        if bytes_ < 1024:
            return f"{bytes_:.1f} {unidad}"
        bytes_ /= 1024
    return f"{bytes_:.1f} TB"


def medir_columna(conn: sqlite3.Connection, col: str) -> int:
    """Tamaño total (en bytes) de los strings de una columna."""
    return conn.execute(f"SELECT SUM(length({col})) FROM tesis").fetchone()[0] or 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ejecutar", action="store_true",
        help="Ejecuta el ALTER TABLE + VACUUM (sin esto solo dry-run).",
    )
    parser.add_argument(
        "--db", default=DB_PATH,
        help=f"Ruta a la BD (default: {DB_PATH})",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: No existe la BD en {db_path}", file=sys.stderr)
        sys.exit(1)

    tamaño_inicial = db_path.stat().st_size
    print(f"BD: {db_path}")
    print(f"Tamaño actual: {humano(tamaño_inicial)}")

    conn = sqlite3.connect(str(db_path))
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(tesis)").fetchall()]
        if "json_completo" not in cols:
            print("La columna `json_completo` ya no existe. Nada que hacer.")
            return

        peso_json = medir_columna(conn, "json_completo")
        peso_texto = medir_columna(conn, "texto")
        print(f"Peso `json_completo` (suma de strings): {humano(peso_json)}")
        print(f"Peso `texto` (referencia): {humano(peso_texto)}")
        ahorro_estimado = peso_json
        print(f"\nAhorro estimado tras VACUUM: ~{humano(ahorro_estimado)}")

        if not args.ejecutar:
            print("\n[DRY RUN] Re-ejecuta con --ejecutar para aplicar.")
            return

        # ── BACKUP ─────────────────────────────────────────────────
        backup_path = db_path.with_suffix(".db.bak_pre_v1.2")
        print(f"\n→ Backup → {backup_path}")
        shutil.copy2(db_path, backup_path)
        print(f"  backup creado: {humano(backup_path.stat().st_size)}")

        # ── ALTER ──────────────────────────────────────────────────
        print("\n→ ALTER TABLE tesis DROP COLUMN json_completo …")
        t0 = time.time()
        conn.execute("ALTER TABLE tesis DROP COLUMN json_completo")
        conn.commit()
        print(f"  OK en {time.time() - t0:.1f}s")

        # ── VACUUM ─────────────────────────────────────────────────
        print("\n→ VACUUM (puede tardar varios minutos en una BD de ~1.7 GB) …")
        t0 = time.time()
        conn.execute("VACUUM")
        conn.commit()
        print(f"  OK en {time.time() - t0:.1f}s")
    finally:
        conn.close()

    tamaño_final = db_path.stat().st_size
    print(f"\nTamaño final: {humano(tamaño_final)}")
    print(f"Ahorro real: {humano(tamaño_inicial - tamaño_final)}")
    print(f"Backup conservado en: {backup_path}")
    print("\nNo olvides:")
    print("  - Validar con `pytest tests/`")
    print("  - Si todo funciona, puedes borrar el backup.")


if __name__ == "__main__":
    main()
