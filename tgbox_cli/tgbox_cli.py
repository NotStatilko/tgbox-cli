#!/usr/bin/env python3

import click

from os import getenv
from pathlib import Path

import warnings

# Disable annoying (in CLI) UserWarning/RuntimeWarning
warnings.simplefilter('ignore', category=UserWarning)
warnings.simplefilter('ignore', category=RuntimeWarning)


# It's here only because we need it in autocompletion mode and CLI
TGBOX_CLI_SHOW_PASSWORD = bool(getenv('TGBOX_CLI_SHOW_PASSWORD'))

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
    from platform import system
    from datetime import datetime

    from base64 import urlsafe_b64encode
    from shutil import get_terminal_size
    from traceback import format_exception

    from subprocess import run as subprocess_run, PIPE
    from code import interact as interactive_console
    from asyncio import gather, get_event_loop

    from sys import exit

    if _MEIPASS:
        # PyInstaller builds has some problems in
        # importing modules started with dots, so
        # here we will make an import from package
        from tgbox_cli.tools import *
        from tgbox_cli.version import *
        from tgbox_cli.session import *
    else:
        from .tools import *
        from .version import *
        from .session import *

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

    cli_folder = get_cli_folder()

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


# = Function to check that CTX has requested fields ======= #

class CheckCTXFailed(click.exceptions.ClickException):
    """Will be raised if check_ctx found unsupported requirement"""

def check_ctx(ctx, *, session=False, account=False, dlb=False, drb=False):
    if session and not ctx.obj.session:
        echo(
            '''[RED]You should run[RED] [WHITE]tgbox-cli '''
            '''cli-init[WHITE] [RED]firstly.[RED]'''
        )
        raise CheckCTXFailed('Failed on "session" requirement')

    if account and not ctx.obj.account:
        echo(
          '''[RED]You should run [RED][WHITE]tgbox-cli '''
          '''account-connect [WHITE][RED]firstly.[RED]'''
        )
        raise CheckCTXFailed('Failed on "account" requirement')

    if dlb and not ctx.obj.dlb:
        echo(
            '''[RED]You didn\'t connected box yet. Use[RED] '''
            '''[WHITE]box-open[WHITE] [RED]command.[RED]'''
        )
        raise CheckCTXFailed('Failed on "dlb" requirement')

    if drb and not ctx.obj.drb:
        echo(
            '''[RED]You didn\'t connected box yet. Use[RED] '''
            '''[WHITE]box-open[WHITE] [RED]command.[RED]'''
        )
        raise CheckCTXFailed('Failed on "drb" requirement')

# ========================================================= #

# = CLI configuration ===================================== #

class StructuredGroup(click.Group):
    def __init__(self, name=None, commands=None, **kwargs):
        super().__init__(name, commands, **kwargs)
        self.commands = commands or {}

    def list_commands(self, ctx):
        return self.commands

    def format_commands(self, ctx, formatter):
        if session_key := getenv('TGBOX_CLI_SK'):
            session = Session(session_key)
        else:
            session = None

        formatter.width = get_terminal_size().columns

        formatter.write_text('')
        formatter.write_heading('Commands')

        last_letter = None
        for k,v in self.commands.items():
            if v.hidden:
                continue

            if last_letter != k[0]:
                last_letter = k[0]
                formatter.write_paragraph()

            if v.name == 'help':
                COLOR = '[GREEN]'

            elif v.name == 'cli-init' and not session:
                COLOR = '[YELLOW]'

            elif session and v.name in ('box-make', 'box-clone', 'box-list'):
                conditions = (
                    session['CURRENT_ACCOUNT'] is not None,
                    session['CURRENT_BOX'] is None
                )
                COLOR = '[YELLOW]' if all(conditions) else '[WHITE]'

            elif session and v.name in ('box-open', 'account-connect'):
                conditions = (
                    session['CURRENT_BOX'] is None,
                    session['CURRENT_ACCOUNT'] is None,
                )
                COLOR = '[YELLOW]' if all(conditions) else '[WHITE]'
            else:
                COLOR = '[WHITE]'

            DOT = 'O' if COLOR != '[WHITE]' else 'o'
            COLOR = '' if TGBOX_CLI_NOCOLOR else COLOR

            text = color(
                f'''  {DOT}  {COLOR}{v.name}{COLOR} :: '''
                f'''{v.get_short_help_str().strip()}'''
            )
            formatter.write_text(text)

        if not TGBOX_CLI_NOCOLOR:
            formatter.write_text('\x1b[0m')

@click.group(cls=StructuredGroup)
@click.pass_context
def cli(ctx):
    class Objects:
        """
        The main purpose of this class (except just a
        container) is to implement a "lazy" drb/account
        attributes. We will not open internet connection
        if there is no request for drb/account property.
        """
        def __init__(self):
            self.dlb = None
            self._drb = None

            self._account = None
            self.session = None

            self.__drb_initialized = False

        def __repr__(self):
            return f'Objects: {self.__dict__=}'

        @property
        def drb(self):
            if self._drb and not self.__drb_initialized:
                self._drb = tgbox.sync(self._drb)
                self.__drb_initialized = True

            return self._drb

        @property
        def account(self):
            if self._account and not isinstance(
                    self._account, tgbox.api.TelegramClient):
                self.drb # Make sure DRB is initialized
                self._account = self._account()

            if self._account and not self._account.is_connected():
                tgbox.sync(self._account.connect())

            return self._account

    ctx.obj = Objects()

    # = Getting Proxy ======================================== #

    if getenv('https_proxy'):
        proxy = env_proxy_to_pysocks(getenv('https_proxy'))

    elif getenv('http_proxy'):
        proxy = env_proxy_to_pysocks(getenv('http_proxy'))
    else:
        proxy = None

    # ========================================================= #

    # = Setting CLI Session =================================== #

    if session_key := getenv('TGBOX_CLI_SK'):
        ctx.obj.session = Session(session_key)
    else:
        ctx.obj.session = None

    # ========================================================= #

    # = Setting DLB & DRB ===================================== #

    if not ctx.obj.session or ctx.obj.session['CURRENT_BOX'] is None:
        ctx.obj.dlb = None
        ctx.obj._drb = None

    elif ctx.obj.session and ctx.obj.session['CURRENT_BOX'] is not None:
        box_path = ctx.obj.session['BOX_LIST'][ctx.obj.session['CURRENT_BOX']][0]
        basekey  = ctx.obj.session['BOX_LIST'][ctx.obj.session['CURRENT_BOX']][1]

        if not Path(box_path).exists():
            ctx.obj.dlb = None
            ctx.obj._drb = None
        else:
            dlb = tgbox.sync(tgbox.api.get_localbox(
                tgbox.keys.BaseKey(basekey), box_path)
            )
            drb = tgbox.api.get_remotebox(dlb, proxy=proxy)

            ctx.obj.dlb = dlb
            ctx.obj._drb = drb

    # ========================================================= #

    # = Setting TelegramClient ================================ #

    if not ctx.obj.session:
        ctx.obj._account = None

    elif ctx.obj.session['CURRENT_ACCOUNT'] is None\
        and ctx.obj.session['CURRENT_BOX'] is not None:
            if ctx.obj._drb:
                ctx.obj._account = lambda: ctx.obj.drb.tc
            else:
                ctx.obj._account = None

    elif ctx.obj.session['CURRENT_ACCOUNT'] is not None:
        current_account = ctx.obj.session['CURRENT_ACCOUNT']
        tg_session = ctx.obj.session['ACCOUNT_LIST'][current_account]

        ctx.obj._account = tgbox.api.TelegramClient(
            session=tg_session,
            api_id=API_ID,
            api_hash=API_HASH,
            proxy=proxy)
    else:
        ctx.obj._account = None

    # ========================================================= #

    def on_exit(ctx_):
        if ctx_.obj.dlb:
            try:
                tgbox.sync(ctx_.obj.dlb.done())
            except ValueError:
                pass # No active connection

        if isinstance(ctx_.obj._drb, tgbox.api.DecryptedRemoteBox):
            try:
                tgbox.sync(ctx_.obj.drb.done())
            except tgbox.errors.SessionUnregistered:
                pass # Session was disconnected

        enlighten_manager.stop()

    # This will close Local & Remote on exit
    ctx.call_on_close(lambda: on_exit(ctx))

