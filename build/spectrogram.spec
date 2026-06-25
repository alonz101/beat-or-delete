# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for dj-spectrogram (on-demand full-size annotated spectrogram)

a = Analysis(
    ['../core/spectrogram_cli.py'],
    pathex=['..'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'librosa',
        'librosa.core',
        'librosa.display',
        'soundfile',
        'scipy',
        'scipy.signal',
        'scipy.fft',
        'numpy',
        'matplotlib',
        'matplotlib.pyplot',
        'numba',
        'numba.core',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['build/hook_runtime.py'],
    excludes=['tkinter', 'PyQt5', 'wx', 'mutagen', 'pyloudnorm', 'reportlab'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='dj-spectrogram',
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
    name='dj-spectrogram',
)
