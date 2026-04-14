"""
Funciones puras de búsqueda — el motor del producto.

Cada función recibe una conexión SQLite ya abierta como primer argumento.
Devuelven string formateado (listo para que el LLM lo lea). El server MCP
y el CLI standalone son wrappers delgados sobre estas funciones.

Diseño:
- Cero estado global (excepto el cache de FTS5 en `database`).
- Cero acoplamiento al MCP — estas funciones son testeables con pytest
  contra una BD real o una BD de fixture.
- Manejo de errores: capturan sqlite3.OperationalError y devuelven texto
  legible. NO levantan excepciones al caller.
"""

import re
import sqlite3  # noqa: F401  (usado por type hints conn: sqlite3.Connection)

from .config import get_logger
from .database import has_fts, rows_to_dicts
from .errores import humanizar
from .filters import aplicar_filtros_comunes
from .format import columnas_select, format_resultados
from .fts import build_or, sanitize
from .ranking import ORDEN_VINCULANTE_SQL, build_order_by

logger = get_logger("scjn.search")


# ════════════════════════════════════════════════════════════════════════
# 1. Búsqueda conceptual (OR de sinónimos)
# ════════════════════════════════════════════════════════════════════════

def buscar_jurisprudencia(
    conn: sqlite3.Connection,
    terminos: list[str],
    solo_jurisprudencia: bool = False,
    materia: str = "",
    instancia: str = "",
    organo: str = "",
    anio_minimo: int = 0,
    anio_maximo: int = 0,
    epocas: list[str] | None = None,
    buscar_en: str = "todo",
    orden: str = "vinculancia",
    limite: int = 25,
) -> str:
    """Busca tesis y jurisprudencia con OR de sinónimos + filtros."""
    if not terminos:
        return "Error: Debes proporcionar al menos un termino de busqueda."

    epocas = epocas or []
    try:
        params: list = []
        usa_fts = has_fts(conn)

        if usa_fts:
            fts_expr = build_or(terminos)
            if not fts_expr:
                return "Error: Terminos invalidos tras sanitizar."

            # Búsqueda por columna específica (rubro/texto) si se pide
            if buscar_en == "rubro":
                fts_expr = "rubro : " + fts_expr.replace(" OR ", " OR rubro : ")
            elif buscar_en == "texto":
                fts_expr = "texto : " + fts_expr.replace(" OR ", " OR texto : ")

            where_clauses = ["tesis_fts MATCH ?"]
            params.append(fts_expr)
            from_sql = (
                "FROM tesis_fts "
                "JOIN tesis t ON t.rowid = tesis_fts.rowid"
            )
        else:
            conds = []
            for term in terminos:
                t_lower = term.lower().strip()
                if buscar_en == "rubro":
                    conds.append("LOWER(t.rubro) LIKE ?")
                    params.append(f"%{t_lower}%")
                elif buscar_en == "texto":
                    conds.append("LOWER(t.texto) LIKE ?")
                    params.append(f"%{t_lower}%")
                else:
                    conds.append("(LOWER(t.texto) LIKE ? OR LOWER(t.rubro) LIKE ?)")
                    params.extend([f"%{t_lower}%", f"%{t_lower}%"])
            where_clauses = [f"({' OR '.join(conds)})"]
            from_sql = "FROM tesis t"

        err = aplicar_filtros_comunes(
            where_clauses, params,
            solo_jurisprudencia=solo_jurisprudencia,
            materia=materia, instancia=instancia, organo=organo,
            anio_minimo=anio_minimo, anio_maximo=anio_maximo,
            epocas=epocas,
        )
        if err:
            return err

        query = f"""
        SELECT {columnas_select(usa_fts)}
        {from_sql}
        WHERE {' AND '.join(where_clauses)}
        ORDER BY {build_order_by(orden, usa_fts)}
        LIMIT ?
        """
        params.append(max(1, min(int(limite), 100)))

        cursor = conn.execute(query, params)
        rows = rows_to_dicts(cursor.fetchall())

        logger.info(
            "buscar_jurisprudencia: %d resultados para %d terminos (FTS=%s, orden=%s)",
            len(rows), len(terminos), "si" if usa_fts else "no", orden,
        )
        return format_resultados(rows)

    except Exception as e:
        logger.error("Error en buscar_jurisprudencia: %s", e)
        return humanizar(e, "buscar_jurisprudencia")


