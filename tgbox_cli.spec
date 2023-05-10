from tgbox.defaults import PYINSTALLER_DATA
from pathlib import Path

MAIN_SCRIPT = Path('tgbox_cli') / 'tgbox_cli.py'
SCRIPT_LOGO = Path('tgbox_cli') / 'data' / 'logo.ico'

pyinstaller_datas = [('tgbox_cli/data/*', 'tgbox_cli/data/')]

for k,v in PYINSTALLER_DATA.items():
    pyinstaller_datas.append((k, v, 'DATA'))

a = Analysis(
    [str(MAIN_SCRIPT)],
    pathex = [],
    binaries = [],
    datas = pyinstaller_datas,
    hiddenimports = [],
    hookspath = [],
    hooksconfig = {},
    runtime_hooks = [],
    excludes = [],
    win_no_prefer_redirects = False,
    win_private_assemblies = False,
    cipher = None,
    noarchive = False
)
pyz = PYZ(
    a.pure, a.zipped_data,
    cipher = None
)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas, [],
    name = 'tgbox-cli',
    icon = str(SCRIPT_LOGO),
    debug = False,
    bootloader_ignore_signals = False,
    strip = False,
    upx = True,
    upx_exclude = [],
    runtime_tmpdir = None,
    console = True,
    disable_windowed_traceback = False,
    target_arch = None,
    codesign_identity = None,
    entitlements_file = None
)
