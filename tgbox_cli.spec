from pathlib import Path
from tgbox.defaults import PYINSTALLER_DATA

TGBOX_CLI_FOLDER = Path('tgbox_cli')
DATA_FOLDER = TGBOX_CLI_FOLDER / 'data'

SCRIPT_LOGO = DATA_FOLDER / 'logo.ico'
MAIN_SCRIPT = TGBOX_CLI_FOLDER / 'tgbox_cli.py'

TGBOX_CLI_DATA: dict = {
    str(Path('data', i.name)): str(i)
    for i in DATA_FOLDER.glob('*')
}
PYINSTALLER_DATA.update(TGBOX_CLI_DATA)

a = Analysis(
    [str(MAIN_SCRIPT)],
    pathex = [],
    binaries = [],
    datas = [],
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
for k,v in PYINSTALLER_DATA.items():
    a.datas += [(k, v, 'DATA')]

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