# ════════════════════════════════════════════════════════════════════════
# 2. Búsqueda interseccional (A AND B [AND C])
# ════════════════════════════════════════════════════════════════════════

def buscar_interseccion(
    conn: sqlite3.Connection,
    concepto_a: list[str],
    concepto_b: list[str],
    concepto_c: list[str] | None = None,
    solo_jurisprudencia: bool = False,
    materia: str = "",
    instancia: str = "",
    organo: str = "",
    anio_minimo: int = 0,
    anio_maximo: int = 0,
    epocas: list[str] | None = None,
    orden: str = "vinculancia",
    limite: int = 25,
) -> str:
    """Cruza 2-3 conceptos (AND) con sinónimos por concepto (OR)."""
    if not concepto_a or not concepto_b:
        return "Error: concepto_a y concepto_b deben tener al menos un termino."

    epocas = epocas or []
    try:
        params: list = []
        usa_fts = has_fts(conn)

        grupos = [concepto_a, concepto_b]
        if concepto_c:
            grupos.append(concepto_c)

        if usa_fts:
            partes_fts = []
            for grupo in grupos:
                sub = build_or(grupo)
                if not sub:
                    return "Error: Terminos invalidos en uno de los conceptos."
                partes_fts.append(f"({sub})")
            fts_expr = " AND ".join(partes_fts)

            where_clauses = ["tesis_fts MATCH ?"]
            params.append(fts_expr)
            from_sql = "FROM tesis_fts JOIN tesis t ON t.rowid = tesis_fts.rowid"
        else:
            where_clauses = []
            for grupo in grupos:
                conds = []
                for t in grupo:
                    conds.append("(LOWER(t.texto) LIKE ? OR LOWER(t.rubro) LIKE ?)")
                    params.extend([f"%{t.lower().strip()}%"] * 2)
                where_clauses.append(f"({' OR '.join(conds)})")
            from_sql = "FROM tesis t"

        err = aplicar_filtros_comunes(
            where_clauses, params,
            solo_jurisprudencia=solo_jurisprudencia,
            materia=materia, instancia=instancia, organo=organo,
            anio_minimo=anio_minimo, anio_maximo=anio_maximo,
            epocas=epocas,
        )
        if err:
            return err

        query = f"""
        SELECT {columnas_select(usa_fts)}
        {from_sql}
        WHERE {' AND '.join(where_clauses)}
        ORDER BY {build_order_by(orden, usa_fts)}
        LIMIT ?
        """
        params.append(max(1, min(int(limite), 100)))

        cursor = conn.execute(query, params)
        rows = rows_to_dicts(cursor.fetchall())

        logger.info(
            "buscar_interseccion: %d resultados (%d conceptos)",
            len(rows), len(grupos),
        )
        return format_resultados(rows)

    except Exception as e:
        logger.error("Error en buscar_interseccion: %s", e)
        return humanizar(e, "buscar_interseccion")


# ════════════════════════════════════════════════════════════════════════
# 3. Búsqueda por proximidad (NEAR)
# ════════════════════════════════════════════════════════════════════════

