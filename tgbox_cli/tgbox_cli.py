#!/usr/bin/env python3

import click

from os import getenv
from pathlib import Path
from functools import wraps

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
    from datetime import datetime

    from os.path import getsize
    from platform import system

    from base64 import urlsafe_b64encode
    from shutil import get_terminal_size
    from traceback import format_exception
    from inspect import isfunction, iscoroutine

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

# = Decorator/Func to check that CTX has requested fields = #

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

def ctx_require(**check_ctx_kwargs):
    """
    This decorator will check that CTX.obj has
    requested fields or will raise CheckCTXFailed
    if not. This will also pass the CTX to func,
    so we don't need to add '@click.pass_context'

    Also see 'check_ctx' function.
    """
    def check_ctx_decorator(func):
        @wraps(func)
        def check(*args, **kwargs):
            ctx = click.get_current_context()
            check_ctx(ctx, **check_ctx_kwargs)

            return func(ctx, *args, **kwargs)

        return check

    return check_ctx_decorator

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

            self._enlighten_manager = None

        def __repr__(self):
            return f'Objects: {self.__dict__=}'

        @property
        def drb(self):
            if iscoroutine(self._drb): # self._drb can be coroutine
                self._drb = tgbox.sync(self._drb)

            return self._drb

        @property
        def account(self):
            if isfunction(self._account): # self._account can be lambda
                self.drb # Make sure DRB is initialized
                self._account = self._account()

            if self._account and not self._account.is_connected():
                tgbox.sync(self._account.connect())

            return self._account

        @property
        def enlighten_manager(self):
            if isfunction(self._enlighten_manager):
                self._enlighten_manager = self._enlighten_manager()

            return self._enlighten_manager

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
    # = Setting ProgressBar manager =========================== #

    # The Enlighten progressbar manager
    ctx.obj._enlighten_manager = get_enlighten_manager

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

        if not isfunction(ctx_.obj._enlighten_manager):
            ctx_.obj._enlighten_manager.stop()

            # TODO: There is some problems with enlighten Progressbar
            #       and bash after a037bee commit that I don't really
            #       understand. enlighten_manager should flush and fix
            #       Terminal after .stop() was called, however, in some
            #       strange cases it leave a CMD in a broken state. As
            #       I currently tried almost everything and don't know
            #       how to fix this, we will force to call a "tset"
            #       bash command, which will return CMD in a normal
            #       state. You can disable this with any value on
            #       the $TGBOX_CLI_NO_TSET, like "1" or "anything".
            if not getenv('TGBOX_CLI_NO_TSET'):
                current_shell = getenv('SHELL')
                if current_shell and 'bash' in current_shell:
                    os_system('tset') # from tools module

    # This will close Local & Remote on exit
    ctx.call_on_close(lambda: on_exit(ctx))

# ========================================================= #
# = Function to search for more RemoteBox on account ====== #

