# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec para el servidor MCP de SCJN.

Construye un único ejecutable `scjn-mcp-server.exe` que Claude Desktop
puede invocar como subproceso. Sin esto, el cliente tiene que instalar
Python, configurar PYTHONPATH y rezar para que `where python` funcione.

Build (en Windows desde la raíz del repo):
    pyinstaller install/scjn_mcp_server.spec --clean

Output:
    dist/scjn-mcp-server.exe (~30-50 MB esperado)

Notas:
- La BD `scjn_tesis.db` NO se incluye en el bundle (es muy pesada y se
  distribuye por separado en `C:\\scjn-tool\\data\\`).
- DB_PATH se pasa por env var desde claude_desktop_config.json.
- `mcp` y `pydantic` traen módulos cargados dinámicamente que PyInstaller
  no detecta solo — los listamos en `hiddenimports` y `collect_submodules`.
"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# El spec se invoca desde la raíz del repo (`pyinstaller install/...spec`)
# así que el cwd es la raíz; resolvemos las rutas relativas a este archivo.
SPEC_DIR = Path(SPECPATH).resolve()
REPO_ROOT = SPEC_DIR.parent

block_cipher = None


# ── Submódulos cargados dinámicamente ────────────────────────────────────
# `mcp` y sus dependencias usan importlib bajo el capó.
hiddenimports = []
hiddenimports += collect_submodules("mcp")
hiddenimports += collect_submodules("pydantic")
hiddenimports += collect_submodules("pydantic_core")
hiddenimports += collect_submodules("anyio")
hiddenimports += collect_submodules("scjn_core")
hiddenimports += [
    "sqlite3",
    "sqlite3.dbapi2",
    "_sqlite3",
]

# Algunos paquetes traen .json/.pyi que necesitan estar en disco.
datas = []
datas += collect_data_files("mcp")
datas += collect_data_files("pydantic")


a = Analysis(
    [str(REPO_ROOT / "server" / "server.py")],
    pathex=[str(REPO_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Cosas grandes que NO necesitamos — recortan el .exe.
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
        "PIL",
        "PySide6",
        "PyQt5",
        "PyQt6",
        "test",
        "unittest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="scjn-mcp-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Claude Desktop habla con el server por stdin/stdout.
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
