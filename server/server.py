"""
MCP Server — Jurisprudencia SCJN
Conecta Claude Desktop con la base de datos SQLite de ~300,000 criterios.

Cómo funciona:
- Claude Desktop lanza este script como proceso hijo (vía stdio).
- El server expone "tools" (funciones) que Claude puede llamar.
- Claude decide cuándo llamar cada tool según la conversación con el abogado.
- Los resultados regresan a Claude, que los interpreta y presenta al usuario.

El abogado nunca ve este código. Solo habla con Claude.
"""

import sqlite3
import os
import sys
import re
import logging
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# ── Logging (a stderr, NUNCA a stdout — stdout es el canal MCP) ──────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("scjn-mcp")

# ── Configuración ────────────────────────────────────────────────────────
_DEFAULT_DB = str(Path(__file__).parent.parent / "data" / "scjn_tesis.db")
DB_PATH = os.environ.get("DB_PATH", _DEFAULT_DB)

# ── Instrucciones estratégicas para Claude ───────────────────────────────
INSTRUCCIONES = """
Eres un abogado litigante experto en derecho mexicano. Tienes acceso a una base
de datos local con ~311,000 criterios de la SCJN (jurisprudencias y tesis
aisladas, desde 1911 hasta 2026) a través de herramientas MCP.

Tu trabajo NO es ser un motor de búsqueda de texto. Es razonar como un abogado
que busca jurisprudencia para GANAR un caso.

IMPORTANTE: NUNCA inventes tesis, rubros, códigos de registro ni precedentes.
TODA la información jurisprudencial que presentes DEBE provenir exclusivamente
de los resultados de las herramientas de búsqueda. Si no encuentras resultados,
dilo honestamente. Jamás alucines criterios judiciales.

══════════════════════════════════════════════════════
PROTOCOLO DE BÚSQUEDA — EJECUCIÓN OBLIGATORIA
══════════════════════════════════════════════════════

PASO 1 — DIAGNÓSTICO JURÍDICO (antes de usar herramientas):
  Analiza el caso del usuario:
  - Hechos clave, derechos vulnerados, tipo de procedimiento
  - Etapa procesal, posición del usuario (actor/demandado/quejoso)
  - Qué necesita probar para esta etapa específica
  Descompón en conceptos jurídicos buscables con 3+ formulaciones
  alternativas cada uno (el lenguaje de la SCJN varía entre épocas y salas).

PASO 2 — BÚSQUEDA ITERATIVA (las 5 rondas son obligatorias):
  Ronda 1: buscar_jurisprudencia con cada concepto principal.
           Pasa TODAS las formulaciones alternativas como lista de términos.
  Ronda 2: buscar_interseccion cruzando los 2-3 conceptos más importantes.
  Ronda 3: leer_tesis_completa de las 5-10 tesis más prometedoras
           para confirmar relevancia real (no confiar solo en el extracto).
  Ronda 4: buscar_contradiccion para temas que lo ameriten.
           Las contradicciones resueltas son especialmente valiosas.
  Ronda 5: buscar_jurisprudencia con términos que la CONTRAPARTE usaría
           para anticipar y preparar respuesta. OBLIGATORIA.

PASO 3 — REGLA DE ORO:
  Si una ronda da 0 resultados, NO reportar "no se encontró nada".
  Reformular con sinónimos más amplios o conceptos análogos.
  Solo reportar ausencia después de 3+ reformulaciones fallidas.
  Si el tema es muy reciente, sugerir verificar en el SJF en línea.

PASO 4 — CLASIFICACIÓN POR FUERZA VINCULANTE:
  Nivel S: Jurisprudencia del Pleno SCJN — Obligatoria para TODOS
  Nivel A: Jurisprudencia de Sala SCJN — Obligatoria (salvo para el Pleno)
  Nivel B: Jurisprudencia de Pleno de Circuito/Regional — Obligatoria en circuito
  Nivel C: Jurisprudencia de TCC — Obligatoria para juzgados del circuito
  Nivel D: Tesis aislada de SCJN — Orientadora, persuasiva
  Nivel E: Tesis aislada de TCC — Orientadora, útil como refuerzo

PASO 5 — PRESENTACIÓN ESTRATÉGICA:
  Organiza resultados por UTILIDAD ESTRATÉGICA, no por keywords:

  1. CRITERIOS PRINCIPALES (directamente aplicables)
     Para cada tesis: nivel de fuerza, rubro, código de registro, órgano,
     época, año, extracto relevante (ratio decidendi), y POR QUÉ sirve
     para este caso específico.

  2. CRITERIOS DE REFUERZO (fortalecen la posición)

  3. CRITERIOS DE RIESGO (podría usar la contraparte)
     SIEMPRE incluye al menos 1 criterio adverso, con sugerencia
     de cómo distinguirlo o neutralizarlo.

  4. CRITERIOS ANÁLOGOS (aplicables por extensión o "con mayor razón")

  5. RESUMEN EJECUTIVO:
     - Total de criterios, jurisprudencias vs. tesis aisladas
     - Cobertura: Sólida / Moderada / Débil
     - Línea argumentativa sugerida basada en los hallazgos
     - Vacíos probatorios detectados

  Reglas:
  - Máximo 15-20 tesis. Calidad sobre cantidad.
  - Cita SIEMPRE con tesis_codigo para que el abogado verifique.
  - Si la cobertura es débil, dilo claramente y sugiere alternativas.

══════════════════════════════════════════════════════
CONOCIMIENTO JURÍDICO DE REFERENCIA
══════════════════════════════════════════════════════

Obligatoriedad (Art. 217 Ley de Amparo):
- Jurisprudencia del Pleno SCJN → todos los tribunales
- Jurisprudencia de Salas SCJN → todos salvo el Pleno
- Jurisprudencia de Plenos de Circuito → TCC y juzgados del circuito
- Jurisprudencia de TCC → juzgados de distrito del circuito
- Tesis aisladas → orientadoras, no vinculantes

Épocas: 11a/12a (2021+) = máxima relevancia | 10a (2011-2021) = muy relevante
| 9a (1995-2011) = relevante si el marco no cambió | Anteriores = histórico

Materia cruzada — buscar además en:
- Administrativa → Constitucional, Común
- Civil → Constitucional, Común, Mercantil
- Laboral → Administrativa, Constitucional
- Penal → Constitucional, Común
- Amparo → La materia del acto reclamado + Constitucional

══════════════════════════════════════════════════════
ERRORES QUE DEBES EVITAR
══════════════════════════════════════════════════════
1. Buscar con un solo término y rendirte → usa múltiples formulaciones.
2. Filtrar por materias en la primera pasada → puede excluir tesis relevantes.
3. Presentar tesis sin leer su texto completo → siempre lee las prometedoras.
4. Ignorar el tipo de tesis → jurisprudencia ≠ tesis aislada.
5. Ignorar la jerarquía del órgano → TCC del 1er circuito no vincula al 4to.
6. Omitir la Ronda 5 → el abogado NECESITA saber qué puede citar el contrario.
7. Entregar lista plana sin análisis → el abogado necesita estrategia, no catálogo.
8. Asumir que la BD es exhaustiva → si es muy reciente, sugerir verificar en SJF.
""".strip()


