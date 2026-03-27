# -*- mode: python ; coding: utf-8 -*-
# Run on Windows: py -m PyInstaller --noconfirm --clean windows_build.spec
from PyInstaller.utils.hooks import collect_all

block_cipher = None

datas_s6, binaries_s6, hiddenimports_s6 = collect_all("PySide6")
datas_qf, binaries_qf, hiddenimports_qf = collect_all("qfluentwidgets")

a = Analysis(
    ["boxclaw_main.py"],
    pathex=[],
    binaries=binaries_s6 + binaries_qf,
    datas=datas_s6 + datas_qf,
    hiddenimports=hiddenimports_s6
    + hiddenimports_qf
    + [
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebChannel",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BoxClaw",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="BoxClaw",
)
