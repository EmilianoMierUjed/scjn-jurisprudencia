"""
CLI standalone — alternativa a Claude Desktop.

Usa la API de Anthropic directo, con el mismo protocolo de búsqueda y las
mismas 13 tools que el MCP server. Pago por uso en lugar de suscripción.

Uso:
    export ANTHROPIC_API_KEY=sk-ant-...
    python cli/scjn_cli.py --caso casos/amparo_issste.txt --output reporte.md
    # o desde stdin:
    cat caso.txt | python cli/scjn_cli.py --output reporte.md

Modelos:
    --model claude-sonnet-4-6   (default — balance precio/calidad)
    --model claude-opus-4-6     (mejor razonamiento, más caro)
    --model claude-haiku-4-5    (más barato, suficiente para casos simples)
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import anthropic

from scjn_core import database, protocol, search, tools_v12


# ════════════════════════════════════════════════════════════════════════
# Esquemas de las 13 tools (formato Anthropic Tool Use)
# ════════════════════════════════════════════════════════════════════════

TOOLS_SCHEMA = [
    {
        "name": "buscar_jurisprudencia",
        "description": (
            "Busca tesis y jurisprudencia en la base de datos SCJN. Acepta "
            "múltiples términos alternativos (sinónimos) que se buscan con OR. "
            "Resultados ordenados por fuerza vinculante (Pleno SCJN > Salas > "
            "Plenos Regionales > Plenos de Circuito > TCC) y relevancia BM25."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "terminos": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Lista de términos alternativos del concepto.",
                },
                "solo_jurisprudencia": {"type": "boolean", "default": False},
                "materia": {"type": "string", "default": ""},
                "instancia": {
                    "type": "string", "default": "",
                    "description": (
                        "Preset: scjn, pleno_scjn, salas_scjn, primera_sala, "
                        "segunda_sala, plenos_regionales, plenos_circuito, tcc."
                    ),
                },
                "organo": {"type": "string", "default": ""},
                "anio_minimo": {"type": "integer", "default": 0},
                "anio_maximo": {"type": "integer", "default": 0},
                "epocas": {"type": "array", "items": {"type": "string"}, "default": []},
                "buscar_en": {
                    "type": "string", "enum": ["todo", "rubro", "texto"],
                    "default": "todo",
                },
                "orden": {
                    "type": "string", "enum": ["vinculancia", "relevancia", "reciente"],
                    "default": "vinculancia",
                },
                "limite": {"type": "integer", "default": 25},
            },
            "required": ["terminos"],
        },
    },
    {
        "name": "buscar_interseccion",
        "description": (
            "Cruza 2-3 conceptos (AND) cada uno con sinónimos (OR). Útil "
            "para encontrar tesis que razonen sobre la relación entre conceptos."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "concepto_a": {"type": "array", "items": {"type": "string"}},
                "concepto_b": {"type": "array", "items": {"type": "string"}},
                "concepto_c": {"type": "array", "items": {"type": "string"}, "default": None},
                "solo_jurisprudencia": {"type": "boolean", "default": False},
                "materia": {"type": "string", "default": ""},
                "instancia": {"type": "string", "default": ""},
                "organo": {"type": "string", "default": ""},
                "anio_minimo": {"type": "integer", "default": 0},
                "anio_maximo": {"type": "integer", "default": 0},
                "epocas": {"type": "array", "items": {"type": "string"}, "default": []},
                "orden": {"type": "string", "default": "vinculancia"},
                "limite": {"type": "integer", "default": 25},
            },
            "required": ["concepto_a", "concepto_b"],
        },
    },
    {
        "name": "buscar_proximidad",
        "description": "NEAR de FTS5: dos términos a N tokens de distancia.",
        "input_schema": {
            "type": "object",
            "properties": {
                "termino_a": {"type": "string"},
                "termino_b": {"type": "string"},
                "distancia": {"type": "integer", "default": 15},
                "solo_jurisprudencia": {"type": "boolean", "default": False},
                "materia": {"type": "string", "default": ""},
                "instancia": {"type": "string", "default": ""},
                "anio_minimo": {"type": "integer", "default": 0},
                "limite": {"type": "integer", "default": 25},
            },
            "required": ["termino_a", "termino_b"],
        },
    },
    {
        "name": "buscar_rubro",
        "description": "Busca SOLO en los rubros (títulos) de las tesis. Más preciso.",
        "input_schema": {
            "type": "object",
            "properties": {
                "terminos": {"type": "array", "items": {"type": "string"}},
                "solo_jurisprudencia": {"type": "boolean", "default": False},
                "materia": {"type": "string", "default": ""},
                "instancia": {"type": "string", "default": ""},
                "anio_minimo": {"type": "integer", "default": 0},
                "limite": {"type": "integer", "default": 25},
            },
            "required": ["terminos"],
        },
    },
    {
        "name": "leer_tesis_completa",
        "description": "Lee texto completo + metadatos de UNA tesis (id_tesis, tesis_codigo o rubro).",
        "input_schema": {
            "type": "object",
            "properties": {
                "identificador": {"type": "string"},
                "campo": {
                    "type": "string", "enum": ["id_tesis", "tesis_codigo", "rubro"],
                    "default": "id_tesis",
                },
            },
            "required": ["identificador"],
        },
    },
    {
        "name": "leer_varias_tesis",
        "description": "Lee hasta 15 tesis en una sola llamada (batch). Evita N idas y vueltas.",
        "input_schema": {
            "type": "object",
            "properties": {
                "identificadores": {"type": "array", "items": {"type": "string"}},
                "campo": {
                    "type": "string", "enum": ["id_tesis", "tesis_codigo"],
                    "default": "id_tesis",
                },
            },
            "required": ["identificadores"],
        },
    },
    {
        "name": "buscar_contradiccion",
        "description": "Jurisprudencias surgidas de contradicción de tesis/criterios.",
        "input_schema": {
            "type": "object",
            "properties": {
                "terminos": {"type": "array", "items": {"type": "string"}},
                "instancia": {"type": "string", "default": ""},
                "anio_minimo": {"type": "integer", "default": 0},
                "limite": {"type": "integer", "default": 20},
            },
            "required": ["terminos"],
        },
    },
    {
        "name": "buscar_similares",
        "description": "Dada una tesis, encuentra otras con rubro similar (BM25).",
        "input_schema": {
            "type": "object",
            "properties": {
                "id_tesis": {"type": "string"},
                "limite": {"type": "integer", "default": 15},
                "solo_jurisprudencia": {"type": "boolean", "default": False},
            },
            "required": ["id_tesis"],
        },
    },
    {
        "name": "explorar_valores",
        "description": "Valores únicos de un campo de la BD (tipo_tesis, epoca, instancia, materias, organo_juris, fuente).",
        "input_schema": {
            "type": "object",
            "properties": {
                "campo": {"type": "string"},
                "limite": {"type": "integer", "default": 30},
            },
            "required": ["campo"],
        },
    },
    {
        "name": "info_base_datos",
        "description": "Estadísticas y estado actual de la base de datos.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "extraer_cita_oficial",
        "description": "Cita formal lista para pegar en escritos legales mexicanos.",
        "input_schema": {
            "type": "object",
            "properties": {
                "identificador": {"type": "string"},
                "campo": {
                    "type": "string", "enum": ["id_tesis", "tesis_codigo"],
                    "default": "id_tesis",
                },
            },
            "required": ["identificador"],
        },
    },
    {
        "name": "compilar_linea_jurisprudencial",
        "description": "Cronología de jurisprudencias sobre un tema, agrupada por época.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tema": {"type": "array", "items": {"type": "string"}},
                "anio_minimo": {"type": "integer", "default": 2010},
                "instancia": {"type": "string", "default": ""},
                "limite": {"type": "integer", "default": 30},
            },
            "required": ["tema"],
        },
    },
    {
        "name": "buscar_obligatorios_para_circuito",
        "description": (
            "Filtra jurisprudencia obligatoria para un circuito específico. "
            "Acepta número (1-32), romano (XVII) u ordinal castellano "
            "(decimo septimo)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "circuito": {"type": "string"},
                "terminos": {"type": "array", "items": {"type": "string"}},
                "limite": {"type": "integer", "default": 30},
            },
            "required": ["circuito", "terminos"],
        },
    },
]


# ════════════════════════════════════════════════════════════════════════
# Dispatch: nombre de tool → función pura
# ════════════════════════════════════════════════════════════════════════

TOOL_DISPATCH = {
    "buscar_jurisprudencia": search.buscar_jurisprudencia,
    "buscar_interseccion": search.buscar_interseccion,
    "buscar_proximidad": search.buscar_proximidad,
    "buscar_rubro": search.buscar_rubro,
    "leer_tesis_completa": search.leer_tesis_completa,
    "leer_varias_tesis": search.leer_varias_tesis,
    "buscar_contradiccion": search.buscar_contradiccion,
    "buscar_similares": search.buscar_similares,
    "explorar_valores": search.explorar_valores,
    "info_base_datos": search.info_base_datos,
    "extraer_cita_oficial": tools_v12.extraer_cita_oficial,
    "compilar_linea_jurisprudencial": tools_v12.compilar_linea_jurisprudencial,
    "buscar_obligatorios_para_circuito": tools_v12.buscar_obligatorios_para_circuito,
}


def ejecutar_tool(conn, name: str, input_data: dict) -> str:
    """Ejecuta una tool por nombre y devuelve el string de resultado."""
    fn = TOOL_DISPATCH.get(name)
    if fn is None:
        return f"Error: tool '{name}' no existe."
    try:
        return fn(conn, **input_data)
    except TypeError as e:
        return f"Error de argumentos para {name}: {e}"


# ════════════════════════════════════════════════════════════════════════
# Loop principal de tool use
# ════════════════════════════════════════════════════════════════════════

def correr_consulta(
    caso: str,
    model: str,
    max_turnos: int = 30,
    verbose: bool = False,
) -> tuple[str, dict]:
    """Ejecuta una consulta completa y devuelve (texto_final, stats).

    stats incluye: total_turnos, input_tokens, output_tokens, tools_llamadas.
    """
    client = anthropic.Anthropic()
    conn = database.connect()

    messages = [{"role": "user", "content": caso}]
    stats = {
        "total_turnos": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "tools_llamadas": [],
    }

    try:
        for turno in range(max_turnos):
            resp = client.messages.create(
                model=model,
                system=protocol.INSTRUCCIONES,
                tools=TOOLS_SCHEMA,
                messages=messages,
                max_tokens=8000,
            )
            stats["total_turnos"] += 1
            stats["input_tokens"] += resp.usage.input_tokens
            stats["output_tokens"] += resp.usage.output_tokens

            messages.append({"role": "assistant", "content": resp.content})

            if resp.stop_reason != "tool_use":
                # Texto final — concatenamos los bloques de texto.
                texto = "\n".join(
                    block.text for block in resp.content
                    if hasattr(block, "text")
                )
                return texto, stats

            # Ejecutar todas las tool_use del turno
            tool_results = []
            for block in resp.content:
                if block.type != "tool_use":
                    continue
                if verbose:
                    print(f"  → tool: {block.name}({json.dumps(block.input)[:100]})", file=sys.stderr)
                stats["tools_llamadas"].append(block.name)
                resultado = ejecutar_tool(conn, block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": resultado,
                })

            messages.append({"role": "user", "content": tool_results})

        return "[Se alcanzó el límite de turnos sin respuesta final]", stats

    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════════════
# Argparse + main
# ════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="CLI standalone para buscar jurisprudencia SCJN con la API de Anthropic.",
    )
    parser.add_argument(
        "--caso", type=Path,
        help="Archivo de texto con el caso. Si no se da, lee de stdin.",
    )
    parser.add_argument(
        "--output", type=Path,
        help="Archivo de salida. Si no se da, imprime a stdout.",
    )
    parser.add_argument(
        "--model", default="claude-sonnet-4-6",
        choices=["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5"],
        help="Modelo de Anthropic a usar (default: sonnet-4-6).",
    )
    parser.add_argument(
        "--max-turnos", type=int, default=30,
        help="Máximo de iteraciones del loop tool-use (default 30).",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Imprime cada llamada a tool en stderr.",
    )
    args = parser.parse_args()

    # Leer el caso
    if args.caso:
        if not args.caso.exists():
            print(f"ERROR: No existe {args.caso}", file=sys.stderr)
            sys.exit(1)
        caso = args.caso.read_text(encoding="utf-8")
    else:
        if sys.stdin.isatty():
            print(
                "Pega tu caso o pregunta y presiona Ctrl+D al terminar:",
                file=sys.stderr,
            )
        caso = sys.stdin.read()

    if not caso.strip():
        print("ERROR: el caso está vacío.", file=sys.stderr)
        sys.exit(1)

    print(f"→ Modelo: {args.model}", file=sys.stderr)
    print(f"→ Iniciando consulta ({len(caso)} chars)...", file=sys.stderr)

    texto, stats = correr_consulta(
        caso, args.model, max_turnos=args.max_turnos, verbose=args.verbose,
    )

    if args.output:
        args.output.write_text(texto, encoding="utf-8")
        print(f"→ Reporte guardado en {args.output}", file=sys.stderr)
    else:
        print(texto)

    # Resumen de uso
    print("", file=sys.stderr)
    print(f"  Turnos: {stats['total_turnos']}", file=sys.stderr)
    print(f"  Tools llamadas: {len(stats['tools_llamadas'])}", file=sys.stderr)
    if stats["tools_llamadas"]:
        from collections import Counter
        for nombre, n in Counter(stats["tools_llamadas"]).most_common():
            print(f"    - {nombre}: {n}", file=sys.stderr)
    print(f"  Tokens entrada: {stats['input_tokens']:,}", file=sys.stderr)
    print(f"  Tokens salida: {stats['output_tokens']:,}", file=sys.stderr)


if __name__ == "__main__":
    main()