# ========================================================= #

# = Function to search for more RemoteBox on account ===== #

@click.pass_context
def select_remotebox(ctx, number: int, prefix: str):
    check_ctx(ctx, account=True)

    count, erb = 1, None
    to_iter = ctx.obj.account.iter_dialogs()

    for chat in sync_async_gen(to_iter):
        if prefix in chat.title and chat.is_channel:
            if count != number:
                count += 1
            else:
                erb = tgbox.api.remote.EncryptedRemoteBox(
                    chat, ctx.obj.account)
                break

    if not erb:
        echo(f'[RED]RemoteBox by number={number} not found.[RED]')
    else:
        return erb

# ========================================================= #

# = CLI manage & setup commands =========================== #

@cli.command()
@click.pass_context
def cli_init(ctx):
    """Get commands for initializing TGBOX-CLI"""

    if ctx.obj.session:
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
    """Get information about the TGBOX-CLI build"""

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
@click.pass_context
def account_connect(ctx, phone):
    """Connect your Telegram account"""
    check_ctx(ctx, session=True)

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
        hide_input = (not TGBOX_CLI_SHOW_PASSWORD),
        default = '',
        show_default = False
    )
    echo('[CYAN]Trying to sign-in...[CYAN] ', nl=False)
    tgbox.sync(tc.log_in(code=code, password=password))

    echo('[GREEN]Successful![GREEN]')
    echo('[CYAN]Updating local data...[CYAN] ', nl=False)

    tc_id = tgbox.sync(tc.get_me()).id

    if ctx.obj.session['CURRENT_ACCOUNT'] is None:
        ctx.obj.session['ACCOUNT_LIST'].append(tc.session.save())
        ctx.obj.session['CURRENT_ACCOUNT'] = 0 # List index
    else:
        disconnected_sessions = []
        for tg_session in ctx.obj.session['ACCOUNT_LIST']:
            other_tc = tgbox.api.TelegramClient(
                session=tg_session,
                api_id=API_ID,
                api_hash=API_HASH
            )
            tgbox.sync(other_tc.connect())
            try:
                other_tc_id = tgbox.sync(other_tc.get_me()).id
            except AttributeError:
                # If session was disconnected
                disconnected_sessions.append(tg_session)
                continue

            if other_tc_id == tc_id:
                tgbox.sync(tc.log_out())
                echo('[RED]Account already added[RED]')
                return

        for d_session in disconnected_sessions:
            ctx.obj.session['ACCOUNT_LIST'].remove(d_session)

        ctx.obj.session['ACCOUNT_LIST'].append(tc.session.save())
        ctx.obj.session['CURRENT_ACCOUNT'] = len(ctx.obj.session['ACCOUNT_LIST']) - 1

    ctx.obj.session.commit()
    echo('[GREEN]Successful![GREEN]')

@cli.command()
@click.option(
    '--number','-n', required=True, type=int,
    help='Number of connected account'
)
@click.option(
    '--log-out', is_flag=True,
    help='Will log out from account if specified'
)
@click.pass_context
def account_disconnect(ctx, number, log_out):
    """Disconnect selected Account from Session"""

    check_ctx(ctx, session=True)

    if ctx.obj.session['CURRENT_ACCOUNT'] is None:
        echo('[RED]You don\'t have any connected account.[RED]')

    elif number < 1 or number > len(ctx.obj.session['ACCOUNT_LIST']):
        echo(
            f'''[RED]There is no account #{number}. Use [RED]'''
             '''[WHITE]account-list[WHITE] [RED]command.[RED]''')
    else:
        if log_out:
            tg_session = ctx.obj.session['ACCOUNT_LIST'][number-1]

            tc = tgbox.api.TelegramClient(
                session=tg_session,
                api_id=API_ID,
                api_hash=API_HASH
            )
            tgbox.sync(tc.connect())
            tgbox.sync(tc.log_out())

        ctx.obj.session['ACCOUNT_LIST'].pop(number-1)

        if not ctx.obj.session['ACCOUNT_LIST']:
            ctx.obj.session['CURRENT_ACCOUNT'] = None
            echo('[GREEN]Disconnected. No more accounts.[GREEN]')
        else:
            ctx.obj.session['CURRENT_ACCOUNT'] = 0
            echo('[GREEN]Disconnected & switched to the account #1[GREEN]')

        ctx.obj.session.commit()

