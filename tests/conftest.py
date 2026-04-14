"""
Fixtures compartidas para los tests de scjn_core.

Los tests corren contra la BD real (read-only). No mockeamos SQLite porque
queremos validar que las queries reales funcionan contra el schema y los
datos producción. Si falta la BD, los tests se skipean automáticamente.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scjn_core import database
from scjn_core.config import DB_PATH


def pytest_collection_modifyitems(config, items):
    """Skipea todos los tests si la BD no existe."""
    if not Path(DB_PATH).exists():
        skip = pytest.mark.skip(reason=f"BD no encontrada en {DB_PATH}")
        for item in items:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def conn():
    """Conexión read-only a la BD real, compartida por toda la sesión."""
    database.reset_fts_cache()
    c = database.connect()
    yield c
    c.close()
