"""
Sanitización y construcción de expresiones FTS5.

FTS5 tiene varios caracteres con significado especial (`"`, `*`, `(`, `)`,
`+`, `^`, `{`, `}`, `[`, `]`, `~`, `:`). Si el usuario escribe un término
con uno de estos, la query truena. Estas funciones limpian los términos y
los envuelven en comillas dobles para tratarlos como frases literales.
"""

import re

# Caracteres que rompen la sintaxis MATCH de FTS5 si no se escapan.
_FTS_SPECIAL = re.compile(r'["\*\(\)\+\^\{\}\[\]~:]')


def sanitize(term: str) -> str:
    """Limpia un término y lo envuelve en comillas para usar como frase FTS5."""
    cleaned = _FTS_SPECIAL.sub(" ", term)
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        return ""
    return f'"{cleaned}"'


def build_or(terms: list[str]) -> str:
    """Construye una expresión FTS5 OR a partir de una lista de términos.

    Cada término se sanitiza y se envuelve como frase. Términos vacíos se
    ignoran. Si todos están vacíos, devuelve "".
    """
    parts = [sanitize(t) for t in terms if t and t.strip()]
    parts = [p for p in parts if p]
    return " OR ".join(parts) if parts else ""
