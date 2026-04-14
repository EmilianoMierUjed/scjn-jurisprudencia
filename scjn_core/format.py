"""
Formato de output que entiende el LLM (texto plano estructurado).

Tanto el MCP server como el CLI standalone serializan los rows de SQLite
con `format_resultados`. El formato es estable: cualquier cambio aquí
afecta la calidad del razonamiento del LLM aguas abajo.
"""

from .config import MAX_EXTRACTO, MAX_TEXTO_COMPLETO
from .ranking import nivel_vinculante


def columnas_select(usa_fts: bool) -> str:
    """Devuelve el SELECT canónico de columnas para listar resultados.

    Cuando hay FTS5, añade snippet (con ráfagas marcadas con «»), bm25 y
    también el extracto plano (por si el snippet falla en algún caso).
    """
    cols = [
        "t.id_tesis", "t.rubro", "t.tipo_tesis", "t.instancia",
        "t.organo_juris", "t.epoca", "t.anio", "t.materias",
        "t.tesis_codigo", "t.fuente",
    ]
    if usa_fts:
        cols.append(
            "snippet(tesis_fts, 1, '«', '»', ' … ', 15) AS snippet_match"
        )
        cols.append("bm25(tesis_fts) AS rank_score")
        cols.append(f"substr(t.texto, 1, {MAX_EXTRACTO}) AS extracto")
    else:
        cols.append(f"substr(t.texto, 1, {MAX_EXTRACTO}) AS extracto")
    return ", ".join(cols)


def format_resultados(
    rows: list[dict],
    incluir_texto: bool = False,
    mostrar_nivel: bool = True,
) -> str:
    """Formatea resultados para que el LLM los interprete.

    Args:
        rows: Lista de dicts (filas de SQLite ya convertidas).
        incluir_texto: Si True, mete el texto completo (truncado a
                       MAX_TEXTO_COMPLETO) y los precedentes. Solo para
                       lecturas puntuales (leer_tesis_completa, etc.).
        mostrar_nivel: Si True, agrega el nivel S/A/B/C/D/E/F al header.
    """
    if not rows:
        return (
            "Sin resultados para esta búsqueda. "
            "Reformula con sinónimos o conceptos más amplios antes de rendirte."
        )

    partes = []
    for i, row in enumerate(rows, 1):
        nivel = nivel_vinculante(row) if mostrar_nivel else None
        header = f"--- Resultado {i}"
        if nivel:
            header += f" (Nivel {nivel})"
        header += " ---"

        lineas = [
            header,
            f"ID: {row.get('id_tesis', 'N/A')}",
            f"Rubro: {row.get('rubro', 'N/A')}",
            f"Codigo: {row.get('tesis_codigo', 'N/A')}",
            f"Tipo: {row.get('tipo_tesis', 'N/A')}",
            f"Instancia: {row.get('instancia', 'N/A')}",
        ]
        if row.get("organo_juris"):
            lineas.append(f"Organo: {row['organo_juris']}")
        lineas.extend([
            f"Epoca: {row.get('epoca', 'N/A')}",
            f"Anio: {row.get('anio', 'N/A')}",
            f"Materia: {row.get('materias', 'N/A')}",
        ])
        if row.get("fuente"):
            lineas.append(f"Fuente: {row['fuente']}")

        if incluir_texto and row.get("texto"):
            texto = row["texto"]
            if len(texto) > MAX_TEXTO_COMPLETO:
                texto = texto[:MAX_TEXTO_COMPLETO] + "... [truncado]"
            lineas.append(f"Texto completo:\n{texto}")
        elif row.get("snippet_match"):
            lineas.append(f"Fragmento relevante: {row['snippet_match']}")
        elif row.get("extracto"):
            lineas.append(f"Extracto: {row['extracto']}")

        if incluir_texto and row.get("precedentes"):
            precedentes = row["precedentes"]
            if len(precedentes) > 2000:
                precedentes = precedentes[:2000] + "... [truncado]"
            lineas.append(f"Precedentes: {precedentes}")

        partes.append("\n".join(lineas))

    encabezado = f"Se encontraron {len(rows)} resultado(s).\n"
    return encabezado + "\n\n".join(partes)
