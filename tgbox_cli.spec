from tgbox.constants import PYINSTALLER_DATA

a = Analysis(
    ['tgbox_cli/tgbox_cli.py'],
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
    icon = 'tgbox-cli_logo.ico',
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
