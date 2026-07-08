# -*- mode: python ; coding: utf-8 -*-
# PyInstaller-Spec fuer die moderne Version (CustomTkinter).
# Build:  pyinstaller gui_rue_generator_modern.spec
# Ergebnis: dist/RUE-Generator.exe  (eine Datei, ohne Konsolenfenster)

from PyInstaller.utils.hooks import collect_data_files

# CustomTkinter bringt Theme-JSONs und Assets mit, die gebuendelt werden
# muessen; projekte.json wird als Fallback in die EXE eingebettet.
# Liegt eine projekte.json NEBEN der EXE, hat sie Vorrang (Datenpflege
# ohne Neubau moeglich).
datas = [('projekte.json', '.')]
datas += collect_data_files('customtkinter')

a = Analysis(
    ['gui_rue_generator_modern.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='RUE-Generator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
