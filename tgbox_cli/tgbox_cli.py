#!/usr/bin/env python3

import click
import logging

from os import getenv
from typing import Union
from pathlib import Path


# _TGBOX_CLI_COMPLETE will be present in env variables
# only on source code scan by the autocompletion. To
# make a scan process faster we drop useless imports
if getenv('_TGBOX_CLI_COMPLETE'):
    # Here we make a dummy tgbox class
    # for the type hints.
    tgbox = type('', (), {})

    tgbox.defaults = type('', (), {})
    tgbox.defaults.REMOTEBOX_PREFIX = None

    tgbox.defaults.Scrypt = type('', (), {})
    tgbox.defaults.Scrypt.SALT = 0
    tgbox.defaults.Scrypt.N = 0
    tgbox.defaults.Scrypt.P = 0
    tgbox.defaults.Scrypt.R = 0
    tgbox.defaults.Scrypt.DKLEN = 0
else:
    try:
        # Will be presented if run
        # from the PyInstaller EXE
        from sys import _MEIPASS
    except ImportError:
        _MEIPASS = None

    import tgbox
    import logging

    from time import sleep
    from hashlib import sha256

    from platform import system
    from datetime import datetime
    from pickle import loads, dumps

    from base64 import urlsafe_b64encode
    from shutil import get_terminal_size
    from traceback import format_exception

    from subprocess import run as subprocess_run, PIPE
    from code import interact as interactive_console
    from asyncio import gather, get_event_loop

    from os import getenv, _exit
    from os.path import expandvars

    if _MEIPASS:
        # PyInstaller builds has some problems in
        # importing modules started with dots, so
        # here we will make an import from package
        from tgbox_cli.tools import *
        from tgbox_cli.version import *
    else:
        from .tools import *
        from .version import *

    from telethon.errors.rpcerrorlist import (
        UsernameNotOccupiedError, UsernameInvalidError
    )
    from enlighten import get_manager as get_enlighten_manager


    TGBOX_CLI_NOCOLOR = bool(getenv('TGBOX_CLI_NOCOLOR'))

    # tools.color with a click.echo function
    echo = lambda t,**k: click.echo(color(t), **k, color=(not TGBOX_CLI_NOCOLOR))

    __version__ = f'{VERSION}_{tgbox.defaults.VERSION}'
    tgbox.api.utils.TelegramClient.__version__ = __version__

    API_ID, API_HASH = getenv('TGBOX_CLI_API_ID'), getenv('TGBOX_CLI_API_HASH')

    if not API_ID or not API_HASH:
        # Please DO NOT use this parameters in your projects.
        # You can get your own at my.telegram.org. Thanks.
        API_ID, API_HASH = 2210681, '33755adb5ba3c296ccf0dd5220143841'


    cli_folders = {
        'windows': Path(str(expandvars('%APPDATA%'))) / '.tgbox-cli',
        '_other_os': Path.home() / '.tgbox-cli'
    }
    cli_folder = cli_folders.get(system().lower(), cli_folders['_other_os'])
    cli_folder.mkdir(parents=True, exist_ok=True)


    logger = logging.getLogger(__name__)

    logging_level = getenv('TGBOX_CLI_LOGLEVEL')
    logging_level = logging_level if logging_level else 'WARNING'

    logfile = getenv('TGBOX_CLI_LOGFILE')

    if not logfile:
        logfile = cli_folder / f'log{__version__}.txt'

    logging.basicConfig(
        format = (
            '''[%(asctime)s] %(levelname)s:%(name)s~'''
            '''%(funcName)s{%(lineno)s} ::: %(message)s'''
        ),
        level = logging.WARNING,
        datefmt = '%Y-%m-%d, %H:%M:%S',
        filename = logfile,
        filemode = 'a'
    )
    logging.getLogger('tgbox').setLevel(
        logging.getLevelName(logging_level)
    )
    # Progressbar manager
    enlighten_manager = get_enlighten_manager()

# ACTIVE_BOX will store current pair of dlb & drb
# to easily close it on program exit.
ACTIVE_BOX = []

class ExitProgram(click.Abort):
    """Will be raised to exit CLI"""

# = Functions for operating on temp CLI session =========== #

def get_sk() -> Union[str, None]:
    """
    This will return StateKey
    from env vars, if present.
    """
    return getenv('TGBOX_CLI_SK')

def check_sk(echo_error: bool=True):
    """Will check if TGBOX_CLI_SK present in env vars"""
    if not get_sk():
        if echo_error:
            echo(
                '''[RED]You should run[RED] [WHITE]tgbox-cli '''
                '''cli-init[WHITE] [RED]firstly.[RED]'''
            )
        raise ExitProgram
    else:
        return True

def get_state(state_key: str) -> dict:
    state_enc_key = sha256(state_key.encode()).digest()
    state_file = cli_folder / f'sess_{sha256(state_enc_key).hexdigest()}'

    if not state_file.exists():
        return {}
    else:
        with open(state_file,'rb') as f:
            d = tgbox.crypto.AESwState(state_enc_key).decrypt(f.read())
            return loads(d)

def write_state(state: dict, state_key: str) -> None:
    state_enc_key = sha256(state_key.encode()).digest()
    state_file = cli_folder / f'sess_{sha256(state_enc_key).hexdigest()}'

    with open(state_file,'wb') as f:
        f.write(tgbox.crypto.AESwState(state_enc_key).encrypt(dumps(state)))

# ========================================================= #

# = Functions for extracting Account/Box data from sesssion #

def get_box(ignore_remote: bool=False, raise_if_none: bool=False):
    check_sk(echo_error=(not raise_if_none))

    state_key = get_sk()
    state = get_state(state_key)

    if ACTIVE_BOX:
        return ACTIVE_BOX[0], ACTIVE_BOX[1]

    if 'TGBOXES' not in state:
        if raise_if_none:
            raise ExitProgram
        echo(
            '''[RED]You didn\'t connected box yet. Use[RED] '''
            '''[WHITE]box-open[WHITE] [RED]command.[RED]'''
        )
        raise ExitProgram
    else:
        box_path = state['TGBOXES'][state['CURRENT_TGBOX']][0]
        basekey  = state['TGBOXES'][state['CURRENT_TGBOX']][1]

        dlb = tgbox.sync(tgbox.api.get_localbox(
            tgbox.keys.BaseKey(basekey), box_path)
        )
        if not ignore_remote:
            if getenv('https_proxy'):
                proxy = env_proxy_to_pysocks(getenv('https_proxy'))

            elif getenv('http_proxy'):
                proxy = env_proxy_to_pysocks(getenv('http_proxy'))
            else:
                proxy = None

            drb = tgbox.sync(tgbox.api.get_remotebox(dlb, proxy=proxy))
        else:
            drb = None

        ACTIVE_BOX.append(dlb)
        ACTIVE_BOX.append(drb)

        return ACTIVE_BOX[0], ACTIVE_BOX[1]

def select_remotebox(number: int, prefix: str):
    tc, count, erb = get_account(), 1, None

    for d in sync_async_gen(tc.iter_dialogs()):
        if prefix in d.title and d.is_channel:
            if count != number:
                count += 1
            else:
                erb = tgbox.api.remote.EncryptedRemoteBox(d,tc)
                break

    if not erb:
        echo(f'[RED]RemoteBox by number={number} not found.[RED]')
        raise ExitProgram
    else:
        return erb

def get_account() -> 'tgbox.api.TelegramClient':
    check_sk()

    state_key, tc = get_sk(), None
    state = get_state(state_key)

    if 'ACCOUNTS' not in state and 'CURRENT_TGBOX' in state:
        echo(
            '''\nYou [RED]didn\'t connected[RED] account with '''
            '''[WHITE]account-connect, [WHITE]\n    however, you '''
            '''already connected Box.'''
        )
        if click.confirm('\nDo you want to use its account?'):
            dlb, drb = get_box()
            tc = drb._tc
            tgbox.sync(dlb.done())

    elif 'ACCOUNTS' in state:
        session = state['ACCOUNTS'][state['CURRENT_ACCOUNT']]

        tc = tgbox.api.TelegramClient(
            session=session,
            api_id=API_ID,
            api_hash=API_HASH
        )
    if not tc:
        echo(
          '''[RED]You should run [RED][WHITE]tgbox-cli '''
          '''account-connect [WHITE][RED]firstly.[RED]'''
        )
        raise ExitProgram

    if getenv('https_proxy'):
        proxy = env_proxy_to_pysocks(getenv('https_proxy'))

    elif getenv('http_proxy'):
        proxy = env_proxy_to_pysocks(getenv('http_proxy'))
    else:
        proxy = None

    tc.set_proxy(proxy)
    tgbox.sync(tc.connect())
    return tc

# ========================================================= #

# = CLI configuration ===================================== #

class StructuredGroup(click.Group):
    def __init__(self, name=None, commands=None, **kwargs):
        super().__init__(name, commands, **kwargs)
        self.commands = commands or {}

    def list_commands(self, ctx):
        return self.commands

    def format_commands(self, ctx, formatter):
        formatter.width = get_terminal_size().columns

        formatter.write_text('')
        formatter.write_heading('Commands')

        largest_command = max(self.commands, key=lambda k: len(k))
        shift = len(largest_command) + 2

        last_letter = None
        for k,v in self.commands.items():
            if v.hidden:
                continue

            if last_letter != k[0]:
                last_letter = k[0]
                formatter.write_paragraph()

            if v.name.lower() == 'help':
                if TGBOX_CLI_NOCOLOR:
                    name = v.name
                else:
                    name = color(f'[GREEN]{v.name}[GREEN]')
            else:
                if TGBOX_CLI_NOCOLOR:
                    name = v.name
                else:
                    name = color(f'[WHITE]{v.name}[WHITE]')

            formatter.write_text(
                f'  o  {name} :: {v.get_short_help_str().strip()}'
            )
        formatter.write_text('\x1b[0m')

@click.group(cls=StructuredGroup)
def cli():
   pass

# ========================================================= #

# = CLI manage & setup commands =========================== #