def buscar_proximidad(
    conn: sqlite3.Connection,
    termino_a: str,
    termino_b: str,
    distancia: int = 15,
    solo_jurisprudencia: bool = False,
    materia: str = "",
    instancia: str = "",
    anio_minimo: int = 0,
    limite: int = 25,
) -> str:
    """Encuentra tesis donde dos términos aparecen dentro de N tokens."""
    if not termino_a or not termino_b:
        return "Error: Debes proporcionar ambos terminos."

    try:
        usa_fts = has_fts(conn)
        if not usa_fts:
            return (
                "buscar_proximidad requiere FTS5 activo. "
                "Contacta al instalador para reconstruir el indice."
            )

        a = sanitize(termino_a)
        b = sanitize(termino_b)
        if not a or not b:
            return "Error: Terminos invalidos tras sanitizar."

        fts_expr = f"NEAR({a} {b}, {max(1, min(int(distancia), 100))})"
        params: list = [fts_expr]

        where_clauses = ["tesis_fts MATCH ?"]
        err = aplicar_filtros_comunes(
            where_clauses, params,
            solo_jurisprudencia=solo_jurisprudencia,
            materia=materia, instancia=instancia, organo="",
            anio_minimo=anio_minimo, anio_maximo=0, epocas=[],
        )
        if err:
            return err

        query = f"""
        SELECT {columnas_select(True)}
        FROM tesis_fts JOIN tesis t ON t.rowid = tesis_fts.rowid
        WHERE {' AND '.join(where_clauses)}
        ORDER BY {build_order_by('vinculancia', True)}
        LIMIT ?
        """
        params.append(max(1, min(int(limite), 100)))

        cursor = conn.execute(query, params)
        rows = rows_to_dicts(cursor.fetchall())

        logger.info("buscar_proximidad: %d resultados (distancia %d)", len(rows), distancia)
        return format_resultados(rows)

    except Exception as e:
        logger.error("Error en buscar_proximidad: %s", e)
        return humanizar(e, "buscar_proximidad")


# ════════════════════════════════════════════════════════════════════════
# 4. Búsqueda por rubro (alias de buscar_jurisprudencia con buscar_en="rubro")
# ════════════════════════════════════════════════════════════════════════

def buscar_rubro(
    conn: sqlite3.Connection,
    terminos: list[str],
    solo_jurisprudencia: bool = False,
    materia: str = "",
    instancia: str = "",
    anio_minimo: int = 0,
    limite: int = 25,
) -> str:
    """Busca solo en los rubros (títulos). Más preciso, casi sin falsos positivos."""
    return buscar_jurisprudencia(
        conn,
        terminos=terminos,
        solo_jurisprudencia=solo_jurisprudencia,
        materia=materia,
        instancia=instancia,
        anio_minimo=anio_minimo,
        buscar_en="rubro",
        limite=limite,
    )


# ════════════════════════════════════════════════════════════════════════
# 5. Lectura completa de una tesis
# ════════════════════════════════════════════════════════════════════════

def leer_tesis_completa(
    conn: sqlite3.Connection,
    identificador: str,
    campo: str = "id_tesis",
) -> str:
    """Lee texto completo + metadatos de UNA tesis (o pocas, si campo=rubro)."""
    try:
        campos_select = """
            rubro, texto, precedentes, tipo_tesis, instancia,
            organo_juris, epoca, anio, tesis_codigo, materias, fuente, id_tesis
        """

        if campo == "rubro":
            query = f"SELECT {campos_select} FROM tesis WHERE LOWER(rubro) LIKE ? LIMIT 5"
            params = [f"%{identificador.lower()}%"]
        elif campo == "tesis_codigo":
            query = f"SELECT {campos_select} FROM tesis WHERE tesis_codigo LIKE ? LIMIT 5"
            params = [f"%{identificador}%"]
        else:
            query = f"SELECT {campos_select} FROM tesis WHERE id_tesis = ? LIMIT 1"
            params = [identificador]

        cursor = conn.execute(query, params)
        rows = rows_to_dicts(cursor.fetchall())

        if not rows:
            return f"No se encontro tesis con {campo} = '{identificador}'"

        return format_resultados(rows, incluir_texto=True)

    except Exception as e:
        logger.error("Error en leer_tesis_completa: %s", e)
        return humanizar(e, "leer_tesis_completa")


