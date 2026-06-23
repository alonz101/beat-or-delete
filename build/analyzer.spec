# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for dj-analyze (single-file analysis)

import os

# Path to the ffprobe binary to bundle
FFPROBE = '/opt/homebrew/bin/ffprobe'

a = Analysis(
    ['../core/analyzer.py'],
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
    name='dj-analyze',
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
    name='dj-analyze',
)
