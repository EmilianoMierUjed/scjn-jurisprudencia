"""
MCP Server — Jurisprudencia SCJN (wrapper delgado sobre scjn_core).

Conecta Claude Desktop con la base de datos SQLite de ~311,000 criterios.

Cómo funciona:
- Claude Desktop lanza este script como proceso hijo (vía stdio).
- El server expone "tools" (funciones) que Claude puede llamar.
- Cada @mcp.tool() es un wrapper de una sola línea sobre scjn_core.search.
- Toda la lógica jurídica (filtros, ranking, formato) vive en scjn_core,
  para que también la pueda usar el CLI standalone (cli/scjn_cli.py).

El abogado nunca ve este código. Solo habla con Claude.
"""

import sys
from pathlib import Path

# Permite ejecutar este script directamente sin instalar el paquete
# (útil cuando Claude Desktop lo lanza con `python server/server.py`).
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from mcp.server.fastmcp import FastMCP

from scjn_core import database, protocol, search, tools_v12
from scjn_core.config import DB_PATH, get_logger

logger = get_logger("scjn-mcp")

# ── Inicializar el server MCP ────────────────────────────────────────────
mcp = FastMCP("SCJN Jurisprudencia", instructions=protocol.INSTRUCCIONES)


def _conn():
    """Abre una conexión a la BD para usar dentro de cada tool."""
    return database.connect()


# ════════════════════════════════════════════════════════════════════════
# TOOL 1: Búsqueda conceptual (OR de sinónimos)
# ════════════════════════════════════════════════════════════════════════

