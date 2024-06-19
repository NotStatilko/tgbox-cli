from pathlib import Path
from platform import system

from tgbox.defaults import PYINSTALLER_DATA
try:
    # Cryptg doesn't have __version__, so we need to check
    # it from the package metadata. However, on making
    # onefile EXE modern PyInstaller doesn't catch it,
    # so it result in error. Here we add it.
    from PyInstaller.utils.hooks import copy_metadata
    cryptg_metadata = copy_metadata('cryptg')
except ImportError: # Some old PyInstaller?
    cryptg_metadata = []


if Path.cwd().name != 'pyinstaller':
    raise RuntimeError('You should build App inside the "pyinstaller" folder.')

TGBOX_CLI_FOLDER = Path.cwd().parent / 'tgbox_cli'
DATA_FOLDER = TGBOX_CLI_FOLDER / 'data'

SCRIPT_LOGO = DATA_FOLDER / 'logo.ico'
MAIN_SCRIPT = Path.cwd() / '.tgbox_cli_wrapper.py'

TGBOX_CLI_DATA: dict = {
    str(Path('data', i.name)): str(i)
    for i in DATA_FOLDER.glob('*')
}
PYINSTALLER_DATA.update(TGBOX_CLI_DATA)

if system().lower() == 'windows':
    # Enlighten may require ANSICON DLLs (32/64) on the Windows machine
    PYINSTALLER_DATA['ansicon/ANSI32.dll'] = 'depends/ansicon/ANSI32.dll'
    PYINSTALLER_DATA['ansicon/ANSI64.dll'] = 'depends/ansicon/ANSI64.dll'

a = Analysis(
    [MAIN_SCRIPT],
    pathex = [str(TGBOX_CLI_FOLDER.parent)],
    binaries = [],
    datas = [*cryptg_metadata],
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
    a.pure,
    a.zipped_data,
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