# ── Inicializar el server MCP ────────────────────────────────────────────
mcp = FastMCP("SCJN Jurisprudencia", instructions=INSTRUCCIONES)


# ── Helpers ──────────────────────────────────────────────────────────────

_fts_available = None


def has_fts() -> bool:
    """Verifica si la tabla FTS5 existe en la BD."""
    global _fts_available
    if _fts_available is not None:
        return _fts_available
    try:
        conn = get_db_connection()
        conn.execute("SELECT COUNT(*) FROM tesis_fts WHERE tesis_fts MATCH 'test'")
        _fts_available = True
        conn.close()
        logger.info("FTS5 disponible — búsquedas rápidas activadas")
    except Exception:
        _fts_available = False
        logger.warning("FTS5 NO disponible — usando LIKE (más lento)")
    return _fts_available


def get_db_connection() -> sqlite3.Connection:
    """Abre conexión a la BD. Lanza error claro si no existe."""
    if not Path(DB_PATH).exists():
        raise FileNotFoundError(
            f"No se encontró la base de datos en: {DB_PATH}\n"
            f"Verifica que scjn_tesis.db esté en esa ruta."
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def sanitize_fts(term: str) -> str:
    """Limpia un término para usarlo en FTS5 MATCH como frase."""
    cleaned = re.sub(r'["\*\(\)\+\^\{\}\[\]~]', " ", term)
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        return ""
    return f'"{cleaned}"'


def build_fts_or(terms: list[str]) -> str:
    """Construye expresión FTS5 OR a partir de una lista de términos."""
    parts = [sanitize_fts(t) for t in terms if t.strip()]
    parts = [p for p in parts if p]
    return " OR ".join(parts) if parts else ""


def rows_to_dicts(rows: list) -> list[dict]:
    return [dict(row) for row in rows]


# Orden para priorizar resultados por fuerza vinculante
ORDEN_VINCULANTE = """
    CASE WHEN LOWER(tipo_tesis) LIKE '%jurisprudencia%' THEN 0 ELSE 1 END,
    CASE
        WHEN LOWER(instancia) LIKE '%pleno%suprema%'
          OR LOWER(instancia) LIKE '%pleno de la s%' THEN 0
        WHEN LOWER(instancia) LIKE '%primera sala%'
          OR LOWER(instancia) LIKE '%segunda sala%' THEN 1
        WHEN LOWER(instancia) LIKE '%pleno%circuito%'
          OR LOWER(instancia) LIKE '%pleno%region%' THEN 2
        WHEN LOWER(instancia) LIKE '%tribunal%colegiado%' THEN 3
        ELSE 4
    END,
    anio DESC
"""


def format_resultados(rows: list[dict], incluir_texto: bool = False) -> str:
    """Formatea resultados para que Claude los interprete."""
    if not rows:
        return "Sin resultados para esta búsqueda."

    partes = []
    for i, row in enumerate(rows, 1):
        lineas = [
            f"--- Resultado {i} ---",
            f"ID: {row.get('id_tesis', 'N/A')}",
            f"Rubro: {row.get('rubro', 'N/A')}",
            f"Codigo: {row.get('tesis_codigo', 'N/A')}",
            f"Tipo: {row.get('tipo_tesis', 'N/A')}",
            f"Instancia: {row.get('instancia', 'N/A')}",
            f"Organo: {row.get('organo_juris', 'N/A')}" if row.get("organo_juris") else None,
            f"Epoca: {row.get('epoca', 'N/A')}",
            f"Anio: {row.get('anio', 'N/A')}",
            f"Materia: {row.get('materias', 'N/A')}",
        ]
        lineas = [l for l in lineas if l is not None]

        if incluir_texto and row.get("texto"):
            lineas.append(f"Texto completo:\n{row['texto']}")
        elif row.get("extracto"):
            lineas.append(f"Extracto: {row['extracto']}")

        if incluir_texto and row.get("precedentes"):
            lineas.append(f"Precedentes: {row['precedentes']}")

        partes.append("\n".join(lineas))

    encabezado = f"Se encontraron {len(rows)} resultado(s).\n"
    return encabezado + "\n\n".join(partes)


# ── TOOL 1: Búsqueda conceptual ─────────────────────────────────────────

@mcp.tool()
def buscar_jurisprudencia(
    terminos: list[str],
    solo_jurisprudencia: bool = False,
    epoca_minima: str = "",
    anio_minimo: int = 0,
    limite: int = 30,
) -> str:
    """Busca tesis y jurisprudencia en la base de datos de la SCJN.

    Pasa MULTIPLES terminos alternativos para el mismo concepto
    (sinonimos, formulaciones diferentes) para maximizar resultados.
    Se buscan con OR: cualquier match cuenta.

    Ejemplos de uso:
    - Derecho a la salud: ["derecho a la salud", "proteccion de la salud",
      "atencion medica", "servicios medicos"]
    - Prescripcion adquisitiva: ["prescripcion adquisitiva", "usucapion",
      "prescripcion positiva"]

    Args:
        terminos: Lista de terminos alternativos a buscar (sinonimos,
                  formulaciones diferentes del mismo concepto).
        solo_jurisprudencia: Si True, solo devuelve jurisprudencias
                            (no tesis aisladas). Util para argumentos
                            que necesitan criterio obligatorio.
        epoca_minima: Filtrar por epoca (ej: "Decima Epoca").
                      Dejar vacio para buscar en todas.
        anio_minimo: Anio minimo de publicacion (ej: 2015).
                     0 = sin filtro de anio.
        limite: Maximo de resultados a devolver (default 30).

    Returns:
        Resultados formateados con rubro, codigo, tipo, instancia,
        epoca, anio, materia, y extracto del texto.
    """
    if not terminos:
        return "Error: Debes proporcionar al menos un termino de busqueda."

    conn = get_db_connection()
    try:
        params = []

        if has_fts():
            # ── FTS5 (rápido) ──
            fts_expr = build_fts_or(terminos)
            if not fts_expr:
                return "Error: Terminos invalidos."

            where_clauses = [
                "t.rowid IN (SELECT rowid FROM tesis_fts WHERE tesis_fts MATCH ?)"
            ]
            params.append(fts_expr)
        else:
            # ── Fallback LIKE (lento) ──
            conds = []
            for t in terminos:
                t_lower = t.lower().strip()
                conds.append("(LOWER(t.texto) LIKE ? OR LOWER(t.rubro) LIKE ?)")
                params.extend([f"%{t_lower}%", f"%{t_lower}%"])
            where_clauses = [f"({' OR '.join(conds)})"]

        if solo_jurisprudencia:
            where_clauses.append("LOWER(t.tipo_tesis) LIKE '%jurisprudencia%'")

        if epoca_minima:
            where_clauses.append("LOWER(t.epoca) LIKE ?")
            params.append(f"%{epoca_minima.lower()}%")

        if anio_minimo > 0:
            where_clauses.append("t.anio >= ?")
            params.append(anio_minimo)

        query = f"""
        SELECT t.id_tesis, t.rubro, t.tipo_tesis, t.instancia, t.epoca,
               t.anio, t.materias, t.tesis_codigo,
               substr(t.texto, 1, 600) AS extracto
        FROM tesis t
        WHERE {' AND '.join(where_clauses)}
        ORDER BY {ORDEN_VINCULANTE}
        LIMIT ?
        """
        params.append(limite)

        cursor = conn.execute(query, params)
        rows = rows_to_dicts(cursor.fetchall())

        logger.info(
            f"buscar_jurisprudencia: {len(rows)} resultados "
            f"para {len(terminos)} terminos (FTS={'si' if has_fts() else 'no'})"
        )
        return format_resultados(rows)

    except Exception as e:
        logger.error(f"Error en buscar_jurisprudencia: {e}")
        return f"Error en la busqueda: {e}"
    finally:
        conn.close()


# ── TOOL 2: Búsqueda interseccional ─────────────────────────────────────

@mcp.tool()
def buscar_interseccion(
    concepto_a: list[str],
    concepto_b: list[str],
    solo_jurisprudencia: bool = False,
    anio_minimo: int = 0,
    limite: int = 30,
) -> str:
    """Busca tesis que contengan DOS conceptos simultaneamente.

    Cada concepto acepta multiples formulaciones alternativas (OR dentro
    de cada concepto, AND entre los dos conceptos).

    Ejemplo: Buscar tesis sobre derecho a la salud EN el ISSSTE:
    - concepto_a: ["derecho a la salud", "proteccion de la salud"]
    - concepto_b: ["ISSSTE", "seguridad social", "derechohabiente"]

    Args:
        concepto_a: Primer concepto (con formulaciones alternativas).
        concepto_b: Segundo concepto (con formulaciones alternativas).
        solo_jurisprudencia: Solo jurisprudencias (criterio obligatorio).
        anio_minimo: Anio minimo (0 = sin filtro).
        limite: Maximo de resultados.

    Returns:
        Tesis que contienen AMBOS conceptos.
    """
    if not concepto_a or not concepto_b:
        return "Error: Ambos conceptos deben tener al menos un termino."

    conn = get_db_connection()
    try:
        params = []

        if has_fts():
            # ── FTS5: AND entre dos grupos OR ──
            fts_a = build_fts_or(concepto_a)
            fts_b = build_fts_or(concepto_b)
            if not fts_a or not fts_b:
                return "Error: Terminos invalidos."

            fts_expr = f"({fts_a}) AND ({fts_b})"
            where_clauses = [
                "t.rowid IN (SELECT rowid FROM tesis_fts WHERE tesis_fts MATCH ?)"
            ]
            params.append(fts_expr)
        else:
            # ── Fallback LIKE ──
            conds_a = []
            for t in concepto_a:
                conds_a.append("(LOWER(t.texto) LIKE ? OR LOWER(t.rubro) LIKE ?)")
                params.extend([f"%{t.lower().strip()}%"] * 2)
            conds_b = []
            for t in concepto_b:
                conds_b.append("(LOWER(t.texto) LIKE ? OR LOWER(t.rubro) LIKE ?)")
                params.extend([f"%{t.lower().strip()}%"] * 2)
            where_clauses = [
                f"({' OR '.join(conds_a)})",
                f"({' OR '.join(conds_b)})",
            ]

        if solo_jurisprudencia:
            where_clauses.append("LOWER(t.tipo_tesis) LIKE '%jurisprudencia%'")

        if anio_minimo > 0:
            where_clauses.append("t.anio >= ?")
            params.append(anio_minimo)

        query = f"""
        SELECT t.id_tesis, t.rubro, t.tipo_tesis, t.instancia, t.epoca,
               t.anio, t.materias, t.tesis_codigo,
               substr(t.texto, 1, 600) AS extracto
        FROM tesis t
        WHERE {' AND '.join(where_clauses)}
        ORDER BY {ORDEN_VINCULANTE}
        LIMIT ?
        """
        params.append(limite)

        cursor = conn.execute(query, params)
        rows = rows_to_dicts(cursor.fetchall())

        logger.info(f"buscar_interseccion: {len(rows)} resultados")
        return format_resultados(rows)

    except Exception as e:
        logger.error(f"Error en buscar_interseccion: {e}")
        return f"Error en la busqueda: {e}"
    finally:
        conn.close()


# ── TOOL 3: Lectura completa de una tesis ────────────────────────────────

@mcp.tool()
def leer_tesis_completa(identificador: str, campo: str = "id_tesis") -> str:
    """Lee el texto completo de una tesis especifica.

    Usa esta herramienta DESPUES de buscar, cuando encuentres una tesis
    prometedora y necesites leer su texto completo para confirmar que
    realmente es relevante al caso.

    Args:
        identificador: El valor a buscar (id_tesis, tesis_codigo, o
                       fragmento del rubro).
        campo: En que campo buscar. Opciones:
               - "id_tesis" (default): Busca por ID exacto
               - "tesis_codigo": Busca por codigo de registro
               - "rubro": Busca por texto parcial del rubro (usa LIKE)

    Returns:
        Texto completo de la tesis, incluyendo rubro, texto, precedentes,
        y todos los metadatos.
    """
    conn = get_db_connection()
    try:
        campos_select = """
            rubro, texto, precedentes, tipo_tesis, instancia,
            organo_juris, epoca, anio, tesis_codigo, materias, id_tesis
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
        logger.error(f"Error en leer_tesis_completa: {e}")
        return f"Error: {e}"
    finally:
        conn.close()


# ── TOOL 4: Búsqueda por contradicción de tesis ─────────────────────────

@mcp.tool()
def buscar_contradiccion(terminos: list[str], limite: int = 15) -> str:
    """Busca jurisprudencias surgidas de contradiccion de tesis.

    Las contradicciones de tesis resueltas son especialmente valiosas
    porque unifican criterios discrepantes entre tribunales. Son oro
    para el litigante.

    Args:
        terminos: Conceptos a buscar dentro de las contradicciones.
        limite: Maximo de resultados.

    Returns:
        Jurisprudencias por contradiccion de tesis relacionadas.
    """
    if not terminos:
        return "Error: Proporciona al menos un termino."

    conn = get_db_connection()
    try:
        params = []

        if has_fts():
            # FTS5: buscar términos AND "contradicción de tesis"
            fts_terminos = build_fts_or(terminos)
            if not fts_terminos:
                return "Error: Terminos invalidos."
            fts_expr = f'({fts_terminos}) AND "contradiccion de tesis"'
            where_clauses = [
                "t.rowid IN (SELECT rowid FROM tesis_fts WHERE tesis_fts MATCH ?)"
            ]
            params.append(fts_expr)
        else:
            conds = []
            for t in terminos:
                conds.append("LOWER(t.texto) LIKE ?")
                params.append(f"%{t.lower().strip()}%")
            where_clauses = [
                f"({' OR '.join(conds)})",
                "(LOWER(t.texto) LIKE '%contradicci_n de tesis%'"
                " OR LOWER(t.rubro) LIKE '%contradicci_n de tesis%')",
            ]

        where_clauses.append("LOWER(t.tipo_tesis) LIKE '%jurisprudencia%'")

        query = f"""
        SELECT t.id_tesis, t.rubro, t.tipo_tesis, t.instancia, t.epoca,
               t.anio, t.materias, t.tesis_codigo,
               substr(t.texto, 1, 600) AS extracto
        FROM tesis t
        WHERE {' AND '.join(where_clauses)}
        ORDER BY t.anio DESC
        LIMIT ?
        """
        params.append(limite)

        cursor = conn.execute(query, params)
        rows = rows_to_dicts(cursor.fetchall())

        logger.info(f"buscar_contradiccion: {len(rows)} resultados")
        return format_resultados(rows)

    except Exception as e:
        logger.error(f"Error en buscar_contradiccion: {e}")
        return f"Error: {e}"
    finally:
        conn.close()


# ── TOOL 5: Explorar valores de la BD ────────────────────────────────────

@mcp.tool()
def explorar_valores(campo: str, limite: int = 30) -> str:
    """Muestra los valores unicos disponibles en un campo de la BD.

    Util para saber que valores usar en los filtros. Por ejemplo,
    antes de filtrar por tipo_tesis, puedes ver que valores existen.

    Args:
        campo: Nombre del campo a explorar. Opciones: tipo_tesis,
               epoca, instancia, materias, organo_juris.
        limite: Maximo de valores unicos a mostrar.

    Returns:
        Lista de valores unicos encontrados con su frecuencia.
    """
    campos_permitidos = {
        "tipo_tesis", "epoca", "instancia", "materias", "organo_juris"
    }
    if campo not in campos_permitidos:
        return (
            f"Campo no permitido: '{campo}'. "
            f"Usa uno de: {', '.join(sorted(campos_permitidos))}"
        )

    conn = get_db_connection()
    try:
        cursor = conn.execute(
            f"SELECT DISTINCT {campo}, COUNT(*) as total "
            f"FROM tesis GROUP BY {campo} ORDER BY total DESC LIMIT ?",
            [limite],
        )
        rows = cursor.fetchall()

        resultado = f"Valores unicos en '{campo}' ({len(rows)} mostrados):\n\n"
        for row in rows:
            resultado += f"  - {row[0]}  ({row[1]:,} tesis)\n"

        return resultado

    except Exception as e:
        logger.error(f"Error en explorar_valores: {e}")
        return f"Error: {e}"
    finally:
        conn.close()


# ── TOOL 6: Info de la base de datos ─────────────────────────────────────

@mcp.tool()
def info_base_datos() -> str:
    """Muestra estadisticas y estado actual de la base de datos.

    Llama a esta herramienta cuando el usuario pregunte que tan
    actualizada esta la base de datos o cuantos criterios contiene.

    Returns:
        Total de tesis, rango de anios, ultima actualizacion, y
        desglose por tipo.
    """
    conn = get_db_connection()
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

        ultima = conn.execute(
            "SELECT MAX(fecha_descarga) FROM tesis"
        ).fetchone()[0]

        # Verificar si FTS5 está activo
        fts_status = "Activo (busquedas rapidas)" if has_fts() else "No disponible (busquedas lentas)"

        # Leer versión del producto
        version_path = Path(__file__).parent.parent / "VERSION"
        version = "desconocida"
        if version_path.exists():
            try:
                version = version_path.read_text(encoding="utf-8").strip()
            except Exception:
                pass

        resultado = [
            "=== Estado de la Base de Datos SCJN ===",
            f"Version del producto: {version}",
            f"Total de criterios: {total:,}",
            f"Rango temporal: {anio_min} - {anio_max}",
            f"Ultima descarga: {ultima or 'No registrada'}",
            f"Indice FTS5: {fts_status}",
            "",
            "Desglose por tipo:",
        ]
        for tipo, count in por_tipo:
            resultado.append(f"  - {tipo}: {count:,}")

        # Log de última actualización automática
        log_path = Path(DB_PATH).parent / "ultimo_update.log"
        if log_path.exists():
            try:
                log_content = log_path.read_text(encoding="utf-8").strip()
                resultado.append(f"\nUltima actualizacion automatica:\n{log_content}")
            except Exception:
                pass

        return "\n".join(resultado)

    except Exception as e:
        logger.error(f"Error en info_base_datos: {e}")
        return f"Error: {e}"
    finally:
        conn.close()


# ── Punto de entrada ─────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info(f"Iniciando MCP Server SCJN — BD: {DB_PATH}")
    mcp.run(transport="stdio")