@ctx_require(account=True)
def select_remotebox(ctx, number: int, prefix: str):

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
            init_commands = (
                '''(for /f %i in (\'tgbox-cli sk-gen\') '''
                '''do set "TGBOX_CLI_SK=%i") > NUL\n'''
                '''chcp 65001 || # Change the default CMD encoding to UTF-8'''
            )
        else:
            current_shell = getenv('SHELL')

            if current_shell and 'bash' in current_shell:
                autocomplete = '\neval "$(_TGBOX_CLI_COMPLETE=bash_source tgbox-cli)"'

            elif current_shell and 'zsh' in current_shell:
                autocomplete = '\neval "$(_TGBOX_CLI_COMPLETE=zsh_source tgbox-cli)"'

            elif current_shell and 'fish' in current_shell:
                autocomplete = '\neval (env _TGBOX_CLI_COMPLETE=fish_source tgbox-cli)'
            else:
                autocomplete = ''

                if 'fish' in current_shell:
                    eval_commands = (
                        f'''export TGBOX_CLI_SK=(tgbox-cli sk-gen)\n'''
                        f'''{autocomplete}''')

            if 'fish' not in current_shell:
                echo('\n# [BLUE](Execute commands below if eval doesn\'t work)[BLUE]\n')
                eval_commands = (
                    f'''export TGBOX_CLI_SK="$(tgbox-cli sk-gen)"'''
                    f'''{autocomplete}'''
                )
                echo(eval_commands)

                init_commands = 'eval "$(!!)" || true && clear'
            else:
                init_commands = (
                    f'''export TGBOX_CLI_SK=(tgbox-cli sk-gen)'''
                    f'''{autocomplete}'''
                )
        echo(
            '''\n[YELLOW]Welcome to the TGBOX-CLI![YELLOW]\n\n'''
            '''Copy & Paste commands below to your shell:\n\n'''
           f'''[WHITE]{init_commands}[WHITE]\n'''
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
@ctx_require(session=True)
def account_connect(ctx, phone):
    """Connect your Telegram account"""

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
@ctx_require(session=True)
def account_disconnect(ctx, number, log_out):
    """Disconnect Account from Session"""

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
@ctx_require(session=True)
def account_list(ctx):
    """List all connected accounts"""

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
@ctx_require(session=True)
def account_switch(ctx, number):
    """Set as main your another connected Account"""

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
@ctx_require(account=True)
def account_info(ctx, show_phone):
    """Show information about current account"""

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
    '--box-path', '-p', help='Path to store LocalBox DB file',
    type=click.Path(writable=True, readable=True, path_type=Path)
)
@click.option(
    '--box-name', '-b', prompt=True,
    help='Name of your future Box',
)
@click.option(
    '--box-salt', help='BoxSalt as hexadecimal'
)
@click.option(
    '--phrase', help='Passphrase to your Box. Keep it secret'
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
@ctx_require(account=True)
def box_make(ctx, box_path, box_name, box_salt, phrase, s, n, p, r, l):
    """Create the new Box (Remote & Local)"""

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

    if box_salt:
        box_salt = tgbox.crypto.BoxSalt(bytes.fromhex(box_salt))

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
    dlb = tgbox.sync(tgbox.api.make_localbox(
        erb, basekey, box_path=box_path, box_name=box_name))
    echo('[GREEN]Successful![GREEN]')

    echo('[CYAN]Updating local data...[CYAN] ', nl=False)

    localbox_path = str(Path(dlb.tgbox_db.db_path).resolve())

    ctx.obj.session['BOX_LIST'].append([localbox_path, basekey.key])
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
@ctx_require(session=True)
def box_open(ctx, box_path, phrase, s, n, p, r, l):
    """Decrypt & connect existing LocalBox"""

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
    except tgbox.errors.AESError:
        echo('[RED]Incorrect passphrase![RED]')
    else:
        echo('[GREEN]Successful![GREEN]')
        echo('[CYAN]Updating local data...[CYAN] ', nl=False)

        localbox_path = str(Path(dlb.tgbox_db.db_path).resolve())
        box_data = [localbox_path, basekey.key]

        for other_box_data in ctx.obj.session['BOX_LIST']:
            if other_box_data == box_data:
                echo('[RED]This Box is already opened[RED]')
                break
        else:
            ctx.obj.session['BOX_LIST'].append(box_data)
            ctx.obj.session['CURRENT_BOX'] = len(ctx.obj.session['BOX_LIST']) - 1

            ctx.obj.session.commit()
            echo('[GREEN]Successful![GREEN]')

        tgbox.sync(dlb.done())

@cli.command()
@click.option(
    '--number', '-n', required=True, type=int,
    help='Number of other connected box, use box-list command'
)
@ctx_require(dlb=True)
def box_close(ctx, number):
    """Disconnect selected LocalBox from Session"""

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
@ctx_require(dlb=True)
def box_switch(ctx, number):
    """Set as main your another connected Box"""

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
                erb_salt = urlsafe_b64encode(erb_salt.salt).decode()

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
                    name = Path(box_path).name

                    dlb = tgbox.sync(tgbox.api.get_localbox(
                        tgbox.keys.BaseKey(basekey), box_path)
                    )
                    salt = urlsafe_b64encode(dlb.box_salt.salt).decode()

                    echo(
                        f'''[WHITE]{count+1})[WHITE] [BLUE]{name}[BLUE]'''
                        f'''@[BRIGHT_BLACK]{salt}[BRIGHT_BLACK]'''
                    )
                    tgbox.sync(dlb.done())
                except FileNotFoundError:
                    echo(
                       f'''[WHITE]{count+1})[WHITE] [RED]{name} LocalBox '''
                        '''file was moved, so disconnected.[RED]'''
                    )
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
@ctx_require(dlb=True, drb=True)
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

    (!) --start-from-id can be used only with --deep sync.
    """
    if start_from_id and not deep:
        echo(
            '''[WHITE]--start-from-id[WHITE] [RED]can be used only '''
            '''with[RED] [WHITE]--deep[WHITE][RED]![RED]'''
        ); return

    if not deep:
        progress_callback = lambda i,a: echo(f'* [WHITE]ID{i}[WHITE]: [CYAN]{a}[CYAN]')
    else:
        progress_callback = Progress(ctx.obj.enlighten_manager,
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
        echo('[GREEN]Syncing complete.[GREEN]')

@cli.command()
@click.option(
    '--number','-n', required=True, type=int,
    help='Number of connected account. We will take session from it.'
)
@ctx_require(dlb=True)
def box_account_change(ctx, number):
    """Change account of your current Box

    This can be useful if you disconnected your TGBOX in
    Telegram settings (Privacy & Security > Devices) or
    your local TGBOX was too long offline.
    """

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
@ctx_require(dlb=True)
def box_share(ctx, requestkey):
    """Command to make ShareKey & to share Box"""

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
    '--box-path', '-p', help='Path to which we will clone',
    type=click.Path(writable=True, readable=True, path_type=Path)
)
@click.option(
    '--box-name', '-b',
    help='Filename to your future cloned LocalBox DB',
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
    '--phrase', required=True,
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
        ctx, box_path, box_name,
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
            salt=tgbox.sync(erb.get_box_salt())
        )
    drb = tgbox.sync(erb.decrypt(key=key))

    dlb = tgbox.sync(tgbox.api.local.clone_remotebox(
        drb = drb,
        basekey = basekey,
        box_name = box_name,
        box_path = box_path,
        progress_callback = Progress(
            ctx.obj.enlighten_manager, 'Cloning...').update_2
        )
    )
    echo('\n[CYAN]Updating local data...[CYAN] ', nl=False)

    localbox_path = str(Path(dlb.tgbox_db.db_path).resolve())
    box_data = [localbox_path, basekey.key]

    for other_box_data in ctx.obj.session['BOX_LIST']:
        if other_box_data == box_data:
            echo('[RED]This Box is already opened[RED]')
            break
    else:
        ctx.obj.session['BOX_LIST'].append(box_data)
        ctx.obj.session['CURRENT_BOX'] = len(ctx.obj.session['BOX_LIST']) - 1

        ctx.obj.session.commit()
        echo('[GREEN]Successful![GREEN]')

    tgbox.sync(dlb.done())
    tgbox.sync(drb.done())

@cli.command()
@click.argument('defaults',nargs=-1)
@ctx_require(dlb=True)
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
    for default in defaults:
        try:
            key, value = default.split('=',1)
            tgbox.sync(ctx.obj.dlb.defaults.change(key, value))
            echo(f'[GREEN]Successfully changed {key} to {value}[GREEN]')
        except AttributeError:
            echo(f'[RED]Default {key} doesn\'t exist, skipping[RED]')

@cli.command()
@click.option(
    '--bytesize-total', is_flag=True,
    help='Will compute a total size of all uploaded to Box files'
)
@ctx_require(dlb=True, drb=True)
def box_info(ctx, bytesize_total):
    """Show information about current Box"""

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
@ctx_require(dlb=True, drb=True)
def box_delete(ctx):
    """Completely remove your Box with all files in it"""

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

    echo(
       f'''\n@ Please enter [YELLOW]{drb_box_name}[YELLOW] to '''
        '''[RED]DESTROY[RED] your Box or press [BLUE]CTRL+C[BLUE] to abort'''
    )
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
    '--no-update', is_flag=True,
    help='If specified, will NOT re-upload file if it was changed (in size)'
)
@click.option(
    '--force-update', is_flag=True,
    help='If specified, will force to re-upload every target file'
)
@click.option(
    '--use-slow-upload', is_flag=True,
    help='If specified, will use slow, non-parallel upload'
)
@click.option(
    '--no-thumb', is_flag=True,
    help='If specified, will not add thumbnail'
)
@click.option(
    '--max-workers', default=10, type=click.IntRange(1,50),
    help='Max amount of files uploaded at the same time, default=10',
)
@click.option(
    '--max-bytes', default=200000000,
    type=click.IntRange(1000000, 1000000000),
    help='Max amount of bytes uploaded at the same time, default=200000000',
)
@ctx_require(dlb=True, drb=True)
def file_upload(
        ctx, path, file_path, cattrs, no_update,
        force_update, use_slow_upload, no_thumb,
        max_workers, max_bytes):
    """
    Upload specified path (file/dir) to the Box

    If file was already uploaded but changed (in size)
    and --no-update is NOT specified, -- will re-upload.
    """
    current_workers = max_workers
    current_bytes = max_bytes

    def _upload(to_upload: list):
        tgbox.sync(gather(*to_upload))
        to_upload.clear()

    async def _push_wrapper(file, file_path, cattrs):
        fingerprint = tgbox.tools.make_file_fingerprint(
            mainkey = ctx.obj.dlb.mainkey,
            file_path = str(file_path)
        )
        # Standard file upload if dlbf is not exists (from scratch)
        if not (dlbf := await ctx.obj.dlb.get_file(fingerprint=fingerprint)) and not force_update:
            file_action = (ctx.obj.drb.push_file, {})

        # File re-uploading (or updating) if file size differ
        elif force_update or not no_update and dlbf and dlbf.size != getsize(file):
            if not dlbf: # Wasn't uploaded before
                file_action = (ctx.obj.drb.push_file, {})
            else:
                drbf = await ctx.obj.drb.get_file(dlbf.id)
                file_action = (ctx.obj.drb.update_file, {'rbf': drbf})
        else:
            # Ignore upload if file exists and wasn't changed
            echo(f'[YELLOW]{file} is already uploaded. Skipping...[YELLOW]')
            return
        try:
            pf = await ctx.obj.dlb.prepare_file(
                file = open(file,'rb'),
                file_path = file_path,
                cattrs = cattrs,
                make_preview = (not no_thumb),
                skip_fingerprint_check = True
            )
        except tgbox.errors.LimitExceeded as e:
            echo(f'[YELLOW]{file}: {e} Skipping...[YELLOW]')
            return

        except PermissionError:
            echo(f'[RED]{file} is not readable! Skipping...[RED]')
            return

        progressbar = Progress(ctx.obj.enlighten_manager, file.name)

        file_action[1]['pf'] = pf
        file_action[1]['progress_callback'] = progressbar.update
        file_action[1]['use_slow_upload'] = use_slow_upload

        await file_action[0](**file_action[1])

    if path.is_dir():
        iter_over = path.rglob('*')
    else:
        iter_over = (path,)

    to_upload = []
    for current_path in iter_over:

        if current_path.is_dir():
            continue

        if not file_path:
            remote_path = current_path.resolve()
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

        current_bytes -= getsize(current_path)
        current_workers -= 1

        if not all((current_workers > 0, current_bytes > 0)):
            try:
                _upload(to_upload)
            except tgbox.errors.NotEnoughRights as e:
                echo(f'\n[RED]{e}[RED]')
                return

            current_workers = max_workers - 1
            current_bytes = max_bytes - getsize(current_path)

        pw = _push_wrapper(
            file = current_path,
            file_path = remote_path,
            cattrs = parsed_cattrs
        )
        to_upload.append(pw)

    if to_upload: # If any files left
        try:
            _upload(to_upload)
        except tgbox.errors.NotEnoughRights as e:
            echo(f'\n[RED]{e}[RED]')

@cli.command()
@click.argument('filters',nargs=-1)
@click.option(
    '--force-remote','-r', is_flag=True,
    help='If specified, will fetch files from RemoteBox'
)
@click.option(
    '--upend', '-u', is_flag=True,
    help='If specified, will search in reverse order'
)
@click.option(
    '--non-interactive', is_flag=True,
    help='If specified, will echo to shell instead of pager'
)
@click.option(
    '--non-imported', is_flag=True,
    help='If specified, will search for non-imported files only'
)
@click.option(
    '--bytesize-total', is_flag=True,
    help='If specified, will calc a total size of filtered files'
)
@click.pass_context
def file_search(
        ctx, filters, force_remote, non_interactive,
        non_imported, upend, bytesize_total):
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
        min_size integer/str: File Size should be > min_size
        max_size integer/str: File Size should be < max_size
        +
        min_size & max_size can be also specified as string,
            i.e "1GB" (one gigabyte), "122.45KB" or "700B"
        \b
        min_time integer/float/str: Upload Time should be > min_time
        max_time integer/float/str: Upload Time should be < max_time
        +
        min_time & max_time can be also specified as string,
            i.e "22/02/22, 22:22:22" or "22/02/22"
               ("%d/%m/%y, %H:%M:%S" or "%d/%m/%y")
        \b
        imported bool: Yield only imported files
        re       bool: Regex search for every str filter
        \b
        non_recursive_scope bool: Ignore scope subdirectories
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

        box = ctx.obj.drb if force_remote else ctx.obj.dlb

        if non_imported:
            iter_over = ctx.obj.drb.search_file(
                sf=sf, reverse=True,
                cache_preview=False,
                return_imported_as_erbf=True
            )
            echo('[YELLOW]\nSearching, press CTRL+C to stop...[YELLOW]')

            for xrbf in sync_async_gen(iter_over):
                if type(xrbf) is tgbox.api.EncryptedRemoteBoxFile:
                    time = datetime.fromtimestamp(xrbf.upload_time)
                    time = f"[CYAN]{time.strftime('%d/%m/%y, %H:%M:%S')}[CYAN]"

                    salt = urlsafe_b64encode(xrbf.file_salt.salt).decode()
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

        elif bytesize_total:
            total_bytes, current_file_count = 0, 0

            echo('')
            for dlbf in sync_async_gen(box.search_file(sf, cache_preview=False)):
                total_bytes += dlbf.size
                current_file_count += 1

                total_formatted = f'[BLUE]{format_bytes(total_bytes)}[BLUE]'
                current_file = f'[YELLOW]{current_file_count}[YELLOW]'

                echo_text = (
                    f'''Total [WHITE]files found ({current_file})[WHITE] '''
                    f'''size is {total_formatted}    \r'''
                )
                echo(echo_text, nl=False)

            echo('\n')
        else:
            sgen = box.search_file(
                sf=sf, reverse=upend,
                cache_preview=True
            )
            sgen = bfi_gen(sgen)

            if non_interactive:
                for dxbfs in sgen:
                    echo(dxbfs, nl=False)
                echo('')
            else:
                colored = False if TGBOX_CLI_NOCOLOR else None

                if getenv('TGBOX_CLI_FORCE_PAGER_COLOR'):
                    colored = True

                click.echo_via_pager(sgen, color=colored)

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
    '--use-slow-download', is_flag=True,
    help='If specified, will use slow, non-parallel download'
)
@click.option(
    '--offset', default=0,
    help='Download decrypted file from specified offset'
)
@click.option(
    '--max-workers', default=10, type=click.IntRange(1,50),
    help='Max amount of files downloaded at the same time, default=10',
)
@click.option(
    '--max-bytes', default=200000000,
    type=click.IntRange(1000000, 1000000000),
    help='Max amount of bytes downloaded at the same time, default=200000000',
)
@click.pass_context
def file_download(
        ctx, filters, preview, show, locate,
        hide_name, hide_folder, out, force_remote,
        redownload, use_slow_download, offset,
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
        min_size integer/str: File Size should be > min_size
        max_size integer/str: File Size should be < max_size
        +
        min_size & max_size can be also specified as string,
            i.e "1GB" (one gigabyte), "122.45KB" or "700B"
        \b
        min_time integer/float/str: Upload Time should be > min_time
        max_time integer/float/str: Upload Time should be < max_time
        +
        min_time & max_time can be also specified as string,
            i.e "22/02/22, 22:22:22" or "22/02/22"
               ("%d/%m/%y, %H:%M:%S" or "%d/%m/%y")
        \b
        imported bool: Yield only imported files
        re       bool: Regex search for every str filter
        \b
        non_recursive_scope bool: Ignore scope subdirectories
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

        box = ctx.obj.drb if force_remote else ctx.obj.dlb
        to_download = box.search_file(sf)

        while True:
            try:
                to_gather_files = []
                while all((current_workers > 0, current_bytes > 0)):
                    dxbf = tgbox.sync(tgbox.tools.anext(to_download))

                    if hide_name:
                        file_name = tgbox.tools.prbg(16).hex()
                        file_name += Path(dxbf.file_name).suffix
                    else:
                        file_name = dxbf.file_name

                    file_name = file_name.lstrip('/')
                    file_name = file_name.lstrip('\\')

                    file_name = file_name if not preview else file_name + '.jpg'

                    if not out:
                        downloads = Path(dxbf.defaults.DOWNLOAD_PATH)
                        downloads = downloads / ('Previews' if preview else 'Files')
                    else:
                        downloads = out

                    downloads.mkdir(parents=True, exist_ok=True)

                    file_path = tgbox.tools.make_safe_file_path(dxbf.file_path)

                    outfile = downloads / file_path / file_name
                    outfile.parent.mkdir(exist_ok=True, parents=True)

                    preview_bytes = dxbf.preview if preview else None

                    if preview_bytes is not None:
                        if preview_bytes == b'':
                            # Drop the '.jpg' preview suffix string
                            file_name = '.'.join(file_name.split('.')[:-1])

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
                        if not force_remote: # box is DecryptedLocalBox
                            dxbf = tgbox.sync(ctx.obj.drb.get_file(dxbf.id))

                        if not dxbf:
                            echo(
                                f'''[YELLOW]There is no file with ID={dxbf.id} in '''
                                 '''RemoteBox. Skipping.[YELLOW]'''
                            )
                            continue

                        write_mode = 'wb'
                        outfile_size = outfile.stat().st_size if outfile.exists() else 0

                        if not redownload and outfile.exists():
                            if outfile_size == dxbf.size:
                                echo(f'[GREEN]{str(outfile)} downloaded. Skipping...[GREEN]')
                                continue
                            else:
                                if offset:
                                    echo(
                                       f'''[YELLOW]{str(outfile)} is partially downloaded and '''
                                        '''you specified offset. This will corrupt file. Drop the '''
                                        '''offset or remove file from your computer. Skipping...[YELLOW]'''
                                    )
                                    continue

                                if outfile_size % 524288: # Remove partially downloaded block
                                    with open(outfile, 'ab') as f:
                                        f.truncate(outfile_size - (outfile_size % 524288))

                                # File is partially downloaded, so we need to fetch left bytes
                                offset, write_mode = outfile.stat().st_size, 'ab'

                        if offset % 4096 or offset % 524288:
                            echo('[RED]Offset must be divisible by 4096 and by 524288.[RED]')
                            continue

                        current_workers -= 1
                        current_bytes -= dxbf.file_size

                        outpath = open(outfile, write_mode)

                        p_file_name = '<Filename hidden>' if hide_name\
                            else dxbf.file_name

                        blocks_downloaded = 0 if not offset else offset // 524288

                        download_coroutine = dxbf.download(
                            outfile = outpath,
                            progress_callback = Progress(
                                ctx.obj.enlighten_manager,
                                p_file_name, blocks_downloaded).update,

                            hide_folder = hide_folder,
                            hide_name = hide_name,
                            offset = offset,
                            use_slow_download = use_slow_download
                        )
                        to_gather_files.append(download_coroutine)

                        if show or locate:
                            def _launch(path: str, locate: bool, size: int) -> None:
                                while (Path(path).stat().st_size+1) / size * 100 < 5:
                                    sleep(1)
                                click.launch(path, locate=locate)

                            loop = get_event_loop()

                            to_gather_files.append(loop.run_in_executor(
                                None, lambda: _launch(outpath.name, locate, dxbf.size))
                            )
                if to_gather_files:
                    tgbox.sync(gather(*to_gather_files))

                current_workers = max_workers
                current_bytes = max_bytes

            except StopAsyncIteration:
                break

        if to_gather_files: # If any files left
            tgbox.sync(gather(*to_gather_files))

@cli.command()
@click.option(
    '--requestkey', '-r',
    help='Requester\'s RequestKey'
)
@click.option(
    '--id', required=True, type=int,
    help='ID of file to share'
)
@click.option(
    '--directory', '-d', required=True, prompt=True,
    help='Absolute path of Directory to share'
)
@ctx_require(dlb=True)
def file_share(ctx, requestkey, id):
    """Get a ShareKey from RequestKey to share file"""

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
    '--propagate', '-p', is_flag=True,
    help='If specified, will open ALL matched files'
)
@click.option(
    '--file-path', '-f', type=Path,
    help='Imported file\'s path.'
)
@ctx_require(dlb=True, drb=True)
def file_import(ctx, key, id, propagate, file_path):
    """Import RemoteBox file to your LocalBox

    Use --propagate option to auto import a
    bunch of files (if you have a ShareKey of
    a DirectoryKey).
    """
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
            return

        if isinstance(key, tgbox.keys.ShareKey):
            key = tgbox.keys.make_importkey(
                key=ctx.obj.dlb._mainkey,
                sharekey=key,
                salt=erbf.file_salt
            )

        async def _import_wrap(erbf):
            try:
                drbf = await erbf.decrypt(key)
            except tgbox.errors.AESError:
                return # Probably not a file of Directory

            await ctx.obj.dlb.import_file(drbf, file_path)
            echo(format_dxbf(drbf), nl=False)

        echo('\n[YELLOW]Searching for files to import[YELLOW]...')

        # Import first found EncryptedRemoteBoxFile
        tgbox.sync(_import_wrap(erbf))

        if propagate:
            IMPORT_STACK, IMPORT_WHEN = [], 100

            iter_over = ctx.obj.drb.files(
                offset_id=erbf.id, reverse=True,
                return_imported_as_erbf=True
            )
            for erbf in sync_async_gen(iter_over):
                if len(IMPORT_STACK) == IMPORT_WHEN:
                    tgbox.sync(gather(*IMPORT_STACK))
                    IMPORT_STACK.clear()

                if type(erbf) is tgbox.api.DecryptedRemoteBoxFile:
                    break # All files from shared Dir was imported

                IMPORT_STACK.append(_import_wrap(erbf))

            if IMPORT_STACK: # If any files left
                tgbox.sync(gather(*IMPORT_STACK))
            echo('')

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
        echo(f'ID of last uploaded to [WHITE]RemoteBox[WHITE] file is [YELLOW]{lfid}[YELLOW]')
    else:
        lfid = tgbox.sync(ctx.obj.dlb.get_last_file_id())
        echo(f'ID of last saved to [WHITE]LocalBox[WHITE] file is [YELLOW]{lfid}[YELLOW]')


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
        min_size integer/str: File Size should be > min_size
        max_size integer/str: File Size should be < max_size
        +
        min_size & max_size can be also specified as string,
            i.e "1GB" (one gigabyte), "122.45KB" or "700B"
        \b
        min_time integer/float/str: Upload Time should be > min_time
        max_time integer/float/str: Upload Time should be < max_time
        +
        min_time & max_time can be also specified as string,
            i.e "22/02/22, 22:22:22" or "22/02/22"
               ("%d/%m/%y, %H:%M:%S" or "%d/%m/%y")
        \b
        imported bool: Yield only imported files
        re       bool: Regex search for every str filter
        \b
        non_recursive_scope bool: Ignore scope subdirectories
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
@ctx_require(dlb=True)
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
        min_size integer/str: File Size should be > min_size
        max_size integer/str: File Size should be < max_size
        +
        min_size & max_size can be also specified as string,
            i.e "1GB" (one gigabyte), "122.45KB" or "700B"
        \b
        min_time integer/float/str: Upload Time should be > min_time
        max_time integer/float/str: Upload Time should be < max_time
        +
        min_time & max_time can be also specified as string,
            i.e "22/02/22, 22:22:22" or "22/02/22"
               ("%d/%m/%y, %H:%M:%S" or "%d/%m/%y")
        \b
        imported bool: Yield only imported files
        re       bool: Regex search for every str filter
        \b
        non_recursive_scope bool: Ignore scope subdirectories
    \b
    See tgbox.readthedocs.io/en/indev/
        tgbox.html#tgbox.tools.SearchFilter
    \b
    You can also use special flags to specify
    that filters is for include (+i, ++include
    [by default]) or exclude (+e, ++exclude) search.
    """
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
    '--chat', '-c', required=True, prompt=True,
    help='Chat to send file to'
)
@click.option(
    '--chat-is-name', is_flag=True,
    help='Interpret --chat as Chat name and search for it'
)
@ctx_require(dlb=True, drb=True, account=True)
def file_forward(ctx, filters, chat, chat_is_name):
    """
    Forward files by filters to specified chat

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
        min_size integer/str: File Size should be > min_size
        max_size integer/str: File Size should be < max_size
        +
        min_size & max_size can be also specified as string,
            i.e "1GB" (one gigabyte), "122.45KB" or "700B"
        \b
        min_time integer/float/str: Upload Time should be > min_time
        max_time integer/float/str: Upload Time should be < max_time
        +
        min_time & max_time can be also specified as string,
            i.e "22/02/22, 22:22:22" or "22/02/22"
               ("%d/%m/%y, %H:%M:%S" or "%d/%m/%y")
        \b
        imported bool: Yield only imported files
        re       bool: Regex search for every str filter
        \b
        non_recursive_scope bool: Ignore scope subdirectories
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
        tgbox-cli file-forward +i id=22 --chat me
        \b
        # Exclude flag (will ignore matched)
        tgbox-cli file-forward +e mime=audio --chat @channel
        \b
        You can use both, the ++include and
        ++exclude (+i, +e) in one command.
    """
    if not filters:
        echo(
            '''\n[RED]You didn\'t specified any filter.\n   This '''
            '''will forward EVERY file from your Box[RED]\n'''
        )
        if not click.confirm('Are you TOTALLY sure?'):
            return
    try:
        sf = filters_to_searchfilter(filters)
    except IndexError: # Incorrect filters format
        echo('[RED]Incorrect filters! Make sure to use format filter=value[RED]')
    except KeyError as e: # Unknown filters
        echo(f'[RED]Filter "{e.args[0]}" doesn\'t exists[RED]')
    else:
        try:
            chat_name = chat
            chat = tgbox.sync(ctx.obj.account.get_entity(chat))
        except (UsernameNotOccupiedError, UsernameInvalidError, ValueError):
            if not chat_is_name:
                echo(f'[YELLOW]Can\'t find specified chat "{chat}"[YELLOW]')
                return

            for dialogue in sync_async_gen(ctx.obj.account.iter_dialogs()):
                if chat in dialogue.title and dialogue.is_channel:
                    chat_name = dialogue.title.split(': ',1)[-1]
                    chat = dialogue; break
            else:
                echo(f'[YELLOW]Can\'t find specified chat "{chat}"[YELLOW]')
                return

        to_forward = ctx.obj.dlb.search_file(sf)
        FORWARD_STACK, FORWARD_WHEN = [], 100

        def _forward(stack: list):
            forward = ctx.obj.account.forward_messages(
                entity=chat,
                messages=[dlbf.id for dlbf in stack],
                from_peer=ctx.obj.drb.box_channel
            )
            tgbox.sync(forward)

            for dlbf in stack:
                echo(f'[GREEN]ID{dlbf.id}: {dlbf.file_name}: was forwarded to {chat_name}[GREEN]')

        echo('[YELLOW]\nSearching files to forward...[YELLOW]\n')

        for dlbf in sync_async_gen(to_forward):
            if len(FORWARD_STACK) == FORWARD_WHEN:
                _forward(FORWARD_STACK)
                FORWARD_STACK.clear()

            FORWARD_STACK.append(dlbf)

        if FORWARD_STACK: # If any left
            _forward(FORWARD_STACK)
        echo('')

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
@ctx_require(dlb=True, drb=True)
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
        min_size integer/str: File Size should be > min_size
        max_size integer/str: File Size should be < max_size
        +
        min_size & max_size can be also specified as string,
            i.e "1GB" (one gigabyte), "122.45KB" or "700B"
        \b
        min_time integer/float/str: Upload Time should be > min_time
        max_time integer/float/str: Upload Time should be < max_time
        +
        min_time & max_time can be also specified as string,
            i.e "22/02/22, 22:22:22" or "22/02/22"
               ("%d/%m/%y, %H:%M:%S" or "%d/%m/%y")
        \b
        imported bool: Yield only imported files
        re       bool: Regex search for every str filter
        \b
        non_recursive_scope bool: Ignore scope subdirectories
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
@ctx_require(dlb=True)
def dir_list(ctx):
    """List all directories in LocalBox"""

    dirs = ctx.obj.dlb.contents(ignore_files=True)

    for dir in sync_async_gen(dirs):
        tgbox.sync(dir.lload(full=True))
        echo(str(dir))