# ════════════════════════════════════════════════════════════════════════
# 6. Lectura batch de varias tesis
# ════════════════════════════════════════════════════════════════════════

def leer_varias_tesis(
    conn: sqlite3.Connection,
    identificadores: list[str],
    campo: str = "id_tesis",
) -> str:
    """Lee hasta 15 tesis en una sola query (batch)."""
    if not identificadores:
        return "Error: Proporciona al menos un identificador."

    ids = [str(i).strip() for i in identificadores if str(i).strip()][:15]
    if not ids:
        return "Error: Identificadores invalidos."

    try:
        placeholders = ",".join(["?"] * len(ids))
        columna = "tesis_codigo" if campo == "tesis_codigo" else "id_tesis"
        query = f"""
        SELECT rubro, texto, precedentes, tipo_tesis, instancia,
               organo_juris, epoca, anio, tesis_codigo, materias, fuente, id_tesis
        FROM tesis
        WHERE {columna} IN ({placeholders})
        ORDER BY {ORDEN_VINCULANTE_SQL.replace('t.', '')}, anio DESC
        """

        cursor = conn.execute(query, ids)
        rows = rows_to_dicts(cursor.fetchall())

        if not rows:
            return f"No se encontro ninguna tesis con los identificadores dados."

        logger.info("leer_varias_tesis: %d/%d encontradas", len(rows), len(ids))
        return format_resultados(rows, incluir_texto=True)

    except Exception as e:
        logger.error("Error en leer_varias_tesis: %s", e)
        return humanizar(e, "leer_varias_tesis")


# ════════════════════════════════════════════════════════════════════════
# 7. Búsqueda por contradicción de tesis
# ════════════════════════════════════════════════════════════════════════

def buscar_contradiccion(
    conn: sqlite3.Connection,
    terminos: list[str],
    instancia: str = "",
    anio_minimo: int = 0,
    limite: int = 20,
) -> str:
    """Jurisprudencias surgidas de contradicción de tesis/criterios."""
    if not terminos:
        return "Error: Proporciona al menos un termino."

    try:
        usa_fts = has_fts(conn)
        params: list = []

        if usa_fts:
            fts_terminos = build_or(terminos)
            if not fts_terminos:
                return "Error: Terminos invalidos."
            # Buscar los terminos Y una mencion a contradiccion (en cualquier
            # columna indexada: rubro, texto, precedentes).
            fts_expr = (
                f"({fts_terminos}) AND "
                f'("contradiccion de tesis" OR "contradiccion de criterios")'
            )
            where_clauses = ["tesis_fts MATCH ?"]
            params.append(fts_expr)
            from_sql = "FROM tesis_fts JOIN tesis t ON t.rowid = tesis_fts.rowid"
        else:
            conds = []
            for t in terminos:
                conds.append("(LOWER(t.texto) LIKE ? OR LOWER(t.rubro) LIKE ?)")
                params.extend([f"%{t.lower().strip()}%", f"%{t.lower().strip()}%"])
            where_clauses = [
                f"({' OR '.join(conds)})",
                "(LOWER(t.precedentes) LIKE '%contradicci%de tesis%'"
                " OR LOWER(t.rubro) LIKE '%contradicci%de tesis%'"
                " OR LOWER(t.texto) LIKE '%contradicci%de tesis%')",
            ]
            from_sql = "FROM tesis t"

        # Solo jurisprudencias
        where_clauses.append("LOWER(t.tipo_tesis) LIKE '%jurisprudencia%'")

        err = aplicar_filtros_comunes(
            where_clauses, params,
            solo_jurisprudencia=False,  # ya lo agregamos arriba
            materia="", instancia=instancia, organo="",
            anio_minimo=anio_minimo, anio_maximo=0, epocas=[],
        )
        if err:
            return err

        query = f"""
        SELECT {columnas_select(usa_fts)}
        {from_sql}
        WHERE {' AND '.join(where_clauses)}
        ORDER BY {build_order_by('vinculancia', usa_fts)}
        LIMIT ?
        """
        params.append(max(1, min(int(limite), 100)))

        cursor = conn.execute(query, params)
        rows = rows_to_dicts(cursor.fetchall())

        logger.info("buscar_contradiccion: %d resultados", len(rows))
        return format_resultados(rows)

    except Exception as e:
        logger.error("Error en buscar_contradiccion: %s", e)
        return humanizar(e, "buscar_contradiccion")


