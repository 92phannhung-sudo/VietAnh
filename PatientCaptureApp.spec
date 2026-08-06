# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

block_cipher = None

datas = []

if os.path.exists('config.json'):
    datas.append(('config.json', '.'))
if os.path.exists('models'):
    datas.append(('models', 'models'))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtWidgets',
        'PySide6.QtGui',
        'cv2',
        'pyaudio',
        'faster_whisper',
        'ctranslate2',
        'keyboard',
        'sqlite3',
        'winsound',
        'barcode_parser',
        'action_registry',
        'database',
        'voice_detector',
        'pedal_gesture_fsm',
        'hardware_test_dialogs',
        'updater',
        'config'
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
    name='PatientCaptureApp',
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PatientCaptureApp',
)
