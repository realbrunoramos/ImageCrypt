# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['ImageCrypt.py'],
    pathex=[],
    binaries=[],
    datas=[('bg.svg', '.'), ('bg2.svg', '.'), ('bg3.svg', '.'), ('bg2-1.png', '.'), ('bg2-2.png', '.'), ('eye0.png', '.'), ('eye1.png', '.'), ('ic_splash.png', '.'), ('Searching IC.gif', '.')],
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
    name='ImageCrypt',
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
    icon=['iconIC.ico'],
)
