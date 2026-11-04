# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH).parent
datas = [(str(root / 'assets'), 'assets'), (str(root / 'LICENSE'), '.'),
         (str(root / 'THIRD-PARTY-NOTICES.md'), '.')]
binaries, hiddenimports = [], []
for package in ('zxingcpp', 'psutil'):
    pd, pb, ph = collect_all(package)
    datas += pd
    binaries += pb
    hiddenimports += ph
a = Analysis([str(root / 'launcher.py')], pathex=[str(root)], binaries=binaries,
    datas=datas, hiddenimports=hiddenimports, hookspath=[], runtime_hooks=[],
    excludes=['pytest', 'qrcode', 'matplotlib', 'torch', 'paddle', 'scipy'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='QRLiveScanner',
    console=False, upx=False, strip=False, icon=str(root / 'assets/app.ico'))
coll = COLLECT(exe, a.binaries, a.datas, name='QRLiveScanner', upx=False, strip=False)
