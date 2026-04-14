"""
Presets de filtros (instancia, época) y función de aplicación.

Aquí vive el conocimiento sobre cómo se nombran las cosas en la BD:
- Las 8 instancias canónicas (presets para el parámetro `instancia`).
- Las 12 épocas y sus formas alternativas de escritura.
- La función `_aplicar_filtros_comunes` que mutates where_clauses/params
  según los filtros opcionales pasados.

IMPORTANTE: en la BD, las ~205k tesis de SCJN comparten
`instancia="Suprema Corte de Justicia de la Nación"`. La distinción
Pleno/Sala vive en `organo_juris`. Los presets de instancia codifican esto.
"""

# ── Presets válidos para el parámetro `instancia` en las tools ──────────
INSTANCIA_PRESETS: dict[str, str] = {
    "scjn": "t.instancia = 'Suprema Corte de Justicia de la Nación'",
    "pleno_scjn": (
        "t.instancia = 'Suprema Corte de Justicia de la Nación' "
        "AND LOWER(t.organo_juris) LIKE 'pleno%'"
    ),
    "salas_scjn": (
        "t.instancia = 'Suprema Corte de Justicia de la Nación' "
        "AND LOWER(t.organo_juris) LIKE '%sala%'"
    ),
    "primera_sala": (
        "t.instancia = 'Suprema Corte de Justicia de la Nación' "
        "AND LOWER(t.organo_juris) LIKE 'primera sala%'"
    ),
    "segunda_sala": (
        "t.instancia = 'Suprema Corte de Justicia de la Nación' "
        "AND LOWER(t.organo_juris) LIKE 'segunda sala%'"
    ),
    "plenos_regionales": "LOWER(t.instancia) LIKE '%plenos regionales%'",
    "plenos_circuito": "LOWER(t.instancia) LIKE '%plenos de circuito%'",
    "tcc": "LOWER(t.instancia) LIKE '%tribunales colegiados%'",
}


# ── Mapa de épocas ───────────────────────────────────────────────────────
# Cubre nombres en español sin acentos, números arábigos y romanos comunes.
EPOCAS_CANONICAS: dict[str, str] = {
    "primera": "Primera Época",
    "segunda": "Segunda Época",
    "tercera": "Tercera Época",
    "cuarta": "Cuarta Época",
    "quinta": "Quinta Época",
    "sexta": "Sexta Época",
    "septima": "Séptima Época",
    "octava": "Octava Época",
    "novena": "Novena Época",
    "decima": "Décima Época",
    "undecima": "Undécima Época",
    "duodecima": "Duodécima Época",
    "1": "Primera Época", "2": "Segunda Época", "3": "Tercera Época",
    "4": "Cuarta Época", "5": "Quinta Época", "6": "Sexta Época",
    "7": "Séptima Época", "8": "Octava Época", "9": "Novena Época",
    "10": "Décima Época", "11": "Undécima Época", "12": "Duodécima Época",
}


def _normalizar_epoca(texto: str) -> str | None:
    """Convierte 'decima', '10', 'Décima', 'decima epoca' → 'Décima Época'."""
    if not texto:
        return None
    limpio = (
        texto.lower()
        .replace("á", "a").replace("é", "e").replace("í", "i")
        .replace("ó", "o").replace("ú", "u")
        .replace("época", "").replace("epoca", "")
        .strip()
    )
    return EPOCAS_CANONICAS.get(limpio)


def aplicar_filtros_comunes(
    where_clauses: list[str],
    params: list,
    *,
    solo_jurisprudencia: bool,
    materia: str,
    instancia: str,
    organo: str,
    anio_minimo: int,
    anio_maximo: int,
    epocas: list[str],
) -> str | None:
    """Añade los filtros opcionales a `where_clauses`/`params` (mutación).

    Devuelve None en éxito, o un string con mensaje de error si el filtro
    `instancia` no corresponde a ningún preset válido.
    """
    if solo_jurisprudencia:
        where_clauses.append("LOWER(t.tipo_tesis) LIKE '%jurisprudencia%'")

    if materia and materia.strip():
        where_clauses.append("LOWER(t.materias) LIKE ?")
        params.append(f"%{materia.strip().lower()}%")

    if instancia and instancia.strip():
        clave = instancia.strip().lower().replace(" ", "_")
        if clave in INSTANCIA_PRESETS:
            where_clauses.append(f"({INSTANCIA_PRESETS[clave]})")
        else:
            return (
                f"Error: instancia='{instancia}' no es un preset valido. "
                f"Opciones: {', '.join(sorted(INSTANCIA_PRESETS))}."
            )

    if organo and organo.strip():
        where_clauses.append("LOWER(t.organo_juris) LIKE ?")
        params.append(f"%{organo.strip().lower()}%")

    if anio_minimo and anio_minimo > 0:
        where_clauses.append("t.anio >= ?")
        params.append(int(anio_minimo))

    if anio_maximo and anio_maximo > 0:
        where_clauses.append("t.anio <= ?")
        params.append(int(anio_maximo))

    if epocas:
        canonicas = []
        for e in epocas:
            normal = _normalizar_epoca(e)
            if normal:
                canonicas.append(normal)
        if canonicas:
            placeholders = ",".join(["?"] * len(canonicas))
            where_clauses.append(f"t.epoca IN ({placeholders})")
            params.extend(canonicas)

    return None