@cli.command()
def cli_init():
    """Get commands for initializing TGBOX-CLI"""
    if get_sk():
        echo('[WHITE]CLI is already initialized.[WHITE]')
    else:
        if system().lower() == 'windows':
            commands = (
                '''(for /f %i in (\'tgbox-cli sk-gen\') '''
                '''do set "TGBOX_CLI_SK=%i") > NUL\n'''
                '''chcp 65001 || # Change the default CMD encoding to UTF-8'''
            )
        else:
            current_shell = getenv('SHELL')
            if current_shell and 'bash' in current_shell:
                autocomplete = 'eval "$(_TGBOX_CLI_COMPLETE=bash_source tgbox-cli)"'
            elif current_shell and 'zsh' in current_shell:
                autocomplete = 'eval "$(_TGBOX_CLI_COMPLETE=zsh_source tgbox-cli)"'
            elif current_shell and 'fish' in current_shell:
                autocomplete = 'eval (env _TGBOX_CLI_COMPLETE=fish_source tgbox-cli)'
            else:
                autocomplete = None

            if autocomplete:
                echo('\n# [BLUE](Execute commands below if eval doesn\'t work)[BLUE]\n')

                real_commands = (
                    '''export TGBOX_CLI_SK="$(tgbox-cli sk-gen)"\n'''
                    f'''{autocomplete}'''
                )
                echo(real_commands)

                commands = 'eval "$(!!)" || true && clear'
            else:
                commands = 'export TGBOX_CLI_SK="$(tgbox-cli sk-gen)"'

        echo(
            '''\n[YELLOW]Welcome to the TGBOX-CLI![YELLOW]\n\n'''
            '''Copy & Paste commands below to your shell:\n\n'''
           f'''[WHITE]{commands}[WHITE]\n'''
        )

@cli.command()
def cli_info():
    """Get base information about TGBOX-CLI"""

    ver = __version__.split('_')
    try:
        sp_result = subprocess_run(
            args=[tgbox.defaults.FFMPEG, '-version'],
            stdout=PIPE, stderr=None
        )
        ffmpeg_version = f"[GREEN]{sp_result.stdout.split(b' ',3)[2].decode()}[GREEN]"
    except:
        ffmpeg_version = '[RED]NOT FOUND[RED]'

    if tgbox.crypto.FAST_ENCRYPTION:
        fast_encryption = '[GREEN]YES[GREEN]'
    else:
        fast_encryption = '[RED]NO[RED]'

    if tgbox.crypto.FAST_TELETHON:
        fast_telethon = '[GREEN]YES[GREEN]'
    else:
        fast_telethon = '[RED]NO[RED]'

    echo(
        '''\n# Copyright [WHITE](c) Non [github.com/NotStatilko][WHITE], the MIT License\n'''
        '''# Author Email: [WHITE]thenonproton@protonmail.com[WHITE]\n\n'''

        f'''TGBOX-CLI Version: [YELLOW]{ver[0]}[YELLOW]\n'''
        f'''TGBOX Version: [MAGENTA]{ver[1]}[MAGENTA]\n\n'''

        f'''FFMPEG: {ffmpeg_version}\n'''
        f'''FAST_ENCRYPTION: {fast_encryption}\n'''
        f'''FAST_TELETHON: {fast_telethon}\n\n'''

        f'''LOGLEVEL: [BLUE]{logging_level}[BLUE]\n'''
        f'''LOGFILE: [BLUE]{logfile.name}[BLUE]\n'''
    )

# ========================================================= #

# = Telegram account management commands ================== #

@cli.command()
@click.option(
    '--phone', '-p', required=True, prompt=True,
    help='Phone number of your Telegram account'
)
def account_connect(phone):
    """Connect to Telegram"""
    check_sk()

    tc = tgbox.api.TelegramClient(
        phone_number=phone,
        api_id=API_ID,
        api_hash=API_HASH
    )
    echo('[CYAN]Connecting to Telegram...[CYAN]')
    tgbox.sync(tc.connect())

    echo('[CYAN]Sending code request...[CYAN]')
    tgbox.sync(tc.send_code())

    code = click.prompt('Received code', type=int)

    password = click.prompt(
        text = 'Password',
        hide_input = True,
        default = '',
        show_default = False
    )
    echo('[CYAN]Trying to sign-in...[CYAN] ', nl=False)
    tgbox.sync(tc.log_in(code=code, password=password))

    echo('[GREEN]Successful![GREEN]')
    echo('[CYAN]Updating local data...[CYAN] ', nl=False)

    state_key = get_sk()
    state = get_state(state_key)

    tc_id = tgbox.sync(tc.get_me()).id

    if 'ACCOUNTS' not in state:
        state['ACCOUNTS'] = [tc.session.save()]
        state['CURRENT_ACCOUNT'] = 0 # Index
    else:
        disconnected_sessions = []
        for session in state['ACCOUNTS']:

            other_tc = tgbox.api.TelegramClient(
                session=session,
                api_id=API_ID,
                api_hash=API_HASH
            )
            other_tc = tgbox.sync(other_tc.connect())
            try:
                other_tc_id = tgbox.sync(other_tc.get_me()).id
            except AttributeError:
                # If session was disconnected
                disconnected_sessions.append(session)
                continue

            if other_tc_id == tc_id:
                tgbox.sync(tc.log_out())
                echo('[RED]Account already added[RED]')
                raise ExitProgram

        for d_session in disconnected_sessions:
            state['ACCOUNTS'].remove(d_session)

        state['ACCOUNTS'].append(tc.session.save())
        state['CURRENT_ACCOUNT'] = len(state['ACCOUNTS']) - 1

    write_state(state, state_key)
    echo('[GREEN]Successful![GREEN]')
    raise ExitProgram

@cli.command()
@click.option(
    '--number','-n', required=True, type=int,
    help='Number of connected account'
)
@click.option(
    '--log-out', is_flag=True,
    help='Will log out from account if specified'
)
def account_disconnect(number, log_out):
    """Will disconnect selected account from TGBOX-CLI"""
    state_key = get_sk()
    state = get_state(state_key)

    if 'ACCOUNTS' not in state or not state['ACCOUNTS']:
        echo('[RED]You don\'t have any connected account.[RED]')
        raise ExitProgram

    elif number < 1 or number > len(state['ACCOUNTS']):
        echo(
            f'''[RED]There is no account #{number}. Use [RED]'''
             '''[WHITE]account-list[WHITE] [RED]command.[RED]'''
        )
    if log_out:
        session = state['ACCOUNTS'][number-1]

        tc = tgbox.api.TelegramClient(
            session=session,
            api_id=API_ID,
            api_hash=API_HASH
        )
        tgbox.sync(tc.connect())
        tgbox.sync(tc.log_out())

    state['ACCOUNTS'].pop(number-1)

    if not state['ACCOUNTS']:
        state.pop('ACCOUNTS')
        state.pop('CURRENT_ACCOUNT')
        echo('[GREEN]Disconnected. No more accounts.[GREEN]')
    else:
        state['CURRENT_ACCOUNT'] = 0
        echo('[GREEN]Disconnected & switched to the account #1[GREEN]')

    write_state(state, state_key)
    raise ExitProgram

@cli.command()
def account_list():
    """List all connected accounts"""
    check_sk()

    state_key = get_sk()
    state = get_state(state_key)

    if 'ACCOUNTS' not in state or not state['ACCOUNTS']:
        echo(
            '''[RED]You didn\'t connected any account yet. Use[RED] '''
            '''[WHITE]account-connect[WHITE] [RED]command firstly.[RED]'''
        )
    else:
        echo(
            '''\n[WHITE]You\'re using account[WHITE] [RED]'''
           f'''#{str(state['CURRENT_ACCOUNT'] + 1)}[RED]\n'''
        )
        disconnected_sessions = []
        for count, session in enumerate(state['ACCOUNTS']):
            try:
                tc = tgbox.api.TelegramClient(
                    session=session,
                    api_id=API_ID,
                    api_hash=API_HASH
                )
                tgbox.sync(tc.connect())
                info = tgbox.sync(tc.get_me())

                name = f'@{info.username}' if info.username else info.first_name
                echo(f'[WHITE]{count+1})[WHITE] [BLUE]{name}[BLUE] (id{info.id})')
            except AttributeError:
                # If session was disconnected
                echo(f'[WHITE]{count+1})[WHITE] [RED]disconnected, so removed[RED]')
                disconnected_sessions.append(session)

        for d_session in disconnected_sessions:
            state['ACCOUNTS'].remove(d_session)

        write_state(state, state_key)

    raise ExitProgram

@cli.command()
@click.option(
    '--number', '-n', required=True, type=int,
    help='Number of other connected account, use account-list command'
)
def account_switch(number):
    """This will set your CURRENT_ACCOUNT to selected"""
    check_sk()

    state_key = get_sk()
    state = get_state(state_key)

    if 'ACCOUNTS' not in state:
        echo(
            '''[RED]You didn\'t connected any account yet. Use[RED] '''
            '''[WHITE]account-connect[WHITE] [RED]command firstly.[RED]'''
        )
    elif number < 1 or number > len(state['ACCOUNTS']):
        echo(
            f'''[RED]There is no account #{number}. Use [RED]'''
             '''[WHITE]account-list[WHITE] [RED]command.[RED]'''
        )
    elif number == state['CURRENT_ACCOUNT']:
        echo(
            f'''[YELLOW]You already on this account. See other with[YELLOW] '''
             '''[WHITE]account-list[WHITE] [YELLOW]command.[YELLOW]'''
        )
    else:
        state['CURRENT_ACCOUNT'] = number
        write_state(state, state_key)
        echo(f'[GREEN]You switched to account #{number}[GREEN]')

    raise ExitProgram

@cli.command()
@click.option(
    '--show-phone', is_flag=True,
    help='Specify this to show phone number'
)
def account_info(show_phone):
    """Show information about current account"""

    tc = get_account()
    me = tgbox.sync(tc.get_me())

    last_name = me.last_name if me.last_name else ''
    full_name = f'[WHITE]{me.first_name} {last_name}[WHITE]'

    if show_phone:
        phone = f'[WHITE]+{me.phone}[WHITE]'
    else:
        phone = '[RED]<Was hidden>[RED]'

    if me.premium:
        premium = '[WHITE]yes[WHITE]'
    else:
        premium = '[RED]no[RED]'

    if me.username:
        username = f'[WHITE]@{me.username}[WHITE]'
    else:
        username = '[RED]<Not presented>[RED]'

    user_id = f'[WHITE]id{me.id}[WHITE]'

    echo(
        '''\n ====== Current Account ====== \n\n'''

        f'''| Full name: {full_name}\n'''
        f'''| Username: {username}\n'''
        f'''| Phone: {phone}\n'''
        f'''| ID: {user_id}\n'''
        f'''| Premium: {premium}\n'''

        '''\n ============================= \n'''
    )

# ========================================================= #

# = Local & Remote Box management commands ================ #

