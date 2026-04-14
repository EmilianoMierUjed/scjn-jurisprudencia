"""
Mensajes de error humanizados.

Las funciones de búsqueda atrapan sqlite3.OperationalError y otros errores
y los convierten en strings que el LLM (y por extensión el abogado) puede
entender. Sin esto, un error de sintaxis FTS5 le llega a Claude como un
stack trace y el LLM se confunde.
"""

import sqlite3


def humanizar(exc: Exception, contexto: str = "") -> str:
    """Devuelve un mensaje legible para una excepción de SQLite/FTS5.

    Args:
        exc: La excepción capturada.
        contexto: String corto que describe la operación (ej: "buscar
                  jurisprudencia"). Se incluye en el mensaje para dar pista.
    """
    msg = str(exc).lower()

    if isinstance(exc, sqlite3.OperationalError):
        if "fts5: syntax error" in msg or "no such column" in msg and "rubro" in msg:
            return (
                f"Error de sintaxis en la búsqueda{f' ({contexto})' if contexto else ''}. "
                "Suele pasar cuando los términos contienen caracteres especiales "
                "como comillas, paréntesis o asteriscos. Intenta reformular con "
                "palabras simples o envuelve frases en comillas dobles."
            )
        if "database is locked" in msg:
            return (
                "La base de datos está temporalmente bloqueada por otro proceso "
                "(probablemente el actualizador semanal). Espera unos segundos y "
                "vuelve a intentar."
            )
        if "no such table" in msg:
            return (
                "Falta una tabla en la base de datos. La instalación quedó "
                "incompleta. Re-ejecuta el script de instalación o contacta al "
                "instalador."
            )
        if "disk i/o error" in msg or "database disk image is malformed" in msg:
            return (
                "Error de lectura del disco — la base de datos podría estar "
                "corrupta. Restaura desde el backup más reciente o re-descárgala."
            )
        return f"Error de SQL{f' en {contexto}' if contexto else ''}: {exc}"

    if isinstance(exc, FileNotFoundError):
        return (
            f"No se encontró la base de datos: {exc}. "
            "Verifica que scjn_tesis.db esté en la carpeta data/."
        )

    if isinstance(exc, sqlite3.DatabaseError):
        return (
            f"Error al leer la base de datos{f' ({contexto})' if contexto else ''}: "
            f"{exc}. Si el problema persiste, validar con scripts/validar_bd.py."
        )

    return f"Error inesperado{f' en {contexto}' if contexto else ''}: {exc}"
