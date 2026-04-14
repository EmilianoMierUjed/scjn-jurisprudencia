"""
Baseline v1.1 → v1.2 — captura el output exacto de queries representativas
para detectar regresiones del refactor.

Uso:
    # 1) Antes del refactor (con server.py monolítico todavía vigente):
    python scripts/baseline_v1_1.py --antes > baseline_antes.txt

    # 2) Después del refactor (cuando server.py ya es wrapper de scjn_core):
    python scripts/baseline_v1_1.py --despues > baseline_despues.txt

    # 3) Diff:
    diff baseline_antes.txt baseline_despues.txt
    # Debe ser vacío.

`--antes` importa funciones directamente desde server/server.py (la versión
monolítica). `--despues` importa de scjn_core.search.
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


# Las queries son determinísticas: mismos términos, mismos filtros, misma BD.
# Cubren el ranking vinculante (ese fue el bug v1.0), filtros de época con
# acentos, intersección de 3 conceptos, NEAR, contradicción y exploración.
QUERIES = [
    {
        "nombre": "1-derecho-salud-issste",
        "tool": "buscar_jurisprudencia",
        "kwargs": {
            "terminos": ["derecho a la salud", "proteccion de la salud"],
            "limite": 10,
        },
    },
    {
        "nombre": "2-despido-prueba-interseccion",
        "tool": "buscar_interseccion",
        "kwargs": {
            "concepto_a": ["despido injustificado", "despido sin causa"],
            "concepto_b": ["carga de la prueba"],
            "limite": 10,
        },
    },
    {
        "nombre": "3-pleno-scjn-amparo",
        "tool": "buscar_jurisprudencia",
        "kwargs": {
            "terminos": ["amparo directo", "amparo indirecto"],
            "instancia": "pleno_scjn",
            "limite": 5,
        },
    },
    {
        "nombre": "4-epoca-decima-acentos",
        "tool": "buscar_jurisprudencia",
        "kwargs": {
            "terminos": ["interes superior del menor"],
            "epocas": ["decima"],
            "limite": 5,
        },
    },
    {
        "nombre": "5-buscar-rubro",
        "tool": "buscar_rubro",
        "kwargs": {
            "terminos": ["pension alimenticia"],
            "limite": 5,
        },
    },
    {
        "nombre": "6-proximidad-near",
        "tool": "buscar_proximidad",
        "kwargs": {
            "termino_a": "despido",
            "termino_b": "carga de la prueba",
            "distancia": 20,
            "limite": 5,
        },
    },
    {
        "nombre": "7-contradiccion",
        "tool": "buscar_contradiccion",
        "kwargs": {
            "terminos": ["pension alimenticia"],
            "limite": 5,
        },
    },
    {
        "nombre": "8-explorar-instancia",
        "tool": "explorar_valores",
        "kwargs": {"campo": "instancia", "limite": 10},
    },
    {
        "nombre": "9-info-base",
        "tool": "info_base_datos",
        "kwargs": {},
    },
]


def correr_antes() -> None:
    """Importa server/server.py y llama directamente a las @mcp.tool funciones."""
    sys.path.insert(0, str(REPO_ROOT / "server"))
    import server as srv

    for q in QUERIES:
        print(f"\n========== {q['nombre']} ==========")
        fn = getattr(srv, q["tool"])
        try:
            print(fn(**q["kwargs"]))
        except Exception as e:
            print(f"ERROR: {e}")


def correr_despues() -> None:
    """Importa scjn_core y llama a search.* con conn."""
    from scjn_core import database, search
    from scjn_core.config import DB_PATH

    # Lee VERSION/log_path para que info_base_datos coincida con el monolito,
    # que también los leía del filesystem.
    version_path = REPO_ROOT / "VERSION"
    version = version_path.read_text(encoding="utf-8").strip() if version_path.exists() else "desconocida"
    log_path = str(Path(DB_PATH).parent / "ultimo_update.log")

    conn = database.connect()
    try:
        for q in QUERIES:
            print(f"\n========== {q['nombre']} ==========")
            fn = getattr(search, q["tool"])
            kwargs = dict(q["kwargs"])
            # info_base_datos necesita los extras que el wrapper le inyecta
            if q["tool"] == "info_base_datos":
                kwargs["version"] = version
                kwargs["log_path"] = log_path
            try:
                print(fn(conn, **kwargs))
            except Exception as e:
                print(f"ERROR: {e}")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--antes", action="store_true", help="Usa server/server.py monolítico")
    grupo.add_argument("--despues", action="store_true", help="Usa scjn_core")
    args = parser.parse_args()

    if args.antes:
        correr_antes()
    else:
        correr_despues()


if __name__ == "__main__":
    main()
