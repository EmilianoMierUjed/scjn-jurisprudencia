"""
scjn_core — núcleo de la herramienta de jurisprudencia SCJN.

Paquete con la lógica de búsqueda, filtros, ranking y formato. Es agnóstico
del transporte: lo usan tanto el MCP server (server/server.py) como el CLI
standalone (cli/scjn_cli.py).

Importa así desde fuera del paquete:

    from scjn_core import search, protocol, database
    conn = database.connect()
    print(search.buscar_jurisprudencia(conn, ["derecho a la salud"]))
"""

from . import (
    config,
    database,
    errores,
    filters,
    format,
    fts,
    protocol,
    ranking,
    search,
    tools_v12,
)

__all__ = [
    "config",
    "database",
    "errores",
    "filters",
    "format",
    "fts",
    "protocol",
    "ranking",
    "search",
    "tools_v12",
]
