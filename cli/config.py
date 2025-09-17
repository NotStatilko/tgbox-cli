"""Configuration, values from EnvVars and defaults"""

from pathlib import Path
from os import getenv


PACKAGE = Path(__file__).absolute().parent

TGBOX_CLI_SHOW_PASSWORD = bool(getenv('TGBOX_CLI_SHOW_PASSWORD'))
TGBOX_CLI_NOCOLOR = bool(getenv('TGBOX_CLI_NOCOLOR'))
DEBUG_MODE = bool(getenv('TGBOX_CLI_DEBUG'))

API_ID = getenv('TGBOX_CLI_API_ID')
API_HASH = getenv('TGBOX_CLI_API_HASH')

if not all((API_ID, API_HASH)):
    # ------------------------------------------------------------------
    # |         !! WARNING !! (Devs, don't be stupid!)                 |
    # ------------------------------------------------------------------
    # | ANY USAGE of these API_ID and API_HASH values OUTSIDE of this  |
    # | project (TGBOX-CLI) inevitable will lead your Telegram account |
    # | INTO THE PERMANENT BAN!!! Get your own at my.telegram.org !!!  |
    API_HASH = '33755adb5ba3c296ccf0dd5220143841'#                     |
    API_ID = 2210681#                                                  |
    # ------------------------------------------------------------------

# Some CustomAttributes are only functional and should not be
# visible to User, e.g Multipart ones. Here we list CAttrs
# that will be hidden in format_dxbf/format_dxbf_multipart
HIDDEN_CATTRS = ['__mp_total', '__mp_previous', '__mp_part']

# _TGBOX_CLI_COMPLETE will be present in env variables
# only on source code scan by the autocompletion. To
# make a scan process faster we drop useless imports
TGBOX_CLI_COMPLETE = getenv('_TGBOX_CLI_COMPLETE')

if TGBOX_CLI_COMPLETE:
    # If TGBOX_CLI_COMPLETE is True, then we're in the "Autocomplete"
    # mode. No functions will be actually executed, only code scan
    # enabled. We can omit useless imports and speedup responsiveness
    # of CLI by instead making some hacky "Dummy" 'tgbox' class. We
    # need it because we use values from the tgbox module to pass
    # them into decorators, which *are* executed. Without it, code
    # would just throw us error. In all commands we will import the
    # "tgbox" from here.
    tgbox = type('tgbox-dummy', (), {'defaults': None})

    tgbox.defaults = type('defaults', (), {})
    tgbox.defaults.REMOTEBOX_PREFIX = None

    tgbox.defaults.Scrypt = type('', (), {})
    tgbox.defaults.Scrypt.SALT = 0
    tgbox.defaults.Scrypt.N = 0
    tgbox.defaults.Scrypt.P = 0
    tgbox.defaults.Scrypt.R = 0
    tgbox.defaults.Scrypt.DKLEN = 0

    CRYPTOGRAPHY_VERSION = None
    CRYPTG_VERSION = None
    LOGLEVEL = None
    LOGFILE = None
    VERSION = None
else: # Not Autocomplete, regular usage
    import tgbox
    import logging

    from platform import system
    from os.path import expandvars

    from .version import VERSION as CLI_VER

    if tgbox.crypto.FAST_ENCRYPTION:
        from cryptography import __version__ as CRYPTOGRAPHY_VERSION
    else:
        CRYPTOGRAPHY_VERSION = None

    if tgbox.crypto.FAST_TELETHON:
        from importlib.metadata import version as _package_version
        CRYPTG_VERSION = _package_version('cryptg')
    else:
        CRYPTG_VERSION = None

    VERSION = f'{CLI_VER}_{tgbox.defaults.VERSION}'
    tgbox.api.utils.TelegramClient.__version__ = VERSION

    if system().lower() == 'windows':
        CLI_FOLDER = Path(str(expandvars('%APPDATA%'))) / '.tgbox-cli'
    else:
        CLI_FOLDER = Path.home() / '.tgbox-cli'
    CLI_FOLDER.mkdir(parents=True, exist_ok=True)

    LOGFILE = getenv('TGBOX_CLI_LOGFILE')

    if not LOGFILE:
        LOGFILE = CLI_FOLDER / f'log{VERSION}.txt'

    elif LOGFILE in ('STDOUT', 'stdout'):
        LOGFILE = None

    LOGLEVEL = getenv('TGBOX_CLI_LOGLEVEL')
    LOGLEVEL = LOGLEVEL if LOGLEVEL else 'WARNING'

    logging.basicConfig(
        format = (
            '[%(asctime)s] %(levelname)s:%(name)s~'
            '%(funcName)s{%(lineno)s} ::: %(message)s'
        ),
        level = logging.WARNING,
        datefmt = '%Y-%m-%d, %H:%M:%S',
        filename = LOGFILE,
        filemode = 'a'
    )
    logging.getLogger('tgbox').setLevel(
        logging.getLevelName(LOGLEVEL)
    )
