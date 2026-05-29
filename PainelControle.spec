# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('fotos', 'fotos'), ('presets', 'presets'), ('templates', 'templates'), ('vereadores.json', '.'), ('session_config.json', '.'), ('GC GERAL.png', '.'), ('Manual_de_Hardware.html', '.'), ('modelo_vereadores.csv', '.')],
    hiddenimports=['simple_websocket', 'engineio.async_drivers.threading'],
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
    [],
    exclude_binaries=True,
    name='PainelControle',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['fotos\\icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PainelControle',
)