@cli.command()
@click.pass_context
def account_list(ctx):
    """List all connected accounts"""

    check_ctx(ctx, session=True)

    if ctx.obj.session['CURRENT_ACCOUNT'] is None:
        echo(
            '''[RED]You didn\'t connected any account yet. Use[RED] '''
            '''[WHITE]account-connect[WHITE] [RED]command firstly.[RED]''')
    else:
        echo(
            '''\n[WHITE]You\'re using account[WHITE] [RED]'''
           f'''#{str(ctx.obj.session['CURRENT_ACCOUNT'] + 1)}[RED]\n'''
        )
        disconnected_sessions = []
        for count, tg_session in enumerate(ctx.obj.session['ACCOUNT_LIST']):
            try:
                tc = tgbox.api.TelegramClient(
                    session=tg_session,
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
                disconnected_sessions.append(tg_session)

        for d_session in disconnected_sessions:
            ctx.obj.session['ACCOUNT_LIST'].remove(d_session)

        ctx.obj.session.commit()
        echo('')

@cli.command()
@click.option(
    '--number', '-n', required=True, type=int,
    help='Number of other connected account, use account-list command'
)
@click.pass_context
def account_switch(ctx, number):
    """Set as main your another connected Account"""

    check_ctx(ctx, session=True)

    if ctx.obj.session['CURRENT_ACCOUNT'] is None:
        echo(
            '''[RED]You didn\'t connected any account yet. Use[RED] '''
            '''[WHITE]account-connect[WHITE] [RED]command firstly.[RED]'''
        )
    elif number < 1 or number > len(ctx.obj.session['ACCOUNT_LIST']):
        echo(
            f'''[RED]There is no account #{number}. Use [RED]'''
             '''[WHITE]account-list[WHITE] [RED]command.[RED]'''
        )
    elif number-1 == ctx.obj.session['CURRENT_ACCOUNT']:
        echo(
            f'''[YELLOW]You already on this account. See other with[YELLOW] '''
             '''[WHITE]account-list[WHITE] [YELLOW]command.[YELLOW]''')
    else:
        ctx.obj.session['CURRENT_ACCOUNT'] = number - 1
        ctx.obj.session.commit()

        echo(f'[GREEN]You switched to account #{number}[GREEN]')

@cli.command()
@click.option(
    '--show-phone', is_flag=True,
    help='Specify this to show phone number'
)
@click.pass_context
def account_info(ctx, show_phone):
    """Show information about current account"""

    check_ctx(ctx, account=True)

    me = tgbox.sync(ctx.obj.account.get_me())

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
@click.pass_context
def box_make(ctx, box_name, box_salt, phrase, s, n, p, r, l):
    """Create the new Box, the Remote and Local"""

    check_ctx(ctx, account=True)

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

            phrase = click.prompt(
                text = 'Phrase',
                hide_input = (not TGBOX_CLI_SHOW_PASSWORD)
            )
            phrase_repeat = click.prompt(
                text = 'Repeat phrase',
                hide_input = (not TGBOX_CLI_SHOW_PASSWORD)
            )

    echo('[CYAN]Making BaseKey...[CYAN] ', nl=False)

    box_salt = bytes.fromhex(box_salt) if box_salt else None

    basekey = tgbox.keys.make_basekey(
        phrase.strip().encode(),
        salt=bytes.fromhex(s),
        n=n, p=p, r=r, dklen=l
    )
    echo('[GREEN]Successful![GREEN]')

    echo('[CYAN]Making RemoteBox...[CYAN] ', nl=False)
    erb = tgbox.sync(tgbox.api.make_remotebox(
        ctx.obj.account, box_name, box_salt=box_salt)
    )
    echo('[GREEN]Successful![GREEN]')

    echo('[CYAN]Making LocalBox...[CYAN] ', nl=False)
    dlb = tgbox.sync(tgbox.api.make_localbox(erb, basekey))
    echo('[GREEN]Successful![GREEN]')

    echo('[CYAN]Updating local data...[CYAN] ', nl=False)

    box_path = str(Path(box_name).absolute())

    ctx.obj.session['BOX_LIST'].append([box_path, basekey.key])
    ctx.obj.session['CURRENT_BOX'] = len(ctx.obj.session['BOX_LIST']) - 1

    ctx.obj.session.commit()

    tgbox.sync(erb.done())
    tgbox.sync(dlb.done())

    echo('[GREEN]Successful![GREEN]')

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
    prompt=True, hide_input=(not TGBOX_CLI_SHOW_PASSWORD),
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
@click.pass_context
def box_open(ctx, box_path, phrase, s, n, p, r, l):
    """Decrypt & connect existing LocalBox"""

    check_ctx(ctx, session=True)

    echo('[CYAN]Making BaseKey...[CYAN] ', nl=False)

    basekey = tgbox.keys.make_basekey(
        phrase.strip().encode(),
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
    else:
        echo('[GREEN]Successful![GREEN]')
        echo('[CYAN]Updating local data...[CYAN] ', nl=False)

        for _, other_basekey in ctx.obj.session['BOX_LIST']:
            if basekey.key == other_basekey:
                echo('[RED]This Box is already opened[RED]')
                break
        else:
            ctx.obj.session['BOX_LIST'].append([box_path, basekey.key])
            ctx.obj.session['CURRENT_BOX'] = len(ctx.obj.session['BOX_LIST']) - 1

            ctx.obj.session.commit()
            echo('[GREEN]Successful![GREEN]')

        tgbox.sync(dlb.done())

@cli.command()
@click.option(
    '--number', '-n', required=True, type=int,
    help='Number of other connected box, use box-list command'
)
@click.pass_context
def box_close(ctx, number):
    """Disconnect selected LocalBox from Session"""

    check_ctx(ctx, dlb=True)

    if number < 1 or number > len(ctx.obj.session['BOX_LIST']):
        echo('[RED]Invalid number, see box-list[RED]')
    else:
        ctx.obj.session['BOX_LIST'].pop(number-1)

        if not ctx.obj.session['BOX_LIST']:
            ctx.obj.session['CURRENT_BOX'] = None
            echo('No more Boxes, use [WHITE]box-open[WHITE].')
        else:
            ctx.obj.session['CURRENT_BOX'] = 0
            echo('[GREEN]Disconnected & switched to the Box #1[GREEN]')

        ctx.obj.session.commit()

@cli.command()
@click.option(
    '--number', '-n', required=True, type=int,
    help='Number of other connected box, use box-list command'
)
@click.pass_context
def box_switch(ctx, number):
    """Set as main your another connected Box"""

    check_ctx(ctx, dlb=True)

    if number < 1 or number > len(ctx.obj.session['BOX_LIST']):
        echo(
            f'''[RED]There is no box #{number}. Use[RED] '''
             '''[WHITE]box-list[WHITE] [RED]command.[RED]'''
        )
    elif number-1 == ctx.obj.session['CURRENT_BOX']:
        echo(
            '''[YELLOW]You already use this box. See other with[YELLOW] '''
            '''[WHITE]box-list[WHITE] [YELLOW]command.[YELLOW]'''
        )
    else:
        ctx.obj.session['CURRENT_BOX'] = number - 1
        ctx.obj.session.commit()

        echo(f'[GREEN]You switched to box #{number}[GREEN]')

@cli.command()
@click.option(
    '--remote', '-r', is_flag=True,
    help='If specified, will search for Remote Boxes on Account'
)
@click.option(
    '--prefix', '-p', default=tgbox.defaults.REMOTEBOX_PREFIX,
    help='Channels with this prefix will be searched (only if --remote)'
)
@click.pass_context
def box_list(ctx, remote, prefix):
    """List all Boxes (--remote for Remote)"""

    if remote:
        check_ctx(ctx, account=True)

        count = 0

        echo('[YELLOW]Searching...[YELLOW]')
        for chat in sync_async_gen(ctx.obj.account.iter_dialogs()):
            if prefix in chat.title and chat.is_channel:
                erb = tgbox.api.EncryptedRemoteBox(chat, ctx.obj.account)

                erb_name = tgbox.sync(erb.get_box_name())
                erb_salt = tgbox.sync(erb.get_box_salt())
                erb_salt = urlsafe_b64encode(erb_salt).decode()

                echo(
                    f'''[WHITE]{count+1}[WHITE]) [BLUE]{erb_name}[BLUE]'''
                    f'''@[BRIGHT_BLACK]{erb_salt}[BRIGHT_BLACK]'''
                )
                count += 1

        echo('[YELLOW]Done.[YELLOW]')
    else:
        check_ctx(ctx, session=True)

        if ctx.obj.session['CURRENT_BOX'] is None:
            echo(
                '''[RED]You didn\'t opened any box yet. Use[RED] '''
                '''[WHITE]box-open[WHITE] [RED]command firstly.[RED]''')
        else:
            echo(
                '''\n[WHITE]You\'re using Box[WHITE] '''
               f'''[RED]#{str(ctx.obj.session['CURRENT_BOX']+1)}[RED]\n'''
            )
            lost_boxes, count = [], 0

            for box_path, basekey in ctx.obj.session['BOX_LIST']:
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
                ctx.obj.session['BOX_LIST'].remove(lbox)

            if lost_boxes:
                if not ctx.obj.session['BOX_LIST']:
                    ctx.obj.session['CURRENT_BOX'] = None
                    echo('No more Boxes, use [WHITE]box-open[WHITE].')
                else:
                    ctx.obj.session['CURRENT_BOX'] = 0
                    echo(
                        '''Switched to the first Box. Set other '''
                        '''with [WHITE]box-switch[WHITE].'''
                    )
            ctx.obj.session.commit()
            echo('')

@cli.command()
@click.option(
    '--start-from-id','-s', default=0,
    help='Will check files that > specified ID'
)
@click.option(
    '--deep','-d', default=False, is_flag=True,
    help='Use a deep Box syncing instead of fast'
)
@click.option(
    '--timeout','-t', default=15,
    help='Sleep timeout per every 1000 file'
)
@click.pass_context
def box_sync(ctx, start_from_id, deep, timeout):
    """Synchronize your current LocalBox with RemoteBox

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
    check_ctx(ctx, dlb=True, drb=True)

    if not deep:
        progress_callback = lambda i,a: echo(f'* [WHITE]ID{i}[WHITE]: [CYAN]{a}[CYAN]')
    else:
        progress_callback = Progress(enlighten_manager,
            'Synchronizing...').update_2

    box_sync_coro = ctx.obj.dlb.sync(
        drb = ctx.obj.drb,
        deep = deep,
        start_from = start_from_id,
        fast_progress_callback = progress_callback,
        deep_progress_callback = progress_callback,
        timeout = timeout
    )
    try:
        tgbox.sync(box_sync_coro)
    except tgbox.errors.RemoteFileNotFound as e:
        echo(f'[RED]{e}[RED]')
    else:
        if deep:
            enlighten_manager.stop()

        echo('[GREEN]Syncing complete.[GREEN]')

@cli.command()
@click.option(
    '--number','-n', required=True, type=int,
    help='Number of connected account. We will take session from it.'
)
@click.pass_context
def box_account_change(ctx, number):
    """Change account of your current Box

    This can be useful if you disconnected your TGBOX in
    Telegram settings (Privacy & Security > Devices) or
    your local TGBOX was too long offline.
    """
    check_ctx(ctx, dlb=True)

    if number < 1 or number > len(ctx.obj.session['ACCOUNT_LIST']):
        echo(
            '''[RED]Invalid account number! See[RED] '''
            '''[WHITE]account-list[WHITE] [RED]command.[RED]''')
    else:
        tg_session = ctx.obj.session['ACCOUNT_LIST'][number-1]

        tc = tgbox.api.TelegramClient(
            session=tg_session,
            api_id=API_ID,
            api_hash=API_HASH
        )
        tgbox.sync(tc.connect())

        basekey = tgbox.keys.BaseKey(
            ctx.obj.session['BOX_LIST'][ctx.obj.session['CURRENT_BOX']][1]
        )
        tgbox.sync(ctx.obj.dlb.replace_session(basekey, tc))
        echo('[GREEN]Session replaced successfully[GREEN]')

@cli.command()
@click.option(
    '--number', '-n', required=True, type=int,
    help='Number of RemoteBox, use box-list-remote command'
)
@click.option(
    '--phrase', '-p', required=True, hide_input=(not TGBOX_CLI_SHOW_PASSWORD),
    help='To request Box you need to specify phrase to it',
    prompt='Phrase to your future cloned Box',
    confirmation_prompt=True
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
        phrase.strip().encode(),
        salt=bytes.fromhex(s),
        n=n, p=p, r=r, dklen=l
    )
    reqkey = tgbox.sync(erb.get_requestkey(basekey))

    echo(
        '''\nSend this Key to the Box owner:\n'''
       f'''    [WHITE]{reqkey.encode()}[WHITE]\n'''
    )

@cli.command()
@click.option(
    '--requestkey', '-r',
    help='Requester\'s RequestKey, by box-request command'
)
@click.pass_context
def box_share(ctx, requestkey):
    """Command to make ShareKey & to share Box"""

    check_ctx(ctx, dlb=True)

    requestkey = requestkey if not requestkey\
        else tgbox.keys.Key.decode(requestkey)

    sharekey = ctx.obj.dlb.get_sharekey(requestkey)

    if not requestkey:
        echo(
            '''\n[RED]You didn\'t specified requestkey.\n   You '''
            '''will receive decryption key IN PLAIN\n[RED]'''
        )
        if not click.confirm('Are you TOTALLY sure?'):
            return
    echo(
        '''\nSend this Key to the Box requester:\n'''
       f'''    [WHITE]{sharekey.encode()}[WHITE]\n'''
    )

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
    '--phrase', '-p', confirmation_prompt=True,
    hide_input=(not TGBOX_CLI_SHOW_PASSWORD),
    prompt='Phrase to your cloned Box',
    help='To clone Box you need to specify phrase to it'
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
@click.pass_context
def box_clone(
        ctx, box_path, box_filename,
        box_number, prefix, key,
        phrase, s, n, p, r, l):
    """
    Clone RemoteBox to LocalBox by your passphrase
    """
    erb = select_remotebox(box_number, prefix)

    try:
        key = tgbox.keys.Key.decode(key)
    except tgbox.errors.IncorrectKey:
        pass

    echo('\n[CYAN]Making BaseKey...[CYAN] ', nl=False)

    basekey = tgbox.keys.make_basekey(
        phrase.strip().encode(),
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

    for _, other_basekey in ctx.obj.session['BOX_LIST']:
        if basekey.key == other_basekey:
            echo('[RED]This Box is already opened[RED]')
            break
    else:
        box_path = str(Path(box_path).absolute())

        ctx.obj.session['BOX_LIST'].append([box_path, basekey.key])
        ctx.obj.session['CURRENT_BOX'] = len(ctx.obj.session['BOX_LIST']) - 1

        ctx.obj.session.commit()
        echo('[GREEN]Successful![GREEN]')

    tgbox.sync(dlb.done())
    tgbox.sync(drb.done())

@cli.command()
@click.argument('defaults',nargs=-1)
@click.pass_context
def box_default(ctx, defaults):
    """Change the TGBOX default values to your own

    \b
    I.e:\b
        # Change METADATA_MAX to the max allowed size
        tgbox-cli box-default METADATA_MAX=1677721
        \b
        # Change download path from DownloadsTGBOX to Downloads
        tgbox-cli box-default DOWNLOAD_PATH=Downloads
    """
    check_ctx(ctx, dlb=True)

    for default in defaults:
        try:
            key, value = default.split('=',1)
            tgbox.sync(ctx.obj.dlb.defaults.change(key, value))
            echo(f'[GREEN]Successfuly changed {key} to {value}[GREEN]')
        except AttributeError:
            echo(f'[RED]Default {key} doesn\'t exist, skipping[RED]')

@cli.command()
@click.option(
    '--bytesize-total', is_flag=True,
    help='Will compute a total size of all uploaded to Box files'
)
@click.pass_context
def box_info(ctx, bytesize_total):
    """Show information about current Box"""

    check_ctx(ctx, dlb=True, drb=True)

    if bytesize_total:
        total_bytes, current_file_count = 0, 0
        total_files = tgbox.sync(ctx.obj.dlb.get_files_total())

        echo('')
        for dlbf in sync_async_gen(ctx.obj.dlb.files()):
            total_bytes += dlbf.size
            current_file_count += 1

            total_formatted = f'[BLUE]{format_bytes(total_bytes)}[BLUE]'

            if current_file_count == total_files:
                current_file = f'[GREEN]{current_file_count}[GREEN]'
            else:
                current_file = f'[YELLOW]{current_file_count}[YELLOW]'

            echo_text = (
                f'''Total [WHITE]Box[WHITE] size is {total_formatted} ['''
                f'''{current_file}/[GREEN]{total_files}[GREEN]]      \r'''
            )
            echo(echo_text, nl=False)

        echo('\n')
    else:
        box_name = tgbox.sync(ctx.obj.drb.get_box_name())
        box_name = f'[WHITE]{box_name}[WHITE]'

        box_id = f'[WHITE]id{ctx.obj.drb.box_channel_id}[WHITE]'

        total_local = tgbox.sync(ctx.obj.dlb.get_files_total())
        total_remote = tgbox.sync(ctx.obj.drb.get_files_total())

        if total_local != total_remote:
            status = f'[RED]Out of sync! ({total_local}L/{total_remote}R)[RED]'
        else:
            status = '[GREEN]Seems synchronized[GREEN]'

        total_local = f'[WHITE]{total_local}[WHITE]'
        total_remote = f'[WHITE]{total_remote}[WHITE]'

        if ctx.obj.drb.box_channel.username:
            public_link = f'[WHITE]@{ctx.obj.drb.box_channel.username}[WHITE]'
        else:
            public_link = '[RED]<Not presented>[RED]'

        if ctx.obj.drb.box_channel.restricted:
            restricted = f'[RED]yes: {ctx.obj.drb.box_channel.restriction_reason}[RED]'
        else:
            restricted = '[WHITE]no[WHITE]'

        box_path = f'[WHITE]{ctx.obj.dlb.tgbox_db.db_path.name}[WHITE]'

        local_box_date = datetime.fromtimestamp(ctx.obj.dlb.box_cr_time).strftime('%d/%m/%Y')
        local_date_created = f'[WHITE]{local_box_date}[WHITE]'

        remote_box_date = tgbox.sync(ctx.obj.drb.tc.get_messages(
            ctx.obj.drb.box_channel, ids=1)
        )
        remote_box_date = remote_box_date.date.strftime('%d/%m/%Y')
        remote_date_created = f'[WHITE]{remote_box_date}[WHITE]'

        rights_interested = {
            'post_messages' : 'Upload files',
            'delete_messages' : 'Remove files',
            'edit_messages' : 'Edit files',
            'invite_users' : 'Invite users',
            'add_admins': 'Add admins'
        }
        if ctx.obj.drb.box_channel.admin_rights:
            rights = ' (+) [GREEN]Fast sync files[GREEN]\n'
        else:
            rights = ' (-) [RED]Fast sync files[RED]\n'

        rights += ' (+) [GREEN]Download files[GREEN]\n'

        for k,v in rights_interested.items():
            if ctx.obj.drb.box_channel.admin_rights and\
                getattr(ctx.obj.drb.box_channel.admin_rights, k):
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
            f'''| Files total: {total_remote}\n'''
            f'''| Is restricted: {restricted}\no\n'''
            f'''| Your rights: \n{rights}\n'''

            ''' ====== Current Box (local) =======\n\n'''

            f'''| Box DB: {box_path}\n'''
            f'''| Date created: {local_date_created}\n'''
            f'''| Files total: {total_local}\n'''

            '''\n :::::::::::::::::::::::::::::::::\n\n'''

            f'''| Status: {status}\n'''

            '''\n =================================\n'''
        )

@cli.command()
@click.pass_context
def box_delete(ctx):
    """Completely remove your Box with all files in it"""

    check_ctx(ctx, dlb=True, drb=True)

    dlb_box_name = Path(ctx.obj.dlb.tgbox_db.db_path).name
    drb_box_name = tgbox.sync(ctx.obj.drb.get_box_name())

    files_total = tgbox.sync(ctx.obj.drb.get_files_total())

    warning_message = (
        '''    [RED]WARNING! You are trying to COMPLETELY REMOVE your\n'''
       f'''    CURRENT SELECTED Box with {files_total} FILES IN IT. After this\n'''
        '''    operation, you WILL NOT BE ABLE to recover or download\n'''
        '''    your files IN ANY WAY. If you wish to remove (for some\n'''
       f'''    strange case) only LocalBox then remove the "{dlb_box_name}"\n'''
        '''    file on your Computer. This command will remove the Local &\n'''
        '''    Remote BOTH. Proceed only if you TOTALLY understand this![RED]'''
    )
    echo('\n' + warning_message)

    echo(f'\n@ Please enter [RED]{drb_box_name}[RED] to destroy your Box or press CTRL+C to abort')
    user_input = click.prompt('\nBox name')

    if user_input == drb_box_name:
        echo('You typed Box name [RED]correctly[RED].\n')

        if click.confirm('The last question: are you sure?'):
            echo('\n[CYAN]Closing you LocalBox...[CYAN] ', nl=False)
            ctx.invoke(box_close, number=ctx.obj.session['CURRENT_BOX']+1)

            echo('[CYAN]Completely removing your LocalBox...[CYAN] ', nl=False)
            tgbox.sync(ctx.obj.dlb.delete())
            echo('[GREEN]Successful![GREEN]')

            echo('[CYAN]Completely removing your RemoteBox...[CYAN] ', nl=False)
            tgbox.sync(ctx.obj.drb.delete())
            echo('[GREEN]Successful![GREEN]')
        else:
            echo('\nYou [RED]didn\'t agreed[RED]. [YELLOW]Aborting[YELLOW].')

    else:
        echo(f'\nYou typed [WHITE]{user_input}[WHITE], which is incorrect. [YELLOW]Aborting.[YELLOW]')

# ========================================================= #

# = Local & Remote BoxFile management commands ============ #

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
@click.pass_context
def file_upload(ctx, path, file_path, cattrs, thumb, max_workers, max_bytes):
    """Upload specified path (file/dir) to the Box"""

    check_ctx(ctx, dlb=True, drb=True)

    current_workers = max_workers
    current_bytes = max_bytes

    def _upload(to_upload: list):
        tgbox.sync(gather(*to_upload))
        to_upload.clear()

    async def _push_wrapper(push_coro, current_path):
        # prepare_file will only check that
        # filesize is < than max allowed,
        # however, user can be without
        # premium, so check on push_file
        # will raise LimitExceeded.
        try:
            await push_coro
        except tgbox.errors.LimitExceeded as e:
            echo(f'[YELLOW]{current_path}: {e} Skipping..[YELLOW]')

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
                    k.strip() : v.strip().encode()
                    for k,v in parsed_cattrs
                }
            except ValueError as e:
                raise ValueError('Invalid cattrs!', e) from None
        else:
            parsed_cattrs = None
        try:
            pf = tgbox.sync(ctx.obj.dlb.prepare_file(
                file = open(current_path,'rb'),
                file_path = remote_path,
                cattrs = parsed_cattrs,
                make_preview = thumb
            ))
        except tgbox.errors.FingerprintExists:
            echo(f'[YELLOW]{current_path} is already uploaded. Skipping..[YELLOW]')
            continue
        except tgbox.errors.LimitExceeded as e:
            echo(f'[YELLOW]{current_path}: {e} Skipping..[YELLOW]')
            continue

        current_bytes -= pf.filesize
        current_workers -= 1

        if not all((current_workers > 0, current_bytes > 0)):
            try:
                _upload(to_upload)
            except tgbox.errors.NotEnoughRights as e:
                echo(f'\n[RED]{e}[RED]')
                enlighten_manager.stop()
                return

            current_workers = max_workers - 1
            current_bytes = max_bytes - pf.filesize

        push = ctx.obj.drb.push_file(pf, Progress(
            enlighten_manager, current_path.name).update)

        to_upload.append(_push_wrapper(push, current_path))

    if to_upload: # If any files left
        try:
            _upload(to_upload)
        except tgbox.errors.NotEnoughRights as e:
            echo(f'\n[RED]{e}[RED]')
            enlighten_manager.stop()

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
@click.option(
    '--non-imported', is_flag=True,
    help='If specified, will search for non-imported files only'
)
@click.pass_context
def file_search(ctx, filters, force_remote, non_interactive, non_imported):
    """List files by selected filters

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
    if force_remote or non_imported:
        check_ctx(ctx, dlb=True, drb=True)
    else:
        check_ctx(ctx, dlb=True)
    try:
        sf = filters_to_searchfilter(filters)
    except IndexError: # Incorrect filters format
        echo('[RED]Incorrect filters! Make sure to use format filter=value[RED]')
    except KeyError as e: # Unknown filters
        echo(f'[RED]Filter "{e.args[0]}" doesn\'t exists[RED]')
    else:
        def bfi_gen(search_file_gen):
            for bfi in sync_async_gen(search_file_gen):
                yield format_dxbf(bfi)

        if non_imported:
            iter_over = ctx.obj.drb.search_file(
                sf, reverse=False,
                cache_preview=False,
                return_imported_as_erbf=True
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

                    req_key = xrbf.get_requestkey(ctx.obj.dlb._mainkey).encode()
                    req_key = f'[WHITE]{req_key}[WHITE]'

                    formatted = (
                       f"""\nFile: {idsalt} {name}\n"""
                       f"""Size, Time: {size}({xrbf.file_size}), {time}\n"""
                       f"""RequestKey: {req_key}"""
                    )
                    echo(formatted)
            echo('')
        else:
            box = ctx.obj.drb if force_remote else ctx.obj.dlb

            if non_interactive:
                for dxbfs in bfi_gen(box.search_file(sf, cache_preview=False)):
                    echo(dxbfs, nl=False)
                echo('')
            else:
                sf_gen = bfi_gen(box.search_file(sf, cache_preview=False))

                colored = True if system().lower() == 'windows' else None
                colored = False if TGBOX_CLI_NOCOLOR else colored
                click.echo_via_pager(sf_gen, color=colored)

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
    help='Download path. ./DownloadsTGBOX by default',
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
@click.pass_context
def file_download(
        ctx, filters, preview, show, locate,
        hide_name, hide_folder, out,
        force_remote, redownload,
        max_workers, max_bytes):
    """Download files by selected filters

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
        check_ctx(ctx, dlb=True)
    else:
        check_ctx(ctx, dlb=True, drb=True)
    try:
        sf = filters_to_searchfilter(filters)
    except IndexError: # Incorrect filters format
        echo('[RED]Incorrect filters! Make sure to use format filter=value[RED]')
    except KeyError as e: # Unknown filters
        echo(f'[RED]Filter "{e.args[0]}" doesn\'t exists[RED]')
    else:
        current_workers = max_workers
        current_bytes = max_bytes

        to_download = ctx.obj.dlb.search_file(sf)
        while True:
            try:
                to_gather_files = []
                while all((current_workers > 0, current_bytes > 0)):
                    dlbf = tgbox.sync(tgbox.tools.anext(to_download))

                    preview_bytes = None

                    if hide_name:
                        file_name = tgbox.tools.prbg(16).hex()
                        file_name += Path(dlbf.file_name).suffix
                    else:
                        file_name = dlbf.file_name

                    file_name = file_name.lstrip('/')
                    file_name = file_name.lstrip('\\')

                    file_name = file_name if not preview else file_name + '.jpg'

                    if not out:
                        downloads = Path(dlbf.defaults.DOWNLOAD_PATH)
                        downloads = downloads / ('Previews' if preview else 'Files')
                    else:
                        downloads = out

                    downloads.mkdir(parents=True, exist_ok=True)

                    file_path = tgbox.tools.make_safe_file_path(dlbf.file_path)

                    outfile = downloads / file_path / file_name
                    outfile.parent.mkdir(exist_ok=True, parents=True)

                    if preview and not force_remote:
                        preview_bytes = dlbf.preview

                    elif preview and force_remote:
                        drbf = tgbox.sync(ctx.obj.drb.get_file(dlbf.id))
                        preview_bytes = drbf.preview

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

                        with open(outfile,'wb') as f:
                            f.write(preview_bytes)

                        if show or locate:
                            click.launch(str(outfile), locate)

                        echo(
                            f'''[WHITE]{file_name}[WHITE] preview downloaded '''
                            f'''to [WHITE]{str(downloads)}[WHITE]''')
                    else:
                        drbf = tgbox.sync(ctx.obj.drb.get_file(dlbf.id))

                        if not drbf:
                            echo(
                                f'''[YELLOW]There is no file with ID={dlbf.id} in '''
                                 '''RemoteBox. Skipping.[YELLOW]''')
                        else:
                            if not redownload and outfile.exists() and\
                                outfile.stat().st_size == dlbf.size:
                                    echo(f'[GREEN]{str(outfile)} downloaded. Skipping...[GREEN]')
                                    continue

                            current_workers -= 1
                            current_bytes -= drbf.file_size

                            outpath = open(outfile, 'wb')

                            p_file_name = '<Filename hidden>' if hide_name\
                                else drbf.file_name

                            download_coroutine = drbf.download(
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
                                    None, lambda: _launch(outpath.name, locate, dlbf.size))
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

@cli.command()
@click.option(
    '--requestkey', '-r',
    help='Requester\'s RequestKey'
)
@click.option(
    '--id', required=True, type=int,
    help='ID of file to share'
)
@click.pass_context
def file_share(ctx, requestkey, id):
    """Use this command to get a ShareKey to your file"""

    check_ctx(ctx, dlb=True)

    dlbf = tgbox.sync(ctx.obj.dlb.get_file(id=id))

    if not dlbf:
        echo(f'[RED]There is no file in LocalBox by ID {id}[RED]')
    else:
        requestkey = requestkey if not requestkey\
            else tgbox.keys.Key.decode(requestkey)

        sharekey = dlbf.get_sharekey(requestkey)

        if not requestkey:
            echo(
                '''\n[RED]You didn\'t specified requestkey.\n   You '''
                '''will receive decryption key IN PLAIN[RED]\n'''
            )
            if not click.confirm('Are you TOTALLY sure?'):
                return
        echo(
            '''\nSend this Key to the Box requester:\n'''
           f'''    [WHITE]{sharekey.encode()}[WHITE]\n'''
        )

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
@click.pass_context
def file_import(ctx, key, id, file_path):
    """Import RemoteBox file to your LocalBox"""

    check_ctx(ctx, dlb=True, drb=True)

    erbf = tgbox.sync(ctx.obj.drb.get_file(
        id, return_imported_as_erbf=True))

    if not erbf:
        echo(f'[RED]There is no file in RemoteBox by ID {id}[RED]')

    elif isinstance(erbf, tgbox.api.remote.DecryptedRemoteBoxFile):
        echo(f'[RED]File ID{id} is already decrypted. Do you mistyped ID?[RED]')
    else:
        try:
            key = tgbox.keys.Key.decode(key)
        except tgbox.errors.IncorrectKey:
            echo(f'[RED]Specified Key is invalid[RED]')
        else:
            if isinstance(key, tgbox.keys.ShareKey):
                key = tgbox.keys.make_importkey(
                    key=ctx.obj.dlb._mainkey,
                    sharekey=key,
                    box_salt=erbf.file_salt
                )
            drbf = tgbox.sync(erbf.decrypt(key))
            tgbox.sync(ctx.obj.dlb.import_file(drbf, file_path))

            echo(format_dxbf(drbf))

@cli.command()
@click.option(
    '--remote','-r', is_flag=True,
    help='If specified, will return ID of last file on RemoteBox'
)
@click.pass_context
def file_last_id(ctx, remote):
    """Return ID of last uploaded to Box file"""

    check_ctx(ctx, dlb=True, drb=remote)

    if remote:
        lfid = tgbox.sync(ctx.obj.drb.get_last_file_id())
    else:
        lfid = tgbox.sync(ctx.obj.dlb.get_last_file_id())

    sbox = 'Remote' if remote else 'Local'
    echo(f'ID of last uploaded to [WHITE]{sbox}Box[WHITE] file is [GREEN]{lfid}[GREEN]')

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
@click.pass_context
def file_remove(ctx, filters, local_only, ask_before_remove):
    """Remove files by selected filters

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
        check_ctx(ctx, dlb=True)
    else:
        check_ctx(ctx, dlb=True, drb=True)
    try:
        sf = filters_to_searchfilter(filters)
    except IndexError: # Incorrect filters format
        echo('[RED]Incorrect filters! Make sure to use format filter=value[RED]')
    except KeyError as e: # Unknown filters
        echo(f'[RED]Filter "{e.args[0]}" doesn\'t exists[RED]')
    else:
        if not filters:
            echo(
                '''\n[RED]You didn\'t specified any search filter.\n   This '''
                '''will [WHITE]REMOVE ALL FILES[WHITE] in your Box[RED]\n'''
            )
            if not click.confirm('Are you TOTALLY sure?'):
                return

        to_remove = ctx.obj.dlb.search_file(sf, cache_preview=False)

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
                            drbf = tgbox.sync(ctx.obj.drb.get_file(dlbf.id))
                            tgbox.sync(drbf.delete())
                        echo('')
                        break
                    elif choice.lower() in ('no','n'):
                        echo('')
                        break
                    elif choice.lower() in ('info','i'):
                        echo(format_dxbf(dlbf).rstrip())
                    elif choice.lower() in ('exit','e'):
                        return
                    else:
                        echo('[RED]Invalid choice, try again[RED]')
        else:
            echo('\n[YELLOW]Searching for LocalBox files[YELLOW]...')
            to_remove = [dlbf for dlbf in sync_async_gen(to_remove)]

            if not to_remove:
                echo('[YELLOW]No files to remove was found.[YELLOW]')
            else:
                echo(f'[WHITE]Removing[WHITE] [RED]{len(to_remove)}[RED] [WHITE]files[WHITE]...')

                delete_files = ctx.obj.dlb.delete_files(
                    *to_remove, rb=(None if local_only else ctx.obj.drb)
                )
                tgbox.sync(delete_files)

                echo('[GREEN]Done.[GREEN]')

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
@click.pass_context
def file_open(ctx, filters, locate, propagate, continuously):
    """
    Search by filters and try to open already
    downloaded file in the default OS app
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
    check_ctx(ctx, dlb=True)

    try:
        sf = filters_to_searchfilter(filters)
    except IndexError: # Incorrect filters format
        echo('[RED]Incorrect filters! Make sure to use format filter=value[RED]')
    except KeyError as e: # Unknown filters
        echo(f'[RED]Filter "{e.args[0]}" doesn\'t exists[RED]')
    else:
        to_open = ctx.obj.dlb.search_file(sf)

        for dlbf in sync_async_gen(to_open):
            outpath = tgbox.defaults.DOWNLOAD_PATH / 'Files'
            file_path = tgbox.tools.make_safe_file_path(dlbf.file_path)

            outpath = (outpath / file_path).absolute()
            outpath = str(outpath / dlbf.file_name)

            click.launch(outpath, locate=locate)

            if not propagate:
                return

            if propagate and not continuously:
                click.prompt(
                    text = '\n@ Press ENTER to open the next file >> ',
                    hide_input = (not TGBOX_CLI_SHOW_PASSWORD),
                    prompt_suffix = ''
                )

@cli.command()
@click.argument('filters', nargs=-1)
@click.option(
    '--entity', '-e', required=True,
    help='Entity to send file to'
)
@click.pass_context
def file_forward(ctx, filters, entity):
    """
    Forward files by filters to specified entity

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
    check_ctx(ctx, dlb=True, drb=True, account=True)

    try:
        sf = filters_to_searchfilter(filters)
    except IndexError: # Incorrect filters format
        echo('[RED]Incorrect filters! Make sure to use format filter=value[RED]')
    except KeyError as e: # Unknown filters
        echo(f'[RED]Filter "{e.args[0]}" doesn\'t exists[RED]')
    else:
        to_forward = ctx.obj.dlb.search_file(sf)

        for dlbf in sync_async_gen(to_forward):
            drbf = tgbox.sync(ctx.obj.drb.get_file(dlbf.id))
            try:
                tgbox.sync(ctx.obj.account.forward_messages(entity, drbf.message))
                echo(f'[GREEN]ID{drbf.id}: {drbf.file_name}: was forwarded to {entity}[GREEN]')
            except (UsernameNotOccupiedError, UsernameInvalidError, ValueError):
                echo(f'[YELLOW]Can not find entity "{entity}"[YELLOW]')

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
@click.pass_context
def file_attr_edit(ctx, filters, attribute, local_only):
    """Change attribute value of Box files (search by filters)

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
        tgbox-cli file-attr-edit min_id=3 max_id=100 -a file_path=/home/non/
        \b
        # Include flag (will ignore unmatched)
        tgbox-cli file-attr-edit +i file_name=.png -a file_path=/home/non/Pictures
        \b
        # Exclude flag (will ignore matched)
        tgbox-cli file-attr-edit +e file_name=.png -a file_path=/home/non/NonPictures
        \b
        # Attribute without value will reset it to default
        tgbox-cli file-attr-edit id=22 -a file_name=
        \b
        You can use both, the ++include and
        ++exclude (+i, +e) in one command.
    """
    check_ctx(ctx, dlb=True, drb=True)

    try:
        sf = filters_to_searchfilter(filters)
    except IndexError: # Incorrect filters format
        echo('[RED]Incorrect filters! Make sure to use format filter=value[RED]')
    except KeyError as e: # Unknown filters
        echo(f'[RED]Filter "{e.args[0]}" doesn\'t exists[RED]')
    else:
        if not filters:
            echo(
                '''\n[RED]You didn\'t specified any search filter.\n   This '''
                '''will [WHITE]change attrs for all files[WHITE] in your Box[RED]\n'''
            )
            if not click.confirm('Are you TOTALLY sure?'):
                return

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

        to_change = ctx.obj.dlb.search_file(sf, cache_preview=False)

        dxbf_to_update = []

        UPDATE_WHEN = 200 if not local_only else 100
        TIMEOUT = 15 if not local_only else 0

        for dlbf in sync_async_gen(to_change):
            if local_only:
                dxbf_to_update.append(dlbf.update_metadata(
                    changes=changes, dlb=ctx.obj.dlb))
            else:
                async def _update_drbf(dlbf_id):
                    drbf = await ctx.obj.drb.get_file(dlbf_id)
                    await drbf.update_metadata(changes=changes, dlb=ctx.obj.dlb)

                dxbf_to_update.append(_update_drbf(dlbf.id))

            if len(dxbf_to_update) == UPDATE_WHEN:
                tgbox.sync(gather(*dxbf_to_update))
                dxbf_to_update.clear()
                sleep(TIMEOUT)

            echo(
                f'''([WHITE]{dlbf.id}[WHITE]) {dlbf.file_name} '''
                f'''<= [YELLOW]{attribute}[YELLOW]''')

        if dxbf_to_update:
            tgbox.sync(gather(*dxbf_to_update))
            dxbf_to_update.clear()

# ========================================================= #

# = LocalBox directory management commands ================ #

@cli.command()
@click.pass_context
def dir_list(ctx):
    """List all directories in LocalBox"""

    check_ctx(ctx, dlb=True)

    dirs = ctx.obj.dlb.contents(ignore_files=True)

    for dir in sync_async_gen(dirs):
        tgbox.sync(dir.lload(full=True))
        echo(str(dir))

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
def logfile_wipe():
    """Clear TGBOX-CLI log file"""
    open(logfile,'w').close()
    echo('[GREEN]Done.[GREEN]')

@cli.command()
def logfile_size():
    """Return size of TGBOX-CLI log file"""
    size = format_bytes(logfile.stat().st_size)
    echo(f'[WHITE]{str(logfile)}[WHITE]: {size}')

@cli.command()
@click.argument('entity', nargs=-1)
@click.pass_context
def logfile_send(ctx, entity):
    """
    Send logfile to the specified entity

    \b
    Example:\b
        tgbox-cli logfile-send @username
    """
    check_ctx(ctx, account=True)

    for e in entity:
        tgbox.sync(ctx.obj.account.send_file(e, logfile))
        echo(f'[WHITE]Logfile has been sent to[WHITE] [BLUE]{e}[BLUE]')

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
@click.option(
    '--enable-logging', is_flag=True,
    help='Will enable logging for Python session'
)
@click.option(
    '--execute', help='Path to Python script to execute'
)
@click.option(
    '--non-interactive', is_flag=True,
    help='Will disable interactive console'
)
@click.pass_context
def python(ctx, enable_logging, execute, non_interactive):
    """Launch interactive Python console"""

    global Objects
    Objects = ctx.obj

    if not enable_logging:
        logging.disable()

    global EXEC_SCRIPT

    if execute:
        EXEC_SCRIPT = lambda: exec(open(execute).read())
    else:
        EXEC_SCRIPT = lambda: None

    if execute:
        echo(
            '''\n    [RED]You are specified some Python script with the --execute option.\n'''
            '''    Third-party scripts can be useful for some actions that out of\n'''
            '''    TGBOX-CLI abilities, however, they can do MANY BAD THINGS to your\n'''
            '''    Telegram account [i.e STEAL IT] (or even to your System [i.e \n'''
            '''    REMOVE ALL FILES]) if written by ATTACKER. NEVER execute scripts\n'''
            '''    you DON\'T UNDERSTAND or DON\'T TRUST. NEVER! NEVER! NEVER![RED]\n'''
        )
        confirm = None
        while confirm != 'YES':
            prompt = (
                '''Type [GREEN]YES[GREEN] [or [RED]NO[RED]'''
                '''] if you understand this and want to proceed'''
            )
            confirm = click.prompt(color(prompt))
            if confirm in ('NO', 'no', 'n'):
                return

    if non_interactive:
        EXEC_SCRIPT()
    else:
        interactive_console(local=globals())

# ========================================================= #

def safe_tgbox_cli_startup():
    try:
        cli(standalone_mode=False)
    except Exception as e:
        if isinstance(e, (click.Abort, CheckCTXFailed)):
            exit(0)

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

        echo(''); exit(1)

if __name__ == '__main__':
    safe_tgbox_cli_startup()