# ════════════════════════════════════════════════════════════════════════
# 8. Buscar tesis similares a una dada
# ════════════════════════════════════════════════════════════════════════

# Stop-words castellanas comunes que no aportan al match BM25
_STOP_WORDS = {
    "para", "como", "esta", "este", "esto", "sobre", "entre", "hacia",
    "desde", "cuando", "donde", "porque", "segun", "ante", "bajo",
    "contra", "por", "con", "sin", "del", "las", "los", "una",
    "uno", "que", "sus", "ser", "son", "haya", "hay",
}


def buscar_similares(
    conn: sqlite3.Connection,
    id_tesis: str,
    limite: int = 15,
    solo_jurisprudencia: bool = False,
) -> str:
    """Encuentra tesis con rubros similares a una tesis dada (BM25)."""
    try:
        if not has_fts(conn):
            return (
                "buscar_similares requiere FTS5 activo. "
                "Contacta al instalador."
            )

        ref = conn.execute(
            "SELECT rubro, tesis_codigo FROM tesis WHERE id_tesis = ?",
            [id_tesis],
        ).fetchone()
        if not ref or not ref["rubro"]:
            return f"No se encontro tesis de referencia con id_tesis='{id_tesis}'."

        rubro = ref["rubro"]
        # Extrae las palabras clave del rubro (toma hasta 8 palabras
        # de 4+ caracteres, ignorando stop-words muy comunes).
        palabras = [
            w for w in re.findall(r"\w+", rubro.lower())
            if len(w) >= 4 and w not in _STOP_WORDS
        ][:8]

        if not palabras:
            return "No se pudieron extraer palabras clave del rubro."

        # OR de palabras como términos unicos (no frases)
        fts_expr = " OR ".join(palabras)

        where_clauses = ["tesis_fts MATCH ?", "t.id_tesis != ?"]
        params: list = [fts_expr, id_tesis]

        if solo_jurisprudencia:
            where_clauses.append("LOWER(t.tipo_tesis) LIKE '%jurisprudencia%'")

        query = f"""
        SELECT {columnas_select(True)}
        FROM tesis_fts JOIN tesis t ON t.rowid = tesis_fts.rowid
        WHERE {' AND '.join(where_clauses)}
        ORDER BY rank_score ASC, {ORDEN_VINCULANTE_SQL}
        LIMIT ?
        """
        params.append(max(1, min(int(limite), 50)))

        cursor = conn.execute(query, params)
        rows = rows_to_dicts(cursor.fetchall())

        if not rows:
            return "No se encontraron tesis similares."

        encabezado = (
            f"Tesis similares a: {rubro[:100]}...\n"
            f"(Codigo referencia: {ref['tesis_codigo']})\n\n"
        )
        return encabezado + format_resultados(rows)

    except Exception as e:
        logger.error("Error en buscar_similares: %s", e)
        return humanizar(e, "buscar_similares")


# ════════════════════════════════════════════════════════════════════════
# 9. Explorar valores de la BD
# ════════════════════════════════════════════════════════════════════════

_CAMPOS_EXPLORABLES = {
    "tipo_tesis", "epoca", "instancia", "materias",
    "organo_juris", "fuente",
}