@cli.command()
@click.option(
    '--box-name', '-b', required=True,
    prompt=True, help='Name of your Box'
)
@click.option(
    '--box-salt', help='BoxSalt as hexadecimal'
)
@click.option(
    '--phrase', '-p',
    help='Passphrase to your Box. Keep it secret'
)
@click.option(
    '--scrypt-salt', 's',
    default=hex(tgbox.defaults.Scrypt.SALT)[2:],
    help='Scrypt salt as hexadecimal'
)
@click.option(
    '--scrypt-n', '-N', 'n', help='Scrypt N',
    default=int(tgbox.defaults.Scrypt.N)
)
@click.option(
    '--scrypt-p', '-P', 'p', help='Scrypt P',
    default=int(tgbox.defaults.Scrypt.P)
)
@click.option(
    '--scrypt-r', '-R', 'r', help='Scrypt R',
    default=int(tgbox.defaults.Scrypt.R)
)
@click.option(
    '--scrypt-dklen', '-L', 'l', help='Scrypt key length',
    default=int(tgbox.defaults.Scrypt.DKLEN)
)
def box_make(box_name, box_salt, phrase, s, n, p, r, l):
    """Create new TGBOX, the Remote and Local"""

    tc = get_account()

    state_key = get_sk()
    state = get_state(state_key)

    if not phrase and click.confirm('Generate passphrase for you?'):
        phrase = tgbox.keys.Phrase.generate(6).phrase.decode()
        echo(f'\nYour Phrase is [MAGENTA]{phrase}[MAGENTA]')

        echo(
            '''Please, write it down [WHITE]on paper[WHITE] '''
            '''and press [RED]Enter[RED]'''
            ''', we will [RED]clear[RED] shell for you'''
        )
        input(); clear_console()

    elif not phrase:
        phrase, phrase_repeat = 0, 1
        while phrase != phrase_repeat:
            if phrase != 0: # Init value
                echo('[RED]Phrase mismatch! Try again[RED]\n')

            phrase = click.prompt('Phrase', hide_input=True)
            phrase_repeat = click.prompt('Repeat phrase', hide_input=True)

    echo('[CYAN]Making BaseKey...[CYAN] ', nl=False)

    box_salt = bytes.fromhex(box_salt) if box_salt else None

    basekey = tgbox.keys.make_basekey(
        phrase.encode(),
        salt=bytes.fromhex(s),
        n=n, p=p, r=r, dklen=l
    )
    echo('[GREEN]Successful![GREEN]')

    echo('[CYAN]Making RemoteBox...[CYAN] ', nl=False)
    erb = tgbox.sync(tgbox.api.make_remotebox(
        tc, box_name, box_salt=box_salt)
    )
    echo('[GREEN]Successful![GREEN]')

    echo('[CYAN]Making LocalBox...[CYAN] ', nl=False)
    dlb = tgbox.sync(tgbox.api.make_localbox(erb, basekey))
    echo('[GREEN]Successful![GREEN]')

    echo('[CYAN]Updating local data...[CYAN] ', nl=False)

    if 'TGBOXES' not in state:
        state['TGBOXES'] = [[box_name, basekey.key]]
        state['CURRENT_TGBOX'] = 0
    else:
        state['TGBOXES'].append([box_name, basekey.key])
        state['CURRENT_TGBOX'] = len(state['TGBOXES']) - 1

    write_state(state, state_key)
    echo('[GREEN]Successful![GREEN]')

    raise ExitProgram

@cli.command()
@click.option(
    '--box-path', '-b',

    required = True,
    prompt = True,

    type = click.Path(
        exists = True,
        dir_okay = False,
        readable = True,
        path_type = Path
    ),
    help = 'Path to the LocalBox DB file',
)
@click.option(
    '--phrase', '-p', required=True,
    prompt=True, hide_input=True,
    help='Passphrase of encrypted Box.'
)
@click.option(
    '--salt', '-s', 's',
    default=hex(tgbox.defaults.Scrypt.SALT)[2:],
    help='Scrypt salt as hexadecimal number'
)
@click.option(
    '--scrypt-n', '-N', 'n', help='Scrypt N',
    default=int(tgbox.defaults.Scrypt.N)
)
@click.option(
    '--scrypt-p', '-P', 'p', help='Scrypt P',
    default=int(tgbox.defaults.Scrypt.P)
)
@click.option(
    '--scrypt-r', '-R', 'r', help='Scrypt R',
    default=int(tgbox.defaults.Scrypt.R)
)
@click.option(
    '--scrypt-dklen', '-L', 'l', help='Scrypt key length',
    default=int(tgbox.defaults.Scrypt.DKLEN)
)
def box_open(box_path, phrase, s, n, p, r, l):
    """Decrypt & connect existing LocalTgbox"""
    check_sk()

    state_key = get_sk()
    state = get_state(state_key)

    echo('[CYAN]Making BaseKey...[CYAN] ', nl=False)

    basekey = tgbox.keys.make_basekey(
        phrase.encode(),
        salt=bytes.fromhex(s),
        n=n, p=p, r=r, dklen=l
    )
    echo('[GREEN]Successful![GREEN]')

    box_path = box_path.resolve()

    echo('[CYAN]Opening LocalBox...[CYAN] ', nl=False)
    try:
        dlb = tgbox.sync(tgbox.api.get_localbox(basekey, box_path))
    except tgbox.errors.IncorrectKey:
        echo('[RED]Incorrect passphrase![RED]')
        raise ExitProgram

    echo('[GREEN]Successful![GREEN]')

    echo('[CYAN]Updating local data...[CYAN] ', nl=False)

    if 'TGBOXES' not in state:
        state['TGBOXES'] = [[box_path, basekey.key]]
        state['CURRENT_TGBOX'] = 0
    else:
        for _, other_basekey in state['TGBOXES']:
            if basekey.key == other_basekey:
                echo('[RED]This Box is already opened[RED]')
                raise ExitProgram

        state['TGBOXES'].append([box_path, basekey.key])
        state['CURRENT_TGBOX'] = len(state['TGBOXES']) - 1

    write_state(state, state_key)
    echo('[GREEN]Successful![GREEN]')
    raise ExitProgram

@cli.command()
@click.option(
    '--number', '-n', required=True, type=int,
    help='Number of other connected box, use box-list command'
)
def box_close(number):
    """Will disconnect selected LocalBox"""
    check_sk()

    state_key = get_sk()
    state = get_state(state_key)

    if 'TGBOXES' not in state or not state['TGBOXES']:
        echo('[RED]You don\'t have any connected Box.[RED]')
    elif number < 1 or number > len(state['TGBOXES']):
        echo('[RED]Invalid number, see box-list[RED]')
    else:
        state['TGBOXES'].pop(number-1)
        if not state['TGBOXES']:
            state.pop('TGBOXES')
            state.pop('CURRENT_TGBOX')
            echo('[GREEN]Disconnected. No more Boxes.[GREEN]')
        else:
            state['CURRENT_TGBOX'] = 0
            echo('[GREEN]Disconnected & switched to the Box #1[GREEN]')

        write_state(state, state_key)
        raise ExitProgram

@cli.command()
@click.option(
    '--number', '-n', required=True, type=int,
    help='Number of other connected box, use box-list command'
)
def box_switch(number):
    """This will set your CURRENT_TGBOX to selected"""
    check_sk()

    state_key = get_sk()
    state = get_state(state_key)
    number -= 1

    if 'TGBOXES' not in state:
        echo(
            '''[RED]You didn\'t connected box yet. Use[RED] '''
            '''[WHITE]box-open[WHITE] [RED]command.[RED]'''
        )
    elif number < 0 or number > len(state['TGBOXES'])-1:
        echo(
            f'''[RED]There is no box #{number+1}. Use[RED] '''
             '''[WHITE]box-list[WHITE] [RED]command.[RED]'''
        )
    elif number == state['CURRENT_TGBOX']:
        echo(
            '''[YELLOW]You already use this box. See other with[YELLOW] '''
            '''[WHITE]box-list[WHITE] [YELLOW]command.[YELLOW]'''
        )
    else:
        state['CURRENT_TGBOX'] = number
        write_state(state, state_key)
        echo(f'[GREEN]You switched to box #{number+1}[GREEN]')

    raise ExitProgram

@cli.command()
def box_list():
    """List all connected boxes"""
    check_sk()

    state_key = get_sk()
    state = get_state(state_key)

    if 'CURRENT_TGBOX' in state:
        echo(
            '''\n[WHITE]You\'re using Box[WHITE] '''
           f'''[RED]#{str(state['CURRENT_TGBOX']+1)}[RED]\n'''
        )
    else:
        echo('[YELLOW]You don\'t have any connected Box.[YELLOW]')
        raise ExitProgram

    lost_boxes, count = [], 0

    for box_path, basekey in state['TGBOXES']:
        try:
            dlb = tgbox.sync(tgbox.api.get_localbox(
                tgbox.keys.BaseKey(basekey), box_path)
            )
            name = Path(box_path).name
            salt = urlsafe_b64encode(dlb.box_salt).decode()

            echo(
                f'''[WHITE]{count+1})[WHITE] [BLUE]{name}[BLUE]'''
                f'''@[BRIGHT_BLACK]{salt}[BRIGHT_BLACK]'''
            )
            tgbox.sync(dlb.done())
        except FileNotFoundError:
            echo(f'[WHITE]{count+1})[WHITE] [RED]Moved, so removed.[RED]')
            lost_boxes.append([box_path, basekey])

        count += 1

    for lbox in lost_boxes:
        state['TGBOXES'].remove(lbox)

    if lost_boxes:
        if not state['TGBOXES']:
            state.pop('TGBOXES')
            state.pop('CURRENT_TGBOX')
            echo('No more Boxes, use [WHITE]box-open[WHITE].')
        else:
            state['CURRENT_TGBOX'] = 0
            echo(
                '''Switched to the first Box. Set other '''
                '''with [WHITE]box-switch[WHITE].'''
            )
    write_state(state, state_key)
    raise ExitProgram

@cli.command()
@click.option(
    '--prefix', '-p', default=tgbox.defaults.REMOTEBOX_PREFIX,
    help='Telegram channels with this prefix will be searched'
)
def box_list_remote(prefix):
    """List all RemoteBoxes on account"""

    tc, count = get_account(), 0

    echo('[YELLOW]Searching...[YELLOW]')

    for dialogue in sync_async_gen(tc.iter_dialogs()):
        if prefix in dialogue.title and dialogue.is_channel:
            erb = tgbox.api.EncryptedRemoteBox(dialogue, tc)

            erb_name = tgbox.sync(erb.get_box_name())
            erb_salt = tgbox.sync(erb.get_box_salt())
            erb_salt = urlsafe_b64encode(erb_salt).decode()

            echo(
                f'''[WHITE]{count+1}[WHITE]) [BLUE]{erb_name}[BLUE]'''
                f'''@[BRIGHT_BLACK]{erb_salt}[BRIGHT_BLACK]'''
            )
            count += 1

    echo('[YELLOW]Done.[YELLOW]')
    raise ExitProgram

