# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for dj-batch (folder batch analysis + export)

import os

FFPROBE = '/opt/homebrew/bin/ffprobe'

a = Analysis(
    ['../batch.py'],
    pathex=['..'],
    binaries=[(FFPROBE, '.')],
    datas=[],
    hiddenimports=[
        'librosa',
        'librosa.core',
        'librosa.feature',
        'soundfile',
        'scipy',
        'scipy.signal',
        'scipy.fft',
        'numpy',
        'matplotlib',
        'matplotlib.pyplot',
        'pyloudnorm',
        'mutagen',
        'mutagen.flac',
        'mutagen.mp3',
        'mutagen.aiff',
        'mutagen.wave',
        'reportlab',
        'reportlab.platypus',
        'reportlab.lib',
        'numba',
        'numba.core',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['build/hook_runtime.py'],
    excludes=['tkinter', 'PyQt5', 'wx'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='dj-batch',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='dj-batch',
)