def explorar_valores(
    conn: sqlite3.Connection,
    campo: str,
    limite: int = 30,
) -> str:
    """Devuelve los valores únicos de un campo con su frecuencia."""
    if campo not in _CAMPOS_EXPLORABLES:
        return (
            f"Campo no permitido: '{campo}'. "
            f"Usa uno de: {', '.join(sorted(_CAMPOS_EXPLORABLES))}"
        )

    try:
        cursor = conn.execute(
            f"SELECT DISTINCT {campo}, COUNT(*) as total "
            f"FROM tesis WHERE {campo} IS NOT NULL AND {campo} != '' "
            f"GROUP BY {campo} ORDER BY total DESC LIMIT ?",
            [limite],
        )
        rows = cursor.fetchall()

        resultado = f"Valores unicos en '{campo}' (top {len(rows)}):\n\n"
        for row in rows:
            resultado += f"  - {row[0]}  ({row[1]:,} tesis)\n"

        return resultado

    except Exception as e:
        logger.error("Error en explorar_valores: %s", e)
        return humanizar(e, "explorar_valores")


# ════════════════════════════════════════════════════════════════════════
# 10. Info de la base de datos
# ════════════════════════════════════════════════════════════════════════

def info_base_datos(
    conn: sqlite3.Connection,
    version: str | None = None,
    log_path: str | None = None,
) -> str:
    """Estadísticas y estado de la BD: totales, rangos, desgloses, FTS5."""
    try:
        total = conn.execute("SELECT COUNT(*) FROM tesis").fetchone()[0]

        row = conn.execute(
            "SELECT MIN(anio), MAX(anio) FROM tesis WHERE anio > 0"
        ).fetchone()
        anio_min, anio_max = row[0], row[1]

        por_tipo = conn.execute(
            "SELECT tipo_tesis, COUNT(*) FROM tesis "
            "GROUP BY tipo_tesis ORDER BY COUNT(*) DESC"
        ).fetchall()

        por_epoca = conn.execute(
            "SELECT epoca, COUNT(*) FROM tesis "
            "WHERE epoca IS NOT NULL AND epoca != '' "
            "GROUP BY epoca ORDER BY COUNT(*) DESC"
        ).fetchall()

        por_instancia = conn.execute(
            "SELECT instancia, COUNT(*) FROM tesis "
            "WHERE instancia IS NOT NULL AND instancia != '' "
            "GROUP BY instancia ORDER BY COUNT(*) DESC"
        ).fetchall()

        ultima = conn.execute(
            "SELECT MAX(fecha_descarga) FROM tesis"
        ).fetchone()[0]

        fts_status = (
            "Activo (busquedas rapidas)" if has_fts(conn)
            else "No disponible (busquedas lentas)"
        )

        resultado = [
            "=== Estado de la Base de Datos SCJN ===",
            f"Version del producto: {version or 'desconocida'}",
            f"Total de criterios: {total:,}",
            f"Rango temporal: {anio_min} - {anio_max}",
            f"Ultima descarga: {ultima or 'No registrada'}",
            f"Indice FTS5: {fts_status}",
            "",
            "Desglose por tipo:",
        ]
        for tipo, count in por_tipo:
            resultado.append(f"  - {tipo}: {count:,}")

        resultado.append("")
        resultado.append("Desglose por instancia (fuerza vinculante):")
        for inst, count in por_instancia:
            resultado.append(f"  - {inst}: {count:,}")

        resultado.append("")
        resultado.append("Desglose por epoca:")
        for epoca, count in por_epoca[:12]:
            resultado.append(f"  - {epoca}: {count:,}")

        if log_path:
            from pathlib import Path
            log_file = Path(log_path)
            if log_file.exists():
                try:
                    log_content = log_file.read_text(encoding="utf-8").strip()
                    resultado.append(f"\nUltima actualizacion automatica:\n{log_content}")
                except Exception:
                    pass

        return "\n".join(resultado)

    except Exception as e:
        logger.error("Error en info_base_datos: %s", e)
        return humanizar(e, "info_base_datos")