@cli.command()
@click.option(
    '--start-from-id','-s', default=0,
    help='Will check files that > specified ID'
)
@click.option(
    '--deep','-d', default=False, is_flag=True,
    help='Use a deep Box syncing instead of fast'
)
def box_sync(start_from_id, deep):
    """Will synchronize your current LocalBox with RemoteBox

    After this operation, all info about your LocalFiles that are
    not in RemoteBox will be deleted from LocalBox. Files that
    not in LocalBox but in RemoteBox will be imported.

    There is two modes of sync: the Fast and the Deep. The
    "Fast" mode will fetch data from the "Recent Actions"
    Telegram channel admin log. The updates here will stay
    up to 48 hours, so this is the best option. In any other
    case specify a --deep flag to enable the "Deep" sync.

    Deep sync will iterate over each file in Remote and
    Local boxes, then compare them. This may take a
    very long time. You can track state of remote
    with the file-last-id command and specify
    the last file ID of your LocalBox as
    --start-from-id (-s) option here.

    \b
    (!) Please note that to make a fast sync you *need*\b
     |  to have access to the Channel's Admin Log. Ask
     |  the RemoteBox owner to make you Admin with (at
     |  least) zero rights or use a deep synchronization.
     |
    (?) Use tgbox-cli box-info to check your rights.

    (!) --start-from-id will be used only on deep sync.
    """
    dlb, drb = get_box()

    if not deep:
        progress_callback = lambda i,a: echo(f'* [WHITE]ID{i}[WHITE]: [CYAN]{a}[CYAN]')
    else:
        progress_callback = Progress(enlighten_manager,
            'Synchronizing...').update_2

    box_sync_coro = dlb.sync(
        drb = drb,
        deep = deep,
        start_from = start_from_id,
        fast_progress_callback = progress_callback,
        deep_progress_callback = progress_callback
    )
    try:
        tgbox.sync(box_sync_coro)
    except tgbox.errors.RemoteFileNotFound as e:
        echo(f'[RED]{e}[RED]')
    else:
        if deep:
            enlighten_manager.stop()

        echo('[GREEN]Syncing complete.[GREEN]')

    raise ExitProgram

@cli.command()
@click.option(
    '--number','-n', required=True, type=int,
    help='Number of connected account. We will take session from it.'
)
def box_replace_account(number):
    """Will replace Telegram account of your current Box

    This can be useful if you disconnected your TGBOX in
    Telegram settings (Privacy & Security > Devices) or
    your local TGBOX was too long offline.
    """
    state_key = get_sk()
    state = get_state(state_key)

    dlb, _ = get_box(ignore_remote=True)

    if number < 1 or number > len(state['ACCOUNTS']):
        echo(
            '''[RED]Invalid account number! See[RED] '''
            '''[WHITE]account-list[WHITE] [RED]command.[RED]'''
        )
        raise ExitProgram

    session = state['ACCOUNTS'][number-1]

    tc = tgbox.api.TelegramClient(
        session=session,
        api_id=API_ID,
        api_hash=API_HASH
    )
    tgbox.sync(tc.connect())

    basekey = tgbox.keys.BaseKey(
        state['TGBOXES'][state['CURRENT_TGBOX']][1]
    )
    tgbox.sync(dlb.replace_session(basekey, tc))
    echo('[GREEN]Session replaced successfully[GREEN]')

    raise ExitProgram

@cli.command()
@click.option(
    '--number', '-n', required=True, type=int,
    help='Number of RemoteBox, use box-list-remote command'
)
@click.option(
    '--phrase', '-p', required=True, hide_input=True,
    help='To request Box you need to specify phrase to it',
    prompt='Phrase to your future cloned Box'
)
@click.option(
    '--salt', '-s', 's',
    default=hex(tgbox.defaults.Scrypt.SALT)[2:],
    help='Scrypt salt as hexadecimal number'
)
@click.option(
    '--scrypt-n', '-N', 'n', help='Scrypt N',
    default=int(tgbox.defaults.Scrypt.N)
)
@click.option(
    '--scrypt-p', '-P', 'p', help='Scrypt P',
    default=int(tgbox.defaults.Scrypt.P)
)
@click.option(
    '--scrypt-r', '-R', 'r', help='Scrypt R',
    default=int(tgbox.defaults.Scrypt.R)
)
@click.option(
    '--scrypt-dklen', '-L', 'l', help='Scrypt key length',
    default=int(tgbox.defaults.Scrypt.DKLEN)
)
@click.option(
    '--prefix', default=tgbox.defaults.REMOTEBOX_PREFIX,
    help='Telegram channels with this prefix will be searched'
)
def box_request(number, phrase, s, n, p, r, l, prefix):
    """Command to receive RequestKey for other Box"""
    erb = select_remotebox(number, prefix)

    basekey = tgbox.keys.make_basekey(
        phrase.encode(),
        salt=bytes.fromhex(s),
        n=n, p=p, r=r, dklen=l
    )
    reqkey = tgbox.sync(erb.get_requestkey(basekey))
    echo(
        '''\nSend this Key to the Box owner:\n'''
       f'''    [WHITE]{reqkey.encode()}[WHITE]\n'''
    )
    raise ExitProgram

@cli.command()
@click.option(
    '--requestkey', '-r',
    help='Requester\'s RequestKey, by box-request command'
)
def box_share(requestkey):
    """Command to make ShareKey & to share Box"""
    dlb, _ = get_box(ignore_remote=True)

    requestkey = requestkey if not requestkey\
        else tgbox.keys.Key.decode(requestkey)

    sharekey = dlb.get_sharekey(requestkey)

    if not requestkey:
        echo(
            '''\n[RED]You didn\'t specified requestkey.\n   You '''
            '''will receive decryption key IN PLAIN\n[RED]'''
        )
        if not click.confirm('Are you TOTALLY sure?'):
            raise ExitProgram

    echo(
        '''\nSend this Key to the Box requester:\n'''
       f'''    [WHITE]{sharekey.encode()}[WHITE]\n'''
    )
    raise ExitProgram

@cli.command()
@click.option(
    '--box-path', '-b', help='Path to which we will clone',
    type=click.Path(writable=True, readable=True, path_type=Path)
)
@click.option(
    '--box-filename', '-f',
    help='Filename of cloned DecryptedLocalBox',
)
@click.option(
    '--box-number', '-n', required=True, type=int,
    prompt=True, help='Number of Box you want to clone',
)
@click.option(
    '--prefix', default=tgbox.defaults.REMOTEBOX_PREFIX,
    help='Telegram channels with this prefix will be searched'
)
@click.option(
    '--key', '-k', help='ShareKey/ImportKey received from Box owner.'
)
@click.option(
    '--phrase', '-p', prompt='Phrase to your cloned Box',
    help='To clone Box you need to specify phrase to it',
    hide_input=True, required=True
)
@click.option(
    '--salt', '-s', 's',
    default=hex(tgbox.defaults.Scrypt.SALT)[2:],
    help='Scrypt salt as hexadecimal number'
)
@click.option(
    '--scrypt-n', '-N', 'n', help='Scrypt N',
    default=int(tgbox.defaults.Scrypt.N)
)
@click.option(
    '--scrypt-p', '-P', 'p', help='Scrypt P',
    default=int(tgbox.defaults.Scrypt.P)
)
@click.option(
    '--scrypt-r', '-R', 'r', help='Scrypt R',
    default=int(tgbox.defaults.Scrypt.R)
)
@click.option(
    '--scrypt-dklen', '-L', 'l', help='Scrypt key length',
    default=int(tgbox.defaults.Scrypt.DKLEN)
)
def box_clone(
        box_path, box_filename,
        box_number, prefix, key,
        phrase, s, n, p, r, l):
    """
    Will clone RemoteBox to LocalBox by your passphrase
    """
    state_key = get_sk()
    state = get_state(state_key)
    erb = select_remotebox(box_number, prefix)

    try:
        key = tgbox.keys.Key.decode(key)
    except tgbox.errors.IncorrectKey:
        pass

    echo('\n[CYAN]Making BaseKey...[CYAN] ', nl=False)

    basekey = tgbox.keys.make_basekey(
        phrase.encode(),
        salt=bytes.fromhex(s),
        n=n, p=p, r=r, dklen=l
    )
    echo('[GREEN]Successful![GREEN]')

    if key is None:
        key = basekey
    else:
        key = tgbox.keys.make_importkey(
            key=basekey, sharekey=key,
            box_salt=tgbox.sync(erb.get_box_salt())
        )
    drb = tgbox.sync(erb.decrypt(key=key))

    if box_path is None:
        if box_filename:
            box_path = box_filename
        else:
            box_path = tgbox.sync(drb.get_box_name())
    else:
        box_path += tgbox.sync(drb.get_box_name())\
            if not box_filename else box_filename

    dlb = tgbox.sync(tgbox.api.local.clone_remotebox(
        drb = drb,
        basekey = basekey,
        box_path = box_path,

        progress_callback = Progress(
            enlighten_manager, 'Cloning...').update_2
        )
    )
    enlighten_manager.stop()

    echo('\n[CYAN]Updating local data...[CYAN] ', nl=False)

    if 'TGBOXES' not in state:
        state['TGBOXES'] = [[box_path, basekey.key]]
        state['CURRENT_TGBOX'] = 0
    else:
        for _, other_basekey in state['TGBOXES']:
            if basekey.key == other_basekey:
                echo('[RED]This Box is already opened[RED]')
                raise ExitProgram

        state['TGBOXES'].append([box_path, basekey.key])
        state['CURRENT_TGBOX'] = len(state['TGBOXES']) - 1

    write_state(state, state_key)
    echo('[GREEN]Successful![GREEN]')
    raise ExitProgram

@cli.command()
@click.argument('defaults',nargs=-1)
def box_default(defaults):
    """Change the TGBOX default values to your own

    \b
    I.e:\b
        # Change METADATA_MAX to the max allowed size
        tgbox-cli box-default METADATA_MAX=1677721
        \b
        # Change download path from DownloadsTGBOX to Downloads
        tgbox-cli box-default DOWNLOAD_PATH=Downloads
    """
    dlb, _ = get_box(ignore_remote=True)

    for default in defaults:
        try:
            key, value = default.split('=',1)
            tgbox.sync(dlb.defaults.change(key, value))
            echo(f'[GREEN]Successfuly changed {key} to {value}[GREEN]')
        except AttributeError:
            echo(f'[RED]Default {key} doesn\'t exist, skipping[RED]')

    raise ExitProgram

