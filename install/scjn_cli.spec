# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec para el CLI standalone (modo API Anthropic).

Construye `scjn-cli.exe`, un binario que el abogado puede correr sin
instalar Python ni saber qué es un venv.

Uso después de buildear:
    set ANTHROPIC_API_KEY=sk-ant-...
    scjn-cli.exe --caso casos\\amparo_issste.txt --output reporte.md

Build:
    pyinstaller install/scjn_cli.spec --clean

Output:
    dist/scjn-cli.exe
"""

from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

SPEC_DIR = Path(SPECPATH).resolve()
REPO_ROOT = SPEC_DIR.parent

block_cipher = None


hiddenimports = []
hiddenimports += collect_submodules("anthropic")
hiddenimports += collect_submodules("httpx")
hiddenimports += collect_submodules("httpcore")
hiddenimports += collect_submodules("pydantic")
hiddenimports += collect_submodules("pydantic_core")
hiddenimports += collect_submodules("anyio")
hiddenimports += collect_submodules("scjn_core")
hiddenimports += [
    "sqlite3",
    "sqlite3.dbapi2",
    "_sqlite3",
]

datas = []
datas += collect_data_files("anthropic")
datas += collect_data_files("pydantic")
# certifi trae el bundle de CAs que httpx usa para HTTPS.
datas += collect_data_files("certifi")


a = Analysis(
    [str(REPO_ROOT / "cli" / "scjn_cli.py")],
    pathex=[str(REPO_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
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
    name="scjn-cli",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