@cli.command()
@click.option(
    '--directory', '-d', required=True, prompt=True,
    help='Absolute path of Directory to forward'
)
@click.option(
    '--chat', '-c', required=True, prompt=True,
    help='Chat to send file to'
)
@click.option(
    '--chat-is-name', is_flag=True,
    help='Interpret --chat as Chat name and search for it'
)
@ctx_require(dlb=True, drb=True, account=True)
def dir_forward(ctx, directory, chat, chat_is_name):
    """
    Forward files from dir to specified chat
    """
    dlbd = tgbox.sync(ctx.obj.dlb.get_directory(directory.strip()))

    if not dlbd:
        echo(f'[RED]There is no dir "{directory}" in LocalBox.[RED]')
    else:
        filters = [f'scope={directory}', 'non_recursive_scope=True']
        ctx.invoke(file_forward, filters=filters, chat=chat, chat_is_name=chat_is_name)

@cli.command()
@click.option(
    '--requestkey', '-r',
    help='Requester\'s RequestKey'
)
@click.option(
    '--directory', '-d', required=True, prompt=True,
    help='Absolute path of Directory to share'
)
@ctx_require(dlb=True)
def dir_share(ctx, requestkey, directory):
    """Get a ShareKey from RequestKey to share dir"""

    dlbd = tgbox.sync(ctx.obj.dlb.get_directory(directory.strip()))

    if not dlbd:
        echo(f'[RED]There is no dir "{directory}" in LocalBox.[RED]')
    else:
        requestkey = requestkey if not requestkey \
            else tgbox.keys.Key.decode(requestkey)

        sharekey = dlbd.get_sharekey(requestkey)

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