@cli.command()
def box_info():
    """Show information about current Box"""

    dlb, drb = get_box()

    box_name = tgbox.sync(drb.get_box_name())
    box_name = f'[WHITE]{box_name}[WHITE]'

    box_id = f'[WHITE]id{drb.box_channel_id}[WHITE]'

    lfid_local = tgbox.sync(dlb.get_last_file_id())
    lfid_remote = tgbox.sync(drb.get_last_file_id())

    if lfid_local != lfid_remote:
        status = f'[RED]Out of sync! ({lfid_local}L/{lfid_remote}R)[RED]'
    else:
        status = '[GREEN]Seems synchronized[GREEN]'

    lfid_local = f'[WHITE]{lfid_local}[WHITE]'
    lfid_remote = f'[WHITE]{lfid_remote}[WHITE]'

    if drb.box_channel.username:
        public_link = f'[WHITE]@{drb.box_channel.username}[WHITE]'
    else:
        public_link = '[RED]<Not presented>[RED]'

    if drb.box_channel.restricted:
        restricted = f'[RED]yes: {drb.box_channel.restriction_reason}[RED]'
    else:
        restricted = '[WHITE]no[WHITE]'

    box_path = f'[WHITE]{dlb.tgbox_db.db_path.name}[WHITE]'

    local_box_date = datetime.fromtimestamp(dlb.box_cr_time).strftime('%d/%m/%Y')
    local_date_created = f'[WHITE]{local_box_date}[WHITE]'

    remote_box_date = tgbox.sync(drb.tc.get_messages(drb.box_channel, ids=1))
    remote_box_date = remote_box_date.date.strftime('%d/%m/%Y')
    remote_date_created = f'[WHITE]{remote_box_date}[WHITE]'

    rights_interested = {
        'post_messages' : 'Upload files',
        'delete_messages' : 'Remove files',
        'edit_messages' : 'Edit files',
        'invite_users' : 'Invite users',
        'add_admins': 'Add admins'
    }
    if drb.box_channel.admin_rights:
        rights = ' (+) [GREEN]Fast sync files[GREEN]\n'
    else:
        rights = ' (-) [RED]Fast sync files[RED]\n'

    rights += ' (+) [GREEN]Download files[GREEN]\n'

    for k,v in rights_interested.items():
        if drb.box_channel.admin_rights and\
            getattr(drb.box_channel.admin_rights, k):
                right_status = '(+)' # User has such right
                right = f'[GREEN]{v}[GREEN]'
        else:
            right_status = '(-)' # User hasn't such right
            right = f'[RED]{v}[RED]'

        rights += f' {right_status} {right}\n'

    echo(
        '''\n ====== Current Box (remote) ======\n\n'''

        f'''| Box name: {box_name}\n'''
        f'''| Public link: {public_link}\n'''
        f'''| ID: {box_id}\no\n'''
        f'''| Date created: {remote_date_created}\n'''
        f'''| Last file ID: {lfid_remote}\n'''
        f'''| Is restricted: {restricted}\no\n'''
        f'''| Your rights: \n{rights}\n'''

        ''' ====== Current Box (local) =======\n\n'''

        f'''| Box DB: {box_path}\n'''
        f'''| Date created: {local_date_created}\n'''
        f'''| Last file ID: {lfid_local}\n'''

        '''\n :::::::::::::::::::::::::::::::::\n\n'''

        f'''| Status: {status}\n'''

        '''\n =================================\n'''
    )
    raise ExitProgram

# ========================================================= #

# = Local & Remote Boxfile management commands ============ #

@cli.command()
@click.option(
    '--path', '-p', required=True, prompt=True,
    help='Will upload specified path. If directory, upload all files in it',
    type=click.Path(readable=True, dir_okay=True, path_type=Path)
)
@click.option(
    '--file-path', '-f', type=Path,
    help='File path. Will be system\'s if not specified'
)
@click.option(
    '--cattrs', '-c', help='File\'s CustomAttributes. Format: "key:value key:value"'
)
@click.option(
    '--thumb/--no-thumb', default=True,
    help='Add thumbnail or not, boolean'
)
@click.option(
    '--max-workers', default=10, type=click.IntRange(1,50),
    help='Max amount of files uploaded at the same time, default=10',
)
@click.option(
    '--max-bytes', default=500000000,
    type=click.IntRange(1000000, 1000000000),
    help='Max amount of bytes uploaded at the same time, default=500000000',
)
def file_upload(path, file_path, cattrs, thumb, max_workers, max_bytes):
    """Will upload specified path to the Box"""
    dlb, drb = get_box()

    current_workers = max_workers
    current_bytes = max_bytes

    def _upload(to_upload: list):
        try:
            tgbox.sync(gather(*to_upload))
            to_upload.clear()
        except tgbox.errors.NotEnoughRights as e:
            echo(f'\n[RED]{e}[RED]')
            enlighten_manager.stop()
            raise ExitProgram

    if path.is_dir():
        iter_over = path.rglob('*')
    else:
        iter_over = (path,)

    to_upload = []
    for current_path in iter_over:

        if current_path.is_dir():
            continue

        if not file_path:
            remote_path = current_path.absolute()
        else:
            remote_path = Path(file_path) / current_path.name

        if cattrs:
            try:
                parsed_cattrs = [
                    i.strip().split(':')
                    for i in cattrs.split() if i
                ]
                parsed_cattrs = {
                    k.strip():v.strip().encode()
                    for k,v in parsed_cattrs
                }
            except ValueError as e:
                raise ValueError('Invalid cattrs!', e) from None
        else:
            parsed_cattrs = None
        try:
            pf = tgbox.sync(dlb.prepare_file(
                file = open(current_path,'rb'),
                file_path = remote_path,
                cattrs = parsed_cattrs,
                make_preview = thumb
            ))
        except tgbox.errors.InvalidFile:
            echo(f'[YELLOW]{current_path} is empty. Skipping.[YELLOW]')
            continue
        except tgbox.errors.FingerprintExists:
            echo(f'[YELLOW]{current_path} already uploaded. Skipping.[YELLOW]')
            continue

        current_bytes -= pf.filesize
        current_workers -= 1

        if not all((current_workers > 0, current_bytes > 0)):
            _upload(to_upload)

            current_workers = max_workers - 1
            current_bytes = max_bytes - pf.filesize

        to_upload.append(drb.push_file(pf, Progress(
            enlighten_manager, current_path.name).update))

    if to_upload: # If any files left
        _upload(to_upload)

    raise ExitProgram

@cli.command()
@click.argument('filters',nargs=-1)
@click.option(
    '--force-remote','-r', is_flag=True,
    help='If specified, will fetch files from RemoteBox'
)
@click.option(
    '--non-interactive', is_flag=True,
    help='If specified, will echo to shell instead of pager'
)
def file_search(filters, force_remote, non_interactive):
    """Will list files by filters

    \b
    Available filters:\b
        scope: Define a path as search scope
               -----------------------------
               The *scope* is an absolute directory in which
               we will search your file by other filters. By
               default, the tgbox.api.utils.search_generator
               will search over the entire LocalBox. This can
               be slow if you're have too many files.
               \b
               Example: let's imagine that You're a Linux user which
               share it's Box with the Windows user. In this case,
               Your LocalBox will contain a path parts on the
               '/' (Linux) and 'C:\\' (Windows) roots. If You
               know that some file was uploaded by Your friend,
               then You can specify a scope='C:\\' to ignore
               all files uploaded from the Linux machine. This
               will significantly fasten the search process,
               because almost all filters require to select
               row from the LocalBox DB, decrypt Metadata and
               compare its values with ones from SearchFilter.
               \b
               !: The scope will be ignored on RemoteBox search.
               !: The min_id & max_id will be ignored if scope used.
        \b
        id integer: File’s ID
        mime str: File mime type
        \b
        cattrs: File CAttrs
                -----------
                Can be used hexed PackedAttributes
                or special CLI format alternatively:
                cattrs="comment:test type:message"
        \b
        file_path str: File path
        file_name str: File name
        file_salt str: File salt
        \b
        min_id integer: File ID should be > min_id
        max_id integer: File ID should be < max_id
        \b
        min_size integer: File Size should be > min_size
        max_size integer: File Size should be < max_size
        \b
        min_time integer/float: Upload Time should be > min_time
        max_time integer/float: Upload Time should be < max_time
        \b
        imported bool: Yield only imported files
        re       bool: re_search for every bytes filter
    \b
    See tgbox.readthedocs.io/en/indev/
        tgbox.html#tgbox.tools.SearchFilter
    \b
    You can also use special flags to specify
    that filters is for include or exclude search.
    \b
    Example:\b
        # Include is used by default
        tgbox-cli file-search min_id=3 max_id=100
        \b
        # Include flag (will ignore unmatched)
        tgbox-cli file-search +i file_name=.png
        \b
        # Exclude flag (will ignore matched)
        tgbox-cli file-search +e file_name=.png
        \b
        You can use both, the ++include and
        ++exclude (+i, +e) in one command.
    """
    if force_remote:
        dlb, drb = get_box()
    else:
        dlb, drb = get_box(ignore_remote=True)

    def bfi_gen(search_file_gen):
        for bfi in sync_async_gen(search_file_gen):
            yield format_dxbf(bfi)
    try:
        sf = filters_to_searchfilter(filters)
    except IndexError: # Incorrect filters format
        echo('[RED]Incorrect filters! Make sure to use format filter=value[RED]')
        raise ExitProgram
    except KeyError as e: # Unknown filters
        echo(f'[RED]Filter "{e.args[0]}" doesn\'t exists[RED]')
        raise ExitProgram

    box = drb if force_remote else dlb

    if non_interactive:
        for dxbfs in bfi_gen(box.search_file(sf, cache_preview=False)):
            echo(dxbfs, nl=False)
        echo('')
    else:
        sf_gen = bfi_gen(box.search_file(sf, cache_preview=False))

        colored = True if system().lower() == 'windows' else None
        colored = False if TGBOX_CLI_NOCOLOR else colored
        click.echo_via_pager(sf_gen, color=colored)

    raise ExitProgram

