# -*- mode: python ; coding: utf-8 -*-
"""
build.spec
Конфігурація PyInstaller: один файл .exe (--onefile), без консольного вікна
(--windowed), з іконкою застосунку та вкладеною текою assets/ (лого, іконка).

Запуск (у активованому venv, з кореня проєкту):
    pyinstaller build.spec --noconfirm

Готовий файл з'явиться у dist\\InvoiceGenerator.exe
"""

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets')],
    hiddenimports=[],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='InvoiceGenerator',
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
    icon='assets/app_icon.ico',
)