# ========================================================= #
# = Commands to manage TGBOX logger ======================= #

@cli.command()
@click.option(
    '--locate', '-l', is_flag=True,
    help='If specified, will open file path in file manager'
)
def logfile_open(locate):
    """Open logfile with default app"""
    click.launch(str(logfile), locate=locate)

@cli.command()
def logfile_wipe():
    """Clear all logfile entries"""
    open(logfile,'w').close()
    echo('[GREEN]Done.[GREEN]')

@cli.command()
def logfile_size():
    """Get bytesize of logfile"""
    size = format_bytes(logfile.stat().st_size)
    echo(f'[WHITE]{str(logfile)}[WHITE]: {size}')

@cli.command()
@click.argument('chat', nargs=-1)
@ctx_require(account=True)
def logfile_send(ctx, chat):
    """
    Send logfile to Telegram chat

    \b
    Example:\b
        tgbox-cli logfile-send @username
    """
    if not chat:
        echo(
            '''[YELLOW]You didn\'t specified any chat! Try'''
            '''[YELLOW] [WHITE]tgbox-cli logfile-send me[WHITE]'''
        )
    elif not logfile.stat().st_size:
        echo(f'[YELLOW]Logfile "{logfile.name}" is empty, so not sent.[YELLOW]')
        return

    for e in chat:
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
        colored = False if TGBOX_CLI_NOCOLOR else None

        if getenv('TGBOX_CLI_FORCE_PAGER_COLOR'):
            colored = True

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