@cli.command()
@click.argument('filters', nargs=-1)
@click.option(
    '--preview', '-p', is_flag=True,
    help='If specified, will download ONLY thumbnails'
)
@click.option(
    '--show', '-s', is_flag=True,
    help='If specified, will open file on downloading'
)
@click.option(
    '--locate', '-l', is_flag=True,
    help='If specified, will open file path in file manager'
)
@click.option(
    '--hide-name', is_flag=True,
    help='If specified, will hide file name'
)
@click.option(
    '--hide-folder', is_flag=True,
    help='If specified, will hide folder'
)
@click.option(
    '--out','-o',
    help='Download path. ./BoxDownloads by default',
    type=click.Path(writable=True, path_type=Path)
)
@click.option(
    '--force-remote','-r', is_flag=True,
    help='If specified, will fetch file data from RemoteBox'
)
@click.option(
    '--redownload', is_flag=True,
    help='If specified, will redownload already cached files'
)
@click.option(
    '--max-workers', default=10, type=click.IntRange(1,50),
    help='Max amount of files downloaded at the same time, default=10',
)
@click.option(
    '--max-bytes', default=500000000,
    type=click.IntRange(1000000, 1000000000),
    help='Max amount of bytes downloaded at the same time, default=500000000',
)
def file_download(
        filters, preview, show, locate,
        hide_name, hide_folder, out,
        force_remote, redownload,
        max_workers, max_bytes):
    """Will download files by filters

    \b
    Available filters:\b
        scope: Define a path as search scope
               -----------------------------
               The *scope* is an absolute directory in which
               we will search your file by other filters. By
               default, the tgbox.api.utils.search_generator
               will search over the entire LocalBox. This can
               be slow if you're have too many files.
               \b
               Example: let's imagine that You're a Linux user which
               share it's Box with the Windows user. In this case,
               Your LocalBox will contain a path parts on the
               '/' (Linux) and 'C:\\' (Windows) roots. If You
               know that some file was uploaded by Your friend,
               then You can specify a scope='C:\\' to ignore
               all files uploaded from the Linux machine. This
               will significantly fasten the search process,
               because almost all filters require to select
               row from the LocalBox DB, decrypt Metadata and
               compare its values with ones from SearchFilter.
               \b
               !: The scope will be ignored on RemoteBox search.
               !: The min_id & max_id will be ignored if scope used.
        \b
        id integer: File’s ID
        mime str: File mime type
        \b
        cattrs: File CAttrs
                -----------
                Can be used hexed PackedAttributes
                or special CLI format alternatively:
                cattrs="comment:test type:message"
        \b
        file_path str: File path
        file_name str: File name
        file_salt str: File salt
        \b
        min_id integer: File ID should be > min_id
        max_id integer: File ID should be < max_id
        \b
        min_size integer: File Size should be > min_size
        max_size integer: File Size should be < max_size
        \b
        min_time integer/float: Upload Time should be > min_time
        max_time integer/float: Upload Time should be < max_time
        \b
        imported bool: Yield only imported files
        re       bool: re_search for every bytes filter
    \b
    See tgbox.readthedocs.io/en/indev/
        tgbox.html#tgbox.tools.SearchFilter
    \b
    You can also use special flags to specify
    that filters is for include or exclude search.
    \b
    Example:\b
        # Include is used by default
        tgbox-cli file-download min_id=3 max_id=100
        \b
        # Include flag (will ignore unmatched)
        tgbox-cli file-download +i file_name=.png
        \b
        # Exclude flag (will ignore matched)
        tgbox-cli file-download +e file_name=.png
        \b
        You can use both, the ++include and
        ++exclude (+i, +e) in one command.
    """
    if preview and not force_remote:
        dlb, drb = get_box(ignore_remote=True)
    else:
        dlb, drb = get_box()
    try:
        sf = filters_to_searchfilter(filters)
    except IndexError: # Incorrect filters format
        echo('[RED]Incorrect filters! Make sure to use format filter=value[RED]')
        raise ExitProgram
    except KeyError as e: # Unknown filters
        echo(f'[RED]Filter "{e.args[0]}" doesn\'t exists[RED]')
        raise ExitProgram

    current_workers = max_workers
    current_bytes = max_bytes

    to_download = dlb.search_file(sf)
    while True:
        try:
            to_gather_files = []
            while all((current_workers > 0, current_bytes > 0)):
                dlbfi = tgbox.sync(tgbox.tools.anext(to_download))

                preview_bytes = None

                if hide_name:
                    file_name = tgbox.tools.prbg(16).hex()
                    file_name += Path(dlbfi.file_name).suffix
                else:
                    file_name = dlbfi.file_name

                file_name = file_name.lstrip('/')
                file_name = file_name.lstrip('\\')

                file_name = file_name if not preview else file_name + '.jpg'

                if not out:
                    downloads = Path(dlbfi.defaults.DOWNLOAD_PATH)
                    downloads = downloads / ('Previews' if preview else 'Files')

                    if hide_folder:
                        file_path = dlbfi.defaults.DEF_UNK_FOLDER
                    else:
                        file_path = dlbfi.file_path

                    file_path = str(tgbox.tools.make_general_path(file_path))

                    if file_path.startswith('/'):
                        file_path = str(Path('@', file_path.lstrip('/')))

                    elif file_path.startswith('\\'):
                        file_path = str(Path('@', file_path.lstrip('\\')))

                    outpath = Path(downloads, file_path, file_name)
                else:
                    outpath = out / file_name

                if preview and not force_remote:
                    preview_bytes = dlbfi.preview

                elif preview and force_remote:
                    drbfi = tgbox.sync(drb.get_file(dlbfi.id))
                    preview_bytes = drbfi.preview

                if preview_bytes is not None:
                    if preview_bytes == b'':
                        if force_remote:
                            echo(f'[YELLOW]{file_name} doesn\'t have preview. Skipping.[YELLOW]')
                        else:
                            echo(
                                f'''[YELLOW]{file_name} doesn\'t have preview. Try '''
                                 '''-r flag. Skipping.[YELLOW]'''
                            )
                        continue

                    outpath.parent.mkdir(parents=True, exist_ok=True)

                    with open(outpath, 'wb') as f:
                        f.write(preview_bytes)

                    if show or locate:
                        click.launch(str(outpath), locate)

                    echo(
                        f'''[WHITE]{file_name}[WHITE] preview downloaded '''
                        f'''to [WHITE]{str(outpath.parent)}[WHITE]''')
                else:
                    drbfi = tgbox.sync(drb.get_file(dlbfi.id))

                    if not drbfi:
                        echo(
                            f'''[YELLOW]There is no file with ID={dlbfi.id} in '''
                             '''RemoteBox. Skipping.[YELLOW]''')
                    else:
                        if not redownload and outpath.exists() and\
                            outpath.stat().st_size == dlbfi.size:
                                echo(f'[GREEN]{str(outpath)} downloaded. Skipping...[GREEN]')
                                continue

                        current_workers -= 1
                        current_bytes -= drbfi.file_size

                        outpath.parent.mkdir(parents=True, exist_ok=True)
                        outpath = open(outpath, 'wb')

                        p_file_name = '<Filename hidden>' if hide_name\
                            else drbfi.file_name

                        download_coroutine = drbfi.download(
                            outfile = outpath,
                            progress_callback = Progress(
                                enlighten_manager, p_file_name).update,
                            hide_folder = hide_folder,
                            hide_name = hide_name
                        )
                        to_gather_files.append(download_coroutine)

                        if show or locate:
                            def _launch(path: str, locate: bool, size: int) -> None:
                                while (Path(path).stat().st_size+1) / size * 100 < 5:
                                    sleep(1)
                                click.launch(path, locate=locate)

                            loop = get_event_loop()

                            to_gather_files.append(loop.run_in_executor(
                                None, lambda: _launch(outpath.name, locate, dlbfi.size))
                            )
            if to_gather_files:
                tgbox.sync(gather(*to_gather_files))

            current_workers = max_workers
            current_bytes = max_bytes

        except StopAsyncIteration:
            break

    if to_gather_files: # If any files left
        tgbox.sync(gather(*to_gather_files))

    enlighten_manager.stop()
    raise ExitProgram

@cli.command()
@click.option(
    '--start-from-id','-s', default=0,
    help='Will start searching from this ID (lower than)'
)
def file_list_non_imported(start_from_id):
    """Will list files not imported to your
    DecryptedLocalBox from other RemoteBox

    Will also show a RequestKey. Send it to the
    file owner. He will use a file-share command
    and will send you a ShareKey. You can use
    it with file-import to decrypt and save
    forwarded RemoteBoxFile to your LocalBox.
    """
    dlb, drb = get_box()

    iter_over = drb.files(
        offset_id = start_from_id,
        return_imported_as_erbf = True
    )
    echo('[YELLOW]\nSearching, press CTRL+C to stop...[YELLOW]')

    for xrbf in sync_async_gen(iter_over):
        if type(xrbf) is tgbox.api.EncryptedRemoteBoxFile:
            time = datetime.fromtimestamp(xrbf.upload_time)
            time = f"[CYAN]{time.strftime('%d/%m/%y, %H:%M:%S')}[CYAN]"

            salt = urlsafe_b64encode(xrbf.file_salt).decode()
            idsalt = f'[[BRIGHT_RED]{str(xrbf.id)}[BRIGHT_RED]:'
            idsalt += f'[BRIGHT_BLACK]{salt[:12]}[BRIGHT_BLACK]]'

            size = f'[GREEN]{format_bytes(xrbf.file_size)}[GREEN]'
            name = '[RED][N/A: No FileKey available][RED]'

            req_key = xrbf.get_requestkey(dlb._mainkey).encode()
            req_key = f'[WHITE]{req_key}[WHITE]'

            formatted = (
               f"""\nFile: {idsalt} {name}\n"""
               f"""Size, Time: {size}({xrbf.file_size}), {time}\n"""
               f"""RequestKey: {req_key}"""
            )
            echo(formatted)
    echo('')
    raise ExitProgram

@cli.command()
@click.option(
    '--requestkey', '-r',
    help='Requester\'s RequestKey'
)
@click.option(
    '--id', required=True, type=int,
    help='ID of file to share'
)
def file_share(requestkey, id):
    """Use this command to get a ShareKey to your file"""

    dlb, _ = get_box(ignore_remote=True)
    dlbf = tgbox.sync(dlb.get_file(id=id))

    if not dlbf:
        echo(f'[RED]There is no file in LocalBox by ID {id}[RED]')
        raise ExitProgram

    requestkey = requestkey if not requestkey\
        else tgbox.keys.Key.decode(requestkey)

    sharekey = dlbf.get_sharekey(requestkey)

    if not requestkey:
        echo(
            '''\n[RED]You didn\'t specified requestkey.\n   You '''
            '''will receive decryption key IN PLAIN[RED]\n'''
        )
        if not click.confirm('Are you TOTALLY sure?'):
            raise ExitProgram
    echo(
        '''\nSend this Key to the Box requester:\n'''
       f'''    [WHITE]{sharekey.encode()}[WHITE]\n'''
    )
    raise ExitProgram

@cli.command()
@click.option(
    '--key', '-k', required=True,
    help='File\'s ShareKey/ImportKey/FileKey'
)
@click.option(
    '--id', required=True, type=int,
    help='ID of file to import'
)
@click.option(
    '--file-path', '-f', type=Path,
    help='Imported file\'s path.'
)
def file_import(key, id, file_path):
    """Will import RemoteBoxFile to your LocalBox"""
    dlb, drb = get_box()
    erbf = tgbox.sync(drb.get_file(
        id, return_imported_as_erbf=True))

    if not erbf:
        echo(f'[RED]There is no file in RemoteBox by ID {id}[RED]')
        raise ExitProgram
    try:
        key = tgbox.keys.Key.decode(key)
    except tgbox.errors.IncorrectKey:
        echo(f'[RED]Specified Key is invalid[RED]')
    else:
        if isinstance(key, tgbox.keys.ShareKey):
            key = tgbox.keys.make_importkey(
                key=dlb._mainkey, sharekey=key,
                box_salt=erbf.file_salt
            )
        drbf = tgbox.sync(erbf.decrypt(key))
        tgbox.sync(dlb.import_file(drbf, file_path))

        echo(format_dxbf(drbf))

    raise ExitProgram

