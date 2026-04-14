"""
Configuración global del paquete: rutas, límites, logger.

DB_PATH se resuelve por env var, con fallback a la ubicación canónica
relativa al repo. El logger escribe a stderr (NUNCA a stdout — stdout es el
canal MCP cuando el server corre como subproceso).
"""

import logging
import os
import sys
from pathlib import Path

# ── Ruta de la base de datos ─────────────────────────────────────────────
# pyproject.toml está en la raíz del repo. scjn_core/ vive al lado de data/.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_DB = str(_REPO_ROOT / "data" / "scjn_tesis.db")

DB_PATH = os.environ.get("DB_PATH", _DEFAULT_DB)

# ── Límites de output ────────────────────────────────────────────────────
# Cuando se listan resultados, recortamos el extracto del texto para no
# explotar el context window de Claude con 25 tesis de 2000 chars.
MAX_EXTRACTO = 500
# Cuando se lee el texto completo de UNA tesis, sí dejamos llegar más, pero
# truncamos para tesis monstruosas.
MAX_TEXTO_COMPLETO = 8000


# ── Logger ───────────────────────────────────────────────────────────────
def get_logger(name: str = "scjn") -> logging.Logger:
    """Devuelve un logger configurado para escribir a stderr."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(stream=sys.stderr)
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
