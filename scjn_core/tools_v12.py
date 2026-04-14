"""
Tools nuevas en v1.2: cita oficial, línea jurisprudencial, obligatorios por circuito.

Estas tres funciones añaden valor jurídico que la v1.1 no tenía:
- `extraer_cita_oficial`: pega-y-listo en escritos legales mexicanos.
- `compilar_linea_jurisprudencial`: cronología de un tema en los últimos N años.
- `buscar_obligatorios_para_circuito`: filtra por jurisprudencia obligatoria
  para un circuito específico (ej. Durango = 17º).
"""

import re
import sqlite3

from .config import get_logger
from .database import has_fts, rows_to_dicts
from .errores import humanizar
from .filters import aplicar_filtros_comunes
from .format import columnas_select, format_resultados
from .fts import build_or
from .ranking import ORDEN_VINCULANTE_SQL

logger = get_logger("scjn.tools_v12")


# ════════════════════════════════════════════════════════════════════════
# 11. Extraer cita oficial
# ════════════════════════════════════════════════════════════════════════

def extraer_cita_oficial(
    conn: sqlite3.Connection,
    identificador: str,
    campo: str = "id_tesis",
) -> str:
    """Devuelve la cita formal lista para pegar en un escrito legal.

    Formato canónico (Manual de Estilo del SJF):
        Tesis: {tesis_codigo}, {fuente}, {epoca}, {mes} de {anio},
        registro digital: {id_tesis}.

    Args:
        identificador: id_tesis o tesis_codigo de la tesis.
        campo: "id_tesis" (default) o "tesis_codigo".
    """
    try:
        if campo == "tesis_codigo":
            row = conn.execute(
                "SELECT id_tesis, rubro, tesis_codigo, fuente, epoca, anio, mes, "
                "tipo_tesis, instancia, organo_juris "
                "FROM tesis WHERE tesis_codigo = ? LIMIT 1",
                [identificador],
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id_tesis, rubro, tesis_codigo, fuente, epoca, anio, mes, "
                "tipo_tesis, instancia, organo_juris "
                "FROM tesis WHERE id_tesis = ? LIMIT 1",
                [identificador],
            ).fetchone()

        if not row:
            return f"No se encontró tesis con {campo}='{identificador}'."

        d = dict(row)
        partes = []
        if d.get("tipo_tesis"):
            partes.append(d["tipo_tesis"])
        if d.get("tesis_codigo"):
            partes.append(d["tesis_codigo"])

        cabeza = ": ".join([s for s in [", ".join(partes)] if s])

        cita = []
        if cabeza:
            cita.append(cabeza)
        if d.get("fuente"):
            cita.append(d["fuente"])
        if d.get("epoca"):
            cita.append(d["epoca"])
        if d.get("mes") and d.get("anio"):
            cita.append(f"{d['mes']} de {d['anio']}")
        elif d.get("anio"):
            cita.append(str(d["anio"]))
        if d.get("id_tesis"):
            cita.append(f"registro digital: {d['id_tesis']}")

        cita_str = ", ".join(cita) + "."

        return (
            f"Cita oficial:\n  {cita_str}\n\n"
            f"Rubro:\n  {d.get('rubro', 'N/A')}\n\n"
            f"Órgano emisor: {d.get('instancia', 'N/A')}"
            + (f" — {d['organo_juris']}" if d.get("organo_juris") else "")
        )

    except Exception as e:
        logger.error("Error en extraer_cita_oficial: %s", e)
        return humanizar(e, "extraer_cita_oficial")


# ════════════════════════════════════════════════════════════════════════
# 12. Compilar línea jurisprudencial
# ════════════════════════════════════════════════════════════════════════