@cli.command()
@click.option(
    '--remote','-r', is_flag=True,
    help='If specified, will return ID of last file on RemoteBox'
)
def file_last_id(remote):
    """Will return ID of last uploaded to Box file"""
    dlb, drb = get_box(ignore_remote=False if remote else True)
    lfid = tgbox.sync((drb if remote else dlb).get_last_file_id())

    sbox = 'Remote' if remote else 'Local'
    echo(f'ID of last uploaded to {sbox}Box file is [GREEN]{lfid}[GREEN]')
    raise ExitProgram


@cli.command()
@click.argument('filters', nargs=-1)
@click.option(
    '--local-only','-l', is_flag=True,
    help='If specified, will remove file ONLY from LocalBox'
)
@click.option(
    '--ask-before-remove','-a', is_flag=True,
    help='If specified, will ask "Are you sure?" for each file'
)
def file_remove(filters, local_only, ask_before_remove):
    """Will remove files by filters

    \b
    Available filters:\b
        scope: Define a path as search scope
               -----------------------------
               The *scope* is an absolute directory in which
               we will search your file by other filters. By
               default, the tgbox.api.utils.search_generator
               will search over the entire LocalBox. This can
               be slow if you're have too many files.
               \b
               Example: let's imagine that You're a Linux user which
               share it's Box with the Windows user. In this case,
               Your LocalBox will contain a path parts on the
               '/' (Linux) and 'C:\\' (Windows) roots. If You
               know that some file was uploaded by Your friend,
               then You can specify a scope='C:\\' to ignore
               all files uploaded from the Linux machine. This
               will significantly fasten the search process,
               because almost all filters require to select
               row from the LocalBox DB, decrypt Metadata and
               compare its values with ones from SearchFilter.
               \b
               !: The scope will be ignored on RemoteBox search.
               !: The min_id & max_id will be ignored if scope used.
        \b
        id integer: File’s ID
        mime str: File mime type
        \b
        cattrs: File CAttrs
                -----------
                Can be used hexed PackedAttributes
                or special CLI format alternatively:
                cattrs="comment:test type:message"
        \b
        file_path str: File path
        file_name str: File name
        file_salt str: File salt
        \b
        min_id integer: File ID should be > min_id
        max_id integer: File ID should be < max_id
        \b
        min_size integer: File Size should be > min_size
        max_size integer: File Size should be < max_size
        \b
        min_time integer/float: Upload Time should be > min_time
        max_time integer/float: Upload Time should be < max_time
        \b
        imported bool: Yield only imported files
        re       bool: re_search for every bytes filter
    \b
    See tgbox.readthedocs.io/en/indev/
        tgbox.html#tgbox.tools.SearchFilter
    \b
    You can also use special flags to specify
    that filters is for include or exclude search.
    \b
    Example:\b
        # Include is used by default
        tgbox-cli file-remove min_id=3 max_id=100
        \b
        # Include flag (will ignore unmatched)
        tgbox-cli file-remove +i file_name=.png
        \b
        # Exclude flag (will ignore matched)
        tgbox-cli file-remove +e file_name=.png
        \b
        You can use both, the ++include and
        ++exclude (+i, +e) in one command.
    """
    if local_only:
        dlb, _ = get_box(ignore_remote=True)
    else:
        dlb, drb = get_box()
    try:
        sf = filters_to_searchfilter(filters)
    except IndexError: # Incorrect filters format
        echo('[RED]Incorrect filters! Make sure to use format filter=value[RED]')
        raise ExitProgram
    except KeyError as e: # Unknown filters
        echo(f'[RED]Filter "{e.args[0]}" doesn\'t exists[RED]')
        raise ExitProgram

    if not filters:
        echo(
            '''\n[RED]You didn\'t specified any search filter.\n   This '''
            '''will [WHITE]REMOVE ALL FILES[WHITE] in your Box[RED]\n'''
        )
        if not click.confirm('Are you TOTALLY sure?'):
            raise ExitProgram

    to_remove = dlb.search_file(sf, cache_preview=False)

    if ask_before_remove:
        for dlbf in sync_async_gen(to_remove):
            file_path = str(Path(dlbf.file_path) / dlbf.file_name)
            echo(f'@ [RED]Removing[RED] [WHITE]Box[WHITE]({file_path})')

            while True:
                echo('')
                choice = click.prompt(
                    'Are you TOTALLY sure? ([y]es | [n]o | [i]nfo | [e]xit)'
                )
                if choice.lower() in ('yes','y'):
                    tgbox.sync(dlbf.delete())
                    if not local_only:
                        drbf = tgbox.sync(drb.get_file(dlbf.id))
                        tgbox.sync(drbf.delete())
                    echo('')
                    break
                elif choice.lower() in ('no','n'):
                    echo('')
                    break
                elif choice.lower() in ('info','i'):
                    echo(format_dxbf(dlbf).rstrip())
                elif choice.lower() in ('exit','e'):
                    raise ExitProgram
                else:
                    echo('[RED]Invalid choice, try again[RED]')
    else:
        echo('\n[YELLOW]Searching for LocalBox files[YELLOW]...')
        to_remove = [dlbf for dlbf in sync_async_gen(to_remove)]

        if not to_remove:
            echo('[YELLOW]No files to remove was found.[YELLOW]')
        else:
            echo(f'[WHITE]Removing[WHITE] [RED]{len(to_remove)}[RED] [WHITE]files[WHITE]...')
            tgbox.sync(dlb.delete_files(*to_remove, rb=(None if local_only else drb)))
            echo('[GREEN]Done.[GREEN]')

    raise ExitProgram

@cli.command()
@click.argument('filters', nargs=-1)
@click.option(
    '--locate', '-l', is_flag=True,
    help='If specified, will open file path in file manager'
)
@click.option(
    '--propagate', '-p', is_flag=True,
    help='If specified, will open ALL matched files'
)
@click.option(
    '--continuously', '-c', is_flag=True,
    help='Do not interrupt --propagate with input-ask'
)
def file_open(filters, locate, propagate, continuously):
    """
    Will try to search by filters and open the
    already downloaded file in the default OS app
    \b
    Available filters:\b
        scope: Define a path as search scope
               -----------------------------
               The *scope* is an absolute directory in which
               we will search your file by other filters. By
               default, the tgbox.api.utils.search_generator
               will search over the entire LocalBox. This can
               be slow if you're have too many files.
               \b
               Example: let's imagine that You're a Linux user which
               share it's Box with the Windows user. In this case,
               Your LocalBox will contain a path parts on the
               '/' (Linux) and 'C:\\' (Windows) roots. If You
               know that some file was uploaded by Your friend,
               then You can specify a scope='C:\\' to ignore
               all files uploaded from the Linux machine. This
               will significantly fasten the search process,
               because almost all filters require to select
               row from the LocalBox DB, decrypt Metadata and
               compare its values with ones from SearchFilter.
               \b
               !: The scope will be ignored on RemoteBox search.
               !: The min_id & max_id will be ignored if scope used.
        \b
        id integer: File’s ID
        mime str: File mime type
        \b
        cattrs: File CAttrs
                -----------
                Can be used hexed PackedAttributes
                or special CLI format alternatively:
                cattrs="comment:test type:message"
        \b
        file_path str: File path
        file_name str: File name
        file_salt str: File salt
        \b
        min_id integer: File ID should be > min_id
        max_id integer: File ID should be < max_id
        \b
        min_size integer: File Size should be > min_size
        max_size integer: File Size should be < max_size
        \b
        min_time integer/float: Upload Time should be > min_time
        max_time integer/float: Upload Time should be < max_time
        \b
        imported bool: Yield only imported files
        re       bool: re_search for every bytes filter
    \b
    See tgbox.readthedocs.io/en/indev/
        tgbox.html#tgbox.tools.SearchFilter
    \b
    You can also use special flags to specify
    that filters is for include (+i, ++include
    [by default]) or exclude (+e, ++exclude) search.
    """
    dlb, _ = get_box(ignore_remote=True)

    try:
        sf = filters_to_searchfilter(filters)
    except IndexError: # Incorrect filters format
        echo('[RED]Incorrect filters! Make sure to use format filter=value[RED]')
        raise ExitProgram
    except KeyError as e: # Unknown filters
        echo(f'[RED]Filter "{e.args[0]}" doesn\'t exists[RED]')
        raise ExitProgram

    to_open = dlb.search_file(sf)

    for dlbf in sync_async_gen(to_open):
        tgbox.sync(dlbf.directory.lload(full=True))

        outpath = tgbox.defaults.DOWNLOAD_PATH / 'Files' / '@'
        outpath = outpath / str(dlbf.directory).strip('/')
        outpath = str(outpath.absolute() / dlbf.file_name)

        click.launch(outpath, locate=locate)

        if not propagate:
            raise ExitProgram

        if propagate and not continuously:
            click.prompt(
                text = '\n@ Press ENTER to open the next file >> ',
                hide_input = True,
                prompt_suffix = ''
            )
    raise ExitProgram