@mcp.tool()
def buscar_jurisprudencia(
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
    """Busca tesis y jurisprudencia en la base de datos de la SCJN.

    Pasa MULTIPLES terminos alternativos para el mismo concepto
    (sinonimos, formulaciones diferentes) para maximizar resultados.
    Se buscan con OR: cualquier match cuenta. Los resultados se
    ordenan por fuerza vinculante (Pleno SCJN > Salas > Plenos
    Regionales > Plenos de Circuito > TCC) y relevancia BM25.

    Ejemplos de uso:
    - Derecho a la salud: ["derecho a la salud", "proteccion de la salud",
      "atencion medica", "servicios medicos"]
    - Prescripcion adquisitiva: ["prescripcion adquisitiva", "usucapion",
      "prescripcion positiva"]

    Args:
        terminos: Lista de terminos alternativos a buscar (sinonimos,
                  formulaciones diferentes del mismo concepto).
        solo_jurisprudencia: Si True, solo devuelve jurisprudencias
                             (criterio obligatorio, no tesis aisladas).
        materia: Filtra por materia (ej: "Civil", "Penal", "Laboral",
                 "Administrativa", "Constitucional", "Comun"). Coincidencia
                 parcial — una tesis con materia "Constitucional, Civil"
                 matchea tanto "Civil" como "Constitucional".
        instancia: Filtra por organo emisor. Presets:
                   - "scjn" — todas las de la Suprema Corte
                   - "pleno_scjn" — solo Pleno SCJN
                   - "salas_scjn" — Primera y Segunda Sala
                   - "primera_sala" / "segunda_sala"
                   - "plenos_regionales" / "plenos_circuito"
                   - "tcc" — Tribunales Colegiados de Circuito
        organo: Filtro libre sobre organo_juris (ej: "Primer Tribunal Colegiado").
        anio_minimo: Anio minimo de publicacion (0 = sin filtro).
        anio_maximo: Anio maximo de publicacion (0 = sin filtro).
        epocas: Lista de epocas a incluir. Acepta "decima", "10", "Decima Epoca",
                etc. Ej: ["decima", "undecima", "duodecima"] → solo 10a, 11a y 12a.
        buscar_en: Ambito de busqueda: "todo" (default), "rubro" (solo en el
                   titulo, mas preciso), o "texto" (solo en el cuerpo).
        orden: "vinculancia" (default — fuerza vinculante + relevancia),
               "relevancia" (BM25 puro), "reciente" (por ano DESC).
        limite: Maximo de resultados (default 25).

    Returns:
        Resultados con rubro, codigo, tipo, instancia, organo, epoca,
        anio, materia, fuente y snippet del fragmento que coincide.
    """
    conn = _conn()
    try:
        return search.buscar_jurisprudencia(
            conn,
            terminos=terminos,
            solo_jurisprudencia=solo_jurisprudencia,
            materia=materia,
            instancia=instancia,
            organo=organo,
            anio_minimo=anio_minimo,
            anio_maximo=anio_maximo,
            epocas=epocas,
            buscar_en=buscar_en,
            orden=orden,
            limite=limite,
        )
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════════════
# TOOL 2: Búsqueda interseccional (A AND B [AND C])
# ════════════════════════════════════════════════════════════════════════

@mcp.tool()
def buscar_interseccion(
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
    """Busca tesis que contengan DOS O TRES conceptos simultaneamente.

    Cada concepto acepta multiples formulaciones alternativas (OR dentro
    de cada concepto, AND entre los conceptos).

    Ejemplo 1: tesis sobre derecho a la salud EN el ISSSTE:
    - concepto_a: ["derecho a la salud", "proteccion de la salud"]
    - concepto_b: ["ISSSTE", "seguridad social", "derechohabiente"]

    Ejemplo 2: tesis sobre suspension de amparo en materia laboral por despido:
    - concepto_a: ["suspension", "medida cautelar"]
    - concepto_b: ["amparo"]
    - concepto_c: ["despido", "rescision", "terminacion de la relacion"]

    Args:
        concepto_a: Primer concepto (formulaciones alternativas).
        concepto_b: Segundo concepto.
        concepto_c: Tercer concepto opcional (deja None para solo 2 conceptos).
        solo_jurisprudencia: Solo jurisprudencias (criterio obligatorio).
        materia, instancia, organo, anio_minimo, anio_maximo, epocas, orden, limite:
            Ver buscar_jurisprudencia para descripcion.

    Returns:
        Tesis que contienen TODOS los conceptos, ordenadas por fuerza
        vinculante y relevancia, con snippet del match.
    """
    conn = _conn()
    try:
        return search.buscar_interseccion(
            conn,
            concepto_a=concepto_a,
            concepto_b=concepto_b,
            concepto_c=concepto_c,
            solo_jurisprudencia=solo_jurisprudencia,
            materia=materia,
            instancia=instancia,
            organo=organo,
            anio_minimo=anio_minimo,
            anio_maximo=anio_maximo,
            epocas=epocas,
            orden=orden,
            limite=limite,
        )
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════════════
# TOOL 3: Búsqueda por proximidad (NEAR)
# ════════════════════════════════════════════════════════════════════════

@mcp.tool()
def buscar_proximidad(
    termino_a: str,
    termino_b: str,
    distancia: int = 15,
    solo_jurisprudencia: bool = False,
    materia: str = "",
    instancia: str = "",
    anio_minimo: int = 0,
    limite: int = 25,
) -> str:
    """Busca tesis donde dos terminos aparecen CERCA en el texto.

    Util cuando dos conceptos deben estar relacionados dentro de la misma
    frase o parrafo (no solo en la misma tesis). Ejemplo: "despido" NEAR
    "carga de la prueba" encontrara solo tesis donde ambos conceptos estan
    a lo sumo a 15 palabras de distancia, lo que implica que la tesis
    realmente razona sobre la relacion entre ambos.

    Args:
        termino_a: Primer termino o frase.
        termino_b: Segundo termino o frase.
        distancia: Distancia maxima en tokens (default 15).
                   Menor = mas estricto y preciso.
        solo_jurisprudencia, materia, instancia, anio_minimo, limite:
            Ver buscar_jurisprudencia.

    Returns:
        Tesis donde ambos terminos aparecen dentro de la distancia dada.
    """
    conn = _conn()
    try:
        return search.buscar_proximidad(
            conn,
            termino_a=termino_a,
            termino_b=termino_b,
            distancia=distancia,
            solo_jurisprudencia=solo_jurisprudencia,
            materia=materia,
            instancia=instancia,
            anio_minimo=anio_minimo,
            limite=limite,
        )
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════════════
# TOOL 4: Búsqueda por rubro (títulos)
# ════════════════════════════════════════════════════════════════════════

@mcp.tool()
def buscar_rubro(
    terminos: list[str],
    solo_jurisprudencia: bool = False,
    materia: str = "",
    instancia: str = "",
    anio_minimo: int = 0,
    limite: int = 25,
) -> str:
    """Busca SOLO en los rubros (titulos) de las tesis.

    Es la herramienta mas precisa cuando el abogado recuerda parte del
    titulo de un criterio, o quiere ver que tesis existen bajo un tema
    muy especifico. Los rubros son mas cortos y limpios que los textos,
    asi que esta busqueda casi nunca devuelve falsos positivos.

    Args:
        terminos: Palabras clave que deben aparecer en el rubro
                  (busqueda OR entre terminos).
        solo_jurisprudencia, materia, instancia, anio_minimo, limite:
            Ver buscar_jurisprudencia.

    Returns:
        Tesis cuyos rubros contienen alguno de los terminos.
    """
    conn = _conn()
    try:
        return search.buscar_rubro(
            conn,
            terminos=terminos,
            solo_jurisprudencia=solo_jurisprudencia,
            materia=materia,
            instancia=instancia,
            anio_minimo=anio_minimo,
            limite=limite,
        )
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════════════
# TOOL 5: Lectura completa de una tesis
# ════════════════════════════════════════════════════════════════════════

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
    conn = _conn()
    try:
        return search.leer_tesis_completa(conn, identificador=identificador, campo=campo)
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════════════
# TOOL 6: Lectura batch de varias tesis
# ════════════════════════════════════════════════════════════════════════

@mcp.tool()
def leer_varias_tesis(
    identificadores: list[str],
    campo: str = "id_tesis",
) -> str:
    """Lee el texto completo de varias tesis en una sola llamada.

    Evita el ida y vuelta de llamar leer_tesis_completa N veces. Ideal
    para la Ronda 3 del protocolo (confirmar 5-10 tesis prometedoras).

    Args:
        identificadores: Lista de id_tesis o codigos (maximo 15).
        campo: "id_tesis" (default) o "tesis_codigo".

    Returns:
        Texto completo de todas las tesis encontradas.
    """
    conn = _conn()
    try:
        return search.leer_varias_tesis(conn, identificadores=identificadores, campo=campo)
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════════════
# TOOL 7: Búsqueda por contradicción de tesis
# ════════════════════════════════════════════════════════════════════════

@mcp.tool()
def buscar_contradiccion(
    terminos: list[str],
    instancia: str = "",
    anio_minimo: int = 0,
    limite: int = 20,
) -> str:
    """Busca jurisprudencias surgidas de contradiccion de tesis.

    Las contradicciones de tesis resueltas son especialmente valiosas
    porque unifican criterios discrepantes entre tribunales. Son oro
    para el litigante.

    Busca en dos lugares:
    1. Rubros que empiecen con "CONTRADICCIÓN DE TESIS"
    2. Precedentes que mencionen explicitamente una contradiccion
       (campo `precedentes`, no solo el texto).

    Args:
        terminos: Conceptos a buscar dentro de las contradicciones.
        instancia: Filtro opcional por organo (ver buscar_jurisprudencia).
        anio_minimo: Solo contradicciones desde este anio.
        limite: Maximo de resultados.

    Returns:
        Jurisprudencias por contradiccion de tesis relacionadas al tema.
    """
    conn = _conn()
    try:
        return search.buscar_contradiccion(
            conn,
            terminos=terminos,
            instancia=instancia,
            anio_minimo=anio_minimo,
            limite=limite,
        )
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════════════
# TOOL 8: Buscar tesis similares a una dada
# ════════════════════════════════════════════════════════════════════════

@mcp.tool()
def buscar_similares(
    id_tesis: str,
    limite: int = 15,
    solo_jurisprudencia: bool = False,
) -> str:
    """Encuentra tesis similares a una tesis dada.

    Toma el rubro de la tesis de referencia y busca otras con lenguaje
    similar, ordenadas por relevancia BM25. Ideal para reconstruir la
    linea jurisprudencial completa de un tema una vez que encontraste
    el criterio clave.

    Args:
        id_tesis: ID de la tesis de referencia.
        limite: Maximo de resultados.
        solo_jurisprudencia: Si True, excluye tesis aisladas.

    Returns:
        Lista de tesis con rubros similares al de la tesis dada,
        ordenadas por relevancia.
    """
    conn = _conn()
    try:
        return search.buscar_similares(
            conn,
            id_tesis=id_tesis,
            limite=limite,
            solo_jurisprudencia=solo_jurisprudencia,
        )
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════════════
# TOOL 9: Explorar valores de la BD
# ════════════════════════════════════════════════════════════════════════

@mcp.tool()
def explorar_valores(campo: str, limite: int = 30) -> str:
    """Muestra los valores unicos disponibles en un campo de la BD.

    Util para saber que valores usar en los filtros. Por ejemplo,
    antes de filtrar por tipo_tesis, puedes ver que valores existen.

    Args:
        campo: Nombre del campo a explorar. Opciones: tipo_tesis,
               epoca, instancia, materias, organo_juris, fuente.
        limite: Maximo de valores unicos a mostrar.

    Returns:
        Lista de valores unicos encontrados con su frecuencia.
    """
    conn = _conn()
    try:
        return search.explorar_valores(conn, campo=campo, limite=limite)
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════════════
# TOOL 10: Info de la base de datos
# ════════════════════════════════════════════════════════════════════════

@mcp.tool()
def info_base_datos() -> str:
    """Muestra estadisticas y estado actual de la base de datos.

    Llama a esta herramienta cuando el usuario pregunte que tan
    actualizada esta la base de datos, cuantos criterios contiene,
    o antes de explicar los limites del producto.

    Returns:
        Total de tesis, rango de anios, ultima actualizacion, desglose
        por tipo, por epoca y por instancia, y estado del indice FTS5.
    """
    # Lee VERSION del repo y el log de la última actualización para que
    # info_base_datos los pueda mostrar.
    version_path = _REPO_ROOT / "VERSION"
    version = "desconocida"
    if version_path.exists():
        try:
            version = version_path.read_text(encoding="utf-8").strip()
        except Exception:
            pass

    log_path = Path(DB_PATH).parent / "ultimo_update.log"

    conn = _conn()
    try:
        return search.info_base_datos(
            conn,
            version=version,
            log_path=str(log_path),
        )
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════════════
# TOOL 11: Extraer cita oficial (v1.2)
# ════════════════════════════════════════════════════════════════════════

@mcp.tool()
def extraer_cita_oficial(identificador: str, campo: str = "id_tesis") -> str:
    """Devuelve la cita formal lista para pegar en un escrito legal mexicano.

    Construye el formato canónico del Manual de Estilo del SJF a partir de
    los campos sueltos de la tesis (codigo, fuente, época, mes/año, registro
    digital). Útil cuando ya identificaste la tesis con buscar_* y necesitas
    la línea exacta para pegar en una demanda o un amparo.

    Args:
        identificador: id_tesis (default) o tesis_codigo de la tesis.
        campo: "id_tesis" (default) o "tesis_codigo".

    Returns:
        Cita oficial + rubro + órgano emisor.
    """
    conn = _conn()
    try:
        return tools_v12.extraer_cita_oficial(conn, identificador=identificador, campo=campo)
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════════════
# TOOL 12: Compilar línea jurisprudencial (v1.2)
# ════════════════════════════════════════════════════════════════════════

@mcp.tool()
def compilar_linea_jurisprudencial(
    tema: list[str],
    anio_minimo: int = 2010,
    instancia: str = "",
    limite: int = 30,
) -> str:
    """Devuelve cronología de jurisprudencias sobre un tema.

    Útil para argumentar evolución del criterio en un escrito (ej:
    "como ha venido sosteniéndose desde 2018, esta Sala…"). Ordena
    ascendente por año y agrupa por época, marcando cambios de etapa.

    Args:
        tema: Lista de términos alternativos del tema.
        anio_minimo: Solo jurisprudencias desde este año (default 2010).
        instancia: Filtro opcional por preset de instancia.
        limite: Máximo de resultados.

    Returns:
        Cronología agrupada por época.
    """
    conn = _conn()
    try:
        return tools_v12.compilar_linea_jurisprudencial(
            conn, tema=tema, anio_minimo=anio_minimo, instancia=instancia, limite=limite,
        )
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════════════
# TOOL 13: Obligatorios para circuito (v1.2)
# ════════════════════════════════════════════════════════════════════════

@mcp.tool()
def buscar_obligatorios_para_circuito(
    circuito: str,
    terminos: list[str],
    limite: int = 30,
) -> str:
    """Filtra jurisprudencia obligatoria para un circuito específico.

    Para un abogado en el 17º circuito (Durango), el universo de criterios
    obligatorios son: Pleno SCJN + Salas SCJN + Plenos Regionales +
    Plenos del propio circuito + TCCs del propio circuito. Esta tool
    aplica ese filtro automáticamente.

    Args:
        circuito: Número (1-32), romano ("XVII") o ordinal castellano
                  ("decimo septimo"). Acepta acentos o no.
        terminos: Lista de términos del tema.
        limite: Máximo de resultados.

    Returns:
        Jurisprudencias obligatorias para ese circuito, ordenadas por
        fuerza vinculante.
    """
    conn = _conn()
    try:
        return tools_v12.buscar_obligatorios_para_circuito(
            conn, circuito=circuito, terminos=terminos, limite=limite,
        )
    finally:
        conn.close()


# ── Punto de entrada ─────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info(f"Iniciando MCP Server SCJN — BD: {DB_PATH}")
    mcp.run(transport="stdio")
