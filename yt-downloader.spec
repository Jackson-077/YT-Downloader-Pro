# -*- mode: python ; coding: utf-8 -*-
# Spec único para Linux (.deb) e Windows (.exe):
#   pyinstaller --clean yt-downloader.spec
import os
import sys
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = ['PIL._tkinter_finder', 'yt_dlp.cookies', 'browser_cookie3']

# yt_dlp (todos os extratores), curl_cffi (impersonate) e o provedor de PO Token
# precisam entrar COMPLETOS no executável, senão alguns sites/recursos falham.
for pacote in ('customtkinter', 'PIL', 'yt_dlp', 'curl_cffi', 'certifi',
               'keyring', 'secretstorage', 'bgutil_ytdlp_pot_provider',
               'yt_dlp_plugins'):
    try:
        d, b, h = collect_all(pacote)
        datas += d; binaries += b; hiddenimports += h
    except Exception as e:
        print(f'[spec] aviso: {pacote} não incluído ({e})')

# Ícone da janela (lido por recurso() no app)
if os.path.exists('icone.png'):
    datas.append(('icone.png', '.'))

icone_exe = 'icone.ico' if (sys.platform == 'win32' and os.path.exists('icone.ico')) else None

a = Analysis(
    ['yt_downloader.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='yt-downloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX costuma disparar falso positivo em antivírus no Windows
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icone_exe,
)