@cli.command()
@click.argument('filters', nargs=-1)
@click.option(
    '--entity', '-e', required=True,
    help='Entity to send file to'
)
def file_forward(filters, entity):
    """
    Will forward file to specified entity

    \b
    Available filters:\b
        scope: Define a path as search scope
               -----------------------------
               The *scope* is an absolute directory in which
               we will search your file by other filters. By
               default, the tgbox.api.utils.search_generator
               will search over the entire LocalBox. This can
               be slow if you're have too many files.
               \b
               Example: let's imagine that You're a Linux user which
               share it's Box with the Windows user. In this case,
               Your LocalBox will contain a path parts on the
               '/' (Linux) and 'C:\\' (Windows) roots. If You
               know that some file was uploaded by Your friend,
               then You can specify a scope='C:\\' to ignore
               all files uploaded from the Linux machine. This
               will significantly fasten the search process,
               because almost all filters require to select
               row from the LocalBox DB, decrypt Metadata and
               compare its values with ones from SearchFilter.
               \b
               !: The scope will be ignored on RemoteBox search.
               !: The min_id & max_id will be ignored if scope used.
        \b
        id integer: File’s ID
        mime str: File mime type
        \b
        cattrs: File CAttrs
                -----------
                Can be used hexed PackedAttributes
                or special CLI format alternatively:
                cattrs="comment:test type:message"
        \b
        file_path str: File path
        file_name str: File name
        file_salt str: File salt
        \b
        min_id integer: File ID should be > min_id
        max_id integer: File ID should be < max_id
        \b
        min_size integer: File Size should be > min_size
        max_size integer: File Size should be < max_size
        \b
        min_time integer/float: Upload Time should be > min_time
        max_time integer/float: Upload Time should be < max_time
        \b
        imported bool: Yield only imported files
        re       bool: re_search for every bytes filter
    \b
    See tgbox.readthedocs.io/en/indev/
        tgbox.html#tgbox.tools.SearchFilter
    \b
    You can also use special flags to specify
    that filters is for include or exclude search.
    \b
    Example:\b
        # Include is used by default
        tgbox-cli file-forward scope=/home/non/Documents -e @username
        \b
        # Include flag (will ignore unmatched)
        tgbox-cli file-forward +i id=22 --entity me
        \b
        # Exclude flag (will ignore matched)
        tgbox-cli file-forward +e mime=audio --entity @channel
        \b
        You can use both, the ++include and
        ++exclude (+i, +e) in one command.
    """
    dlb, drb = get_box()
    try:
        sf = filters_to_searchfilter(filters)
    except IndexError: # Incorrect filters format
        echo('[RED]Incorrect filters! Make sure to use format filter=value[RED]')
        raise ExitProgram
    except KeyError as e: # Unknown filters
        echo(f'[RED]Filter "{e.args[0]}" doesn\'t exists[RED]')
        raise ExitProgram

    to_forward = dlb.search_file(sf)

    for dlbf in sync_async_gen(to_forward):
        drbf = tgbox.sync(drb.get_file(dlbf.id))
        try:
            tgbox.sync(drb.tc.forward_messages(entity, drbf.message))
            echo(f'[GREEN]ID{drbf.id}: {drbf.file_name}: was forwarded to {entity}[GREEN]')
        except (UsernameNotOccupiedError, UsernameInvalidError, ValueError):
            echo(f'[YELLOW]Can not find entity "{entity}"[YELLOW]')

    raise ExitProgram

@cli.command()
@click.argument('filters', nargs=-1)
@click.option(
    '--attribute', '-a', required=True,
    help='File attribute, e.g file_name=test.txt'
)
@click.option(
    '--local-only','-l', is_flag=True,
    help='If specified, will change attr only in LocalBox'
)
def file_attr_change(filters, attribute, local_only):
    """Will change attribute of Box files (search by filters)

    \b
    Available filters:\b
        scope: Define a path as search scope
               -----------------------------
               The *scope* is an absolute directory in which
               we will search your file by other filters. By
               default, the tgbox.api.utils.search_generator
               will search over the entire LocalBox. This can
               be slow if you're have too many files.
               \b
               Example: let's imagine that You're a Linux user which
               share it's Box with the Windows user. In this case,
               Your LocalBox will contain a path parts on the
               '/' (Linux) and 'C:\\' (Windows) roots. If You
               know that some file was uploaded by Your friend,
               then You can specify a scope='C:\\' to ignore
               all files uploaded from the Linux machine. This
               will significantly fasten the search process,
               because almost all filters require to select
               row from the LocalBox DB, decrypt Metadata and
               compare its values with ones from SearchFilter.
               \b
               !: The scope will be ignored on RemoteBox search.
               !: The min_id & max_id will be ignored if scope used.
        \b
        id integer: File’s ID
        mime str: File mime type
        \b
        cattrs: File CAttrs
                -----------
                Can be used hexed PackedAttributes
                or special CLI format alternatively:
                cattrs="comment:test type:message"
        \b
        file_path str: File path
        file_name str: File name
        file_salt str: File salt
        \b
        min_id integer: File ID should be > min_id
        max_id integer: File ID should be < max_id
        \b
        min_size integer: File Size should be > min_size
        max_size integer: File Size should be < max_size
        \b
        min_time integer/float: Upload Time should be > min_time
        max_time integer/float: Upload Time should be < max_time
        \b
        imported bool: Yield only imported files
        re       bool: re_search for every bytes filter
    \b
    See tgbox.readthedocs.io/en/indev/
        tgbox.html#tgbox.tools.SearchFilter
    \b
    You can also use special flags to specify
    that filters is for include or exclude search.
    \b
    Example:\b
        # Include is used by default
        tgbox-cli file-attr-change min_id=3 max_id=100 -a file_path=/home/non/
        \b
        # Include flag (will ignore unmatched)
        tgbox-cli file-attr-change +i file_name=.png -a file_path=/home/non/Pictures
        \b
        # Exclude flag (will ignore matched)
        tgbox-cli file-attr-change +e file_name=.png -a file_path=/home/non/NonPictures
        \b
        # Attribute without value will reset it to default
        tgbox-cli file-attr-change id=22 -a file_name=
        \b
        You can use both, the ++include and
        ++exclude (+i, +e) in one command.
    """
    dlb, drb = get_box()
    try:
        sf = filters_to_searchfilter(filters)
    except IndexError: # Incorrect filters format
        echo('[RED]Incorrect filters! Make sure to use format filter=value[RED]')
        raise ExitProgram
    except KeyError as e: # Unknown filters
        echo(f'[RED]Filter "{e.args[0]}" doesn\'t exists[RED]')
        raise ExitProgram

    if not filters:
        echo(
            '''\n[RED]You didn\'t specified any search filter.\n   This '''
            '''will [WHITE]change attrs for all files[WHITE] in your Box[RED]\n'''
        )
        if not click.confirm('Are you TOTALLY sure?'):
            raise ExitProgram

    attr_key, attr_value = attribute.split('=',1)

    if attr_key == 'cattrs':
        try:
            attr_value = tgbox.tools.PackedAttributes.unpack(
                bytes.fromhex(attr_value)
            );  assert attr_value
        except (ValueError, AssertionError):
            # Specified value isn't a hexed PackedAttributes
            cattrs = {}
            for items in attr_value.split():
                items = items.split(':',1)
                cattrs[items[0]] = items[1].encode()

            attr_value = cattrs

    if attr_key == 'cattrs':
        changes = {attr_key: tgbox.tools.PackedAttributes.pack(**attr_value)}
    else:
        changes = {attr_key: attr_value.encode()}

    to_change = dlb.search_file(sf, cache_preview=False)

    for dlbf in sync_async_gen(to_change):
        if local_only:
            tgbox.sync(dlbf.update_metadata(changes=changes, dlb=dlb))
        else:
            drbf = tgbox.sync(drb.get_file(dlbf.id))
            tgbox.sync(drbf.update_metadata(changes=changes, dlb=dlb))

        echo(
            f'''([WHITE]{dlbf.id}[WHITE]) {dlbf.file_name} '''
            f'''<= [YELLOW]{attribute}[YELLOW]''')

    raise ExitProgram

# ========================================================= #

# = LocalBox directory management commands ================ #

@cli.command()
def dir_list():
    """List all directories in LocalBox"""

    dlb, _ = get_box(ignore_remote=True)
    dirs = dlb.contents(ignore_files=True)

    for dir in sync_async_gen(dirs):
        tgbox.sync(dir.lload(full=True))
        echo(str(dir))

    raise ExitProgram

# ========================================================= #

# = Commands to manage TGBOX logger ======================= #

@cli.command()
@click.option(
    '--locate', '-l', is_flag=True,
    help='If specified, will open file path in file manager'
)
def logfile_open(locate):
    """Open TGBOX-CLI log file with the default app"""
    click.launch(str(logfile), locate=locate)

@cli.command()
def logfile_clear():
    """Will clear TGBOX-CLI log file"""
    open(logfile,'w').close()
    echo('[GREEN]Done.[GREEN]')

@cli.command()
def logfile_size():
    """Will return size of TGBOX-CLI log file"""
    size = format_bytes(logfile.stat().st_size)
    echo(f'[WHITE]{str(logfile)}[WHITE]: {size}')

@cli.command()
@click.argument('entity', nargs=-1)
def logfile_send(entity):
    """
    Send logfile to the specified entity

    \b
    Example:\b
        tgbox-cli logfile-send @username
    """
    dlb, drb = get_box()

    for e in entity:
        tgbox.sync(drb.tc.send_file(e, logfile))
        echo(f'[WHITE]Logfile has been sent to[WHITE] [BLUE]{e}[BLUE]')

    raise ExitProgram

# ========================================================= #

# = Documentation commands  =============================== #

@cli.command(name='help')
@click.option(
    '--non-interactive', '-n', is_flag=True,
    help='If specified, will echo to shell instead of pager'
)
def help_(non_interactive):
    """Write this command for extended Help!"""

    help_path = Path(__file__).parent / 'data'
    help_text = open(help_path / 'help.txt').read()

    if non_interactive:
        echo(help_text)
    else:
        colored = True if system().lower() == 'windows' else None
        colored = False if TGBOX_CLI_NOCOLOR else colored
        click.echo_via_pager(color(help_text), color=colored)

# ========================================================= #

# = Hidden CLI tools commands ============================= #

@cli.command(hidden=True)
@click.option(
    '--size', '-s', default=32,
    help='SessionKey bytesize'
)
def sk_gen(size: int):
    """Generate random urlsafe b64encoded SessionKey"""
    echo(urlsafe_b64encode(tgbox.crypto.get_rnd_bytes(size)).decode())

@cli.command(hidden=True)
@click.option(
    '--words', '-w', default=6,
    help='Words amount in Phrase'
)
def phrase_gen(words: int):
    """Generate random Phrase"""
    echo(f'[MAGENTA]{tgbox.keys.Phrase.generate(words)}[MAGENTA]')

@cli.command(hidden=True)
def python():
    """Launch interactive Python console"""
    interactive_console(local=globals())
    raise ExitProgram

# ========================================================= #

def safe_tgbox_cli_startup():
    try:
        cli(standalone_mode=False)
    except Exception as e:
        # Close Progressbar
        enlighten_manager.stop()
        try:
            # Try to close all connections on exception
            dlb, drb = get_box(raise_if_none=True)
            try:
                if dlb:
                    tgbox.sync(dlb.done())
            except ValueError:
                pass # No active connection

            if drb:
                tgbox.sync(drb.done())
        except ExitProgram:
            pass # Box wasn't connected to TGBOX-CLI (raise_if_none)
        except tgbox.errors.SessionUnregistered:
            pass # Session was disconnected

        if isinstance(e, (ExitProgram, click.Abort)):
            _exit(0)
        else:
            traceback = ''.join(format_exception(
                e,
                value = e,
                tb = e.__traceback__
            ))
            # This will ignore some click exceptions that we really
            # don't need to log like click.exceptions.UsageError
            if not issubclass(type(e), click.exceptions.ClickException):
                logger.error(traceback)

            if getenv('TGBOX_CLI_DEBUG'):
                echo(f'[RED]{traceback}[RED]')

            elif e.args: # Will echo only if error have message
                echo(f'[RED]{e}[RED]')

            echo(''); _exit(1)

if __name__ == '__main__':
    safe_tgbox_cli_startup()