def compilar_linea_jurisprudencial(
    conn: sqlite3.Connection,
    tema: list[str],
    anio_minimo: int = 2010,
    instancia: str = "",
    limite: int = 30,
) -> str:
    """Devuelve cronología de jurisprudencias sobre un tema.

    Útil para argumentar evolución del criterio. Ordena ascendente por año
    y agrupa por época. Marca cambios de etapa con separadores.

    Args:
        tema: Lista de términos alternativos del tema (ej. ["interés
              superior del menor", "interés del niño"]).
        anio_minimo: Solo jurisprudencias publicadas desde este año.
        instancia: Filtro opcional por preset de instancia.
        limite: Máximo de resultados.
    """
    if not tema:
        return "Error: proporciona al menos un término del tema."

    try:
        usa_fts = has_fts(conn)
        params: list = []

        if usa_fts:
            fts_expr = build_or(tema)
            if not fts_expr:
                return "Error: términos inválidos tras sanitizar."
            where_clauses = ["tesis_fts MATCH ?"]
            params.append(fts_expr)
            from_sql = "FROM tesis_fts JOIN tesis t ON t.rowid = tesis_fts.rowid"
        else:
            conds = []
            for t in tema:
                conds.append("(LOWER(t.texto) LIKE ? OR LOWER(t.rubro) LIKE ?)")
                params.extend([f"%{t.lower().strip()}%"] * 2)
            where_clauses = [f"({' OR '.join(conds)})"]
            from_sql = "FROM tesis t"

        # Solo jurisprudencias — la línea es de criterios obligatorios.
        where_clauses.append("LOWER(t.tipo_tesis) LIKE '%jurisprudencia%'")

        err = aplicar_filtros_comunes(
            where_clauses, params,
            solo_jurisprudencia=False,
            materia="", instancia=instancia, organo="",
            anio_minimo=anio_minimo, anio_maximo=0, epocas=[],
        )
        if err:
            return err

        query = f"""
        SELECT {columnas_select(usa_fts)}
        {from_sql}
        WHERE {' AND '.join(where_clauses)}
        ORDER BY t.anio ASC, {ORDEN_VINCULANTE_SQL}
        LIMIT ?
        """
        params.append(max(1, min(int(limite), 80)))

        cursor = conn.execute(query, params)
        rows = rows_to_dicts(cursor.fetchall())

        if not rows:
            return (
                "Sin jurisprudencias en el rango pedido. "
                "Prueba bajar `anio_minimo` o ampliar los términos."
            )

        # Agrupa por época para marcar cambios de etapa.
        partes = []
        epoca_actual = None
        for row in rows:
            ep = row.get("epoca") or "Sin época"
            if ep != epoca_actual:
                partes.append(f"\n══ {ep} ══")
                epoca_actual = ep
            partes.append(
                f"  [{row.get('anio', '?')}] "
                f"{row.get('tesis_codigo', 'N/A')} — {row.get('rubro', 'N/A')[:140]}"
            )

        encabezado = (
            f"Línea jurisprudencial — {len(rows)} criterio(s) "
            f"desde {anio_minimo}.\n"
        )
        return encabezado + "\n".join(partes)

    except Exception as e:
        logger.error("Error en compilar_linea_jurisprudencial: %s", e)
        return humanizar(e, "compilar_linea_jurisprudencial")


# ════════════════════════════════════════════════════════════════════════
# 13. Buscar obligatorios para un circuito específico
# ════════════════════════════════════════════════════════════════════════

# Mapas de circuitos: número arábigo → ordinal castellano + romano.
# Cubre los 32 circuitos federales mexicanos.
_CIRCUITOS = {
    1: ("primer", "i"), 2: ("segundo", "ii"), 3: ("tercer", "iii"),
    4: ("cuarto", "iv"), 5: ("quinto", "v"), 6: ("sexto", "vi"),
    7: ("septimo", "vii"), 8: ("octavo", "viii"), 9: ("noveno", "ix"),
    10: ("decimo", "x"), 11: ("decimo primer", "xi"),
    12: ("decimo segundo", "xii"), 13: ("decimo tercer", "xiii"),
    14: ("decimo cuarto", "xiv"), 15: ("decimo quinto", "xv"),
    16: ("decimo sexto", "xvi"), 17: ("decimo septimo", "xvii"),
    18: ("decimo octavo", "xviii"), 19: ("decimo noveno", "xix"),
    20: ("vigesimo", "xx"), 21: ("vigesimo primer", "xxi"),
    22: ("vigesimo segundo", "xxii"), 23: ("vigesimo tercer", "xxiii"),
    24: ("vigesimo cuarto", "xxiv"), 25: ("vigesimo quinto", "xxv"),
    26: ("vigesimo sexto", "xxvi"), 27: ("vigesimo septimo", "xxvii"),
    28: ("vigesimo octavo", "xxviii"), 29: ("vigesimo noveno", "xxix"),
    30: ("trigesimo", "xxx"), 31: ("trigesimo primer", "xxxi"),
    32: ("trigesimo segundo", "xxxii"),
}

# Romanos arábigos (entrada del usuario)
_ROMANOS = {v[1]: k for k, v in _CIRCUITOS.items()}


def _parse_circuito(entrada) -> int | None:
    """Acepta 17, '17', 'XVII', 'xvii', 'decimo septimo' → 17."""
    if isinstance(entrada, int):
        return entrada if 1 <= entrada <= 32 else None
    if not isinstance(entrada, str) or not entrada.strip():
        return None
    s = entrada.strip().lower()
    if s.isdigit():
        n = int(s)
        return n if 1 <= n <= 32 else None
    if s in _ROMANOS:
        return _ROMANOS[s]
    # Match ordinal castellano (sin acentos). Ordenamos por longitud
    # descendente para que "decimo septimo" gane sobre "decimo".
    s_norm = (
        s.replace("á", "a").replace("é", "e").replace("í", "i")
        .replace("ó", "o").replace("ú", "u")
    )
    ordenados = sorted(_CIRCUITOS.items(), key=lambda kv: -len(kv[1][0]))
    for num, (ordinal, _) in ordenados:
        if s_norm.startswith(ordinal):
            return num
    return None


def buscar_obligatorios_para_circuito(
    conn: sqlite3.Connection,
    circuito,
    terminos: list[str],
    limite: int = 30,
) -> str:
    """Devuelve jurisprudencia obligatoria para el circuito dado.

    Para un abogado en el 17º circuito (Durango), el universo de
    criterios obligatorios incluye:
        - Pleno SCJN
        - Salas SCJN
        - Plenos Regionales que cubran el circuito (no se filtran porque
          la BD no codifica la región del circuito)
        - Plenos del propio circuito
        - TCCs del propio circuito

    Args:
        circuito: Número del circuito (int 1-32, o "XVII", o "decimo septimo").
        terminos: Lista de términos del tema.
        limite: Máximo de resultados.
    """
    n = _parse_circuito(circuito)
    if n is None:
        return (
            f"Circuito '{circuito}' no reconocido. "
            f"Usa un número (1-32), un romano (XVII) o el ordinal en castellano."
        )

    if not terminos:
        return "Error: proporciona al menos un término."

    try:
        ordinal, romano = _CIRCUITOS[n]
        # Variantes de cómo aparece el circuito en organo_juris:
        # "Décimo Séptimo Circuito", "XVII Circuito", "Pleno del Decimoséptimo Circuito"
        # Construimos LIKEs flexibles.
        variantes = [
            f"%{ordinal.replace(' ', '')}%circuito%",
            f"%{ordinal}%circuito%",
            f"%{romano} circuito%",
            f"%{romano}.%circuito%",
        ]
        like_circuito = " OR ".join(["LOWER(t.organo_juris) LIKE ?"] * len(variantes))

        usa_fts = has_fts(conn)
        params: list = []

        if usa_fts:
            fts_expr = build_or(terminos)
            if not fts_expr:
                return "Error: términos inválidos tras sanitizar."
            where_clauses = ["tesis_fts MATCH ?"]
            params.append(fts_expr)
            from_sql = "FROM tesis_fts JOIN tesis t ON t.rowid = tesis_fts.rowid"
        else:
            conds = []
            for t in terminos:
                conds.append("(LOWER(t.texto) LIKE ? OR LOWER(t.rubro) LIKE ?)")
                params.extend([f"%{t.lower().strip()}%"] * 2)
            where_clauses = [f"({' OR '.join(conds)})"]
            from_sql = "FROM tesis t"

        # Universo obligatorio para este circuito:
        #   - Toda jurisprudencia de Pleno SCJN o Salas SCJN
        #   - Todos los plenos regionales (sin filtro de región — la BD
        #     no codifica qué circuito cae en qué región)
        #   - Plenos de circuito y TCCs del circuito específico
        condicion_universo = f"""
            (
                LOWER(t.tipo_tesis) LIKE '%jurisprudencia%'
                AND (
                    (t.instancia = 'Suprema Corte de Justicia de la Nación')
                    OR LOWER(t.instancia) LIKE '%plenos regionales%'
                    OR (
                        (LOWER(t.instancia) LIKE '%plenos de circuito%'
                         OR LOWER(t.instancia) LIKE '%tribunales colegiados%')
                        AND ({like_circuito})
                    )
                )
            )
        """
        where_clauses.append(condicion_universo)
        params.extend(variantes)

        query = f"""
        SELECT {columnas_select(usa_fts)}
        {from_sql}
        WHERE {' AND '.join(where_clauses)}
        ORDER BY {ORDEN_VINCULANTE_SQL}{', rank_score ASC' if usa_fts else ''}, t.anio DESC
        LIMIT ?
        """
        params.append(max(1, min(int(limite), 100)))

        cursor = conn.execute(query, params)
        rows = rows_to_dicts(cursor.fetchall())

        encabezado = (
            f"Jurisprudencia obligatoria para el {ordinal} circuito "
            f"({romano.upper()}): {len(rows)} criterio(s).\n\n"
        )
        return encabezado + format_resultados(rows)

    except Exception as e:
        logger.error("Error en buscar_obligatorios_para_circuito: %s", e)
        return humanizar(e, "buscar_obligatorios_para_circuito")
