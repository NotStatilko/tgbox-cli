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
    import tgbox
    import logging

    from time import sleep
    from io import BytesIO

    from datetime import datetime
    from re import search as re_search

    from os.path import getsize
    from platform import system, platform

    from base64 import urlsafe_b64encode
    from shutil import get_terminal_size
    from traceback import format_exception
    from inspect import isfunction, iscoroutine

    from subprocess import (
        run as subprocess_run,
        PIPE, CalledProcessError
    )
    from code import interact as interactive_console
    from asyncio import gather, get_event_loop

    from sys import exit, version as sys_version
    try:
        # This will enable navigation in input
        import readline # pylint: disable=unused-import
    except (ImportError, ModuleNotFoundError):
        pass

    from telethon.errors.rpcerrorlist import (
        UsernameNotOccupiedError, UsernameInvalidError
    )
    from enlighten import get_manager as get_enlighten_manager
    from filetype import guess as filetype_guess # Included in tgbox

    from .tools import *
    from .version import VERSION
    from .session import Session

    if tgbox.crypto.FAST_ENCRYPTION:
        from cryptography import __version__ as CRYPTOGRAPHY_VERSION
    else:
        CRYPTOGRAPHY_VERSION = None

    if tgbox.crypto.FAST_TELETHON:
        from importlib.metadata import version as _package_version
        CRYPTG_VERSION = _package_version('cryptg')
    else:
        CRYPTG_VERSION = None


    TGBOX_CLI_NOCOLOR = bool(getenv('TGBOX_CLI_NOCOLOR'))

    # tools.color with a click.echo function
    echo = lambda t,**k: click.echo(colorize(t), **k, color=(not TGBOX_CLI_NOCOLOR))

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

    elif logfile in ('STDOUT', 'stdout'):
        logfile = None

    logging.basicConfig(
        format = (
            '[%(asctime)s] %(levelname)s:%(name)s~'
            '%(funcName)s{%(lineno)s} ::: %(message)s'
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
            '[R0b]You should run[X] [W0b]tgbox-cli '
            'cli-init[X] [R0b]firstly.[X]'
        )
        raise CheckCTXFailed('Failed on "session" requirement')

    if account and not ctx.obj.account:
        echo(
          '[R0b]You should run [X][W0b]tgbox-cli '
          'account-connect [X][R0b]firstly.[X]'
        )
        raise CheckCTXFailed('Failed on "account" requirement')

    if dlb and not ctx.obj.dlb:
        echo(
            '[R0b]You didn\'t connected box yet. Use[X] '
            '[W0b]box-open[X] [R0b]command.[X]'
        )
        raise CheckCTXFailed('Failed on "dlb" requirement')

    if drb and not ctx.obj.drb:
        echo(
            '[R0b]You didn\'t connected box yet. Use[X] '
            '[W0b]box-open[X] [R0b]command.[X]'
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
                COLOR = '[G0bl]'

            elif v.name == 'cli-init' and not session:
                COLOR = '[Y0b]'

            elif session and v.name in ('box-make', 'box-clone', 'box-list'):
                conditions = (
                    session['CURRENT_ACCOUNT'] is not None,
                    session['CURRENT_BOX'] is None
                )
                COLOR = '[Y0b]' if all(conditions) else '[W0b]'

            elif session and v.name in ('box-open', 'account-connect'):
                conditions = (
                    session['CURRENT_BOX'] is None,
                    session['CURRENT_ACCOUNT'] is None,
                )
                COLOR = '[Y0b]' if all(conditions) else '[W0b]'
            else:
                COLOR = '[W0b]'

            DOT = 'O' if COLOR != '[W0b]' else 'o'
            COLOR = '' if TGBOX_CLI_NOCOLOR else COLOR

            text = colorize(
                f'  {DOT}  {COLOR}{v.name}[X] :: '
                f'{v.get_short_help_str().strip()}'
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
        echo(f'[R0b]RemoteBox by number={number} not found.[X]')
    else:
        return erb

# ========================================================= #
# = CLI manage & setup commands =========================== #

@cli.command()
@click.option(
    '--bash', '-b', is_flag=True,
    help='If specified, will give commands for Bash'
)
@click.option(
    '--fish', '-f', is_flag=True,
    help='If specified, will give commands for Fish'
)
@click.option(
    '--zsh', '-z', is_flag=True,
    help='If specified, will give commands for Zsh'
)
@click.option(
    '--win-cmd', '-w', is_flag=True,
    help='If specified, will give commands for Zsh'
)
@click.pass_context
def cli_init(ctx, bash, fish, zsh, win_cmd):
    """Get commands for initializing TGBOX-CLI"""

    if ctx.obj.session:
        echo('[W0b]CLI is already initialized.[X]')
    else:
        if win_cmd or system() == 'Windows' and not any((bash, fish, zsh)):
            init_commands = (
                '(for /f %i in (\'tgbox-cli sk-gen\') '
                'do set "TGBOX_CLI_SK=%i") > NUL\n'
                'chcp 65001 || # Change the default CMD encoding to UTF-8'
            )
        else:
            current_shell = getenv('SHELL')

            autocompletions = {
                'bash': '\neval "$(_TGBOX_CLI_COMPLETE=bash_source tgbox-cli)"',
                'zsh': '\neval "$(_TGBOX_CLI_COMPLETE=zsh_source tgbox-cli)"',
                'fish' : '\neval (env _TGBOX_CLI_COMPLETE=fish_source tgbox-cli)'
            }
            if bash: autocomplete, cmd = autocompletions['bash'], 'bash'
            elif fish: autocomplete, cmd = autocompletions['fish'], 'fish'
            elif zsh: autocomplete, cmd = autocompletions['zsh'], 'zsh'
            else:
                if current_shell and 'bash' in current_shell:
                    autocomplete, cmd = autocompletions['bash'], 'bash'

                elif current_shell and 'fish' in current_shell:
                    autocomplete, cmd = autocompletions['fish'], 'fish'

                elif current_shell and 'zsh' in current_shell:
                    autocomplete, cmd = autocompletions['zsh'], 'zsh'
                else:
                    autocomplete = ''

            if cmd == 'fish':
                eval_commands = (
                    f'export TGBOX_CLI_SK=(tgbox-cli sk-gen)\n'
                    f'{autocomplete}')

            if cmd != 'fish':
                echo('\n# [B0b](Execute commands below if eval doesn\'t work)[X]\n')
                eval_commands = (
                    f'export TGBOX_CLI_SK="$(tgbox-cli sk-gen)"'
                    f'{autocomplete}'
                )
                echo(eval_commands)

                init_commands = 'eval "$(!!)" || true && clear'
            else:
                init_commands = (
                    f'export TGBOX_CLI_SK=(tgbox-cli sk-gen)'
                    f'{autocomplete}'
                )
        echo(
            '\n[Y0b]Welcome to the TGBOX-CLI![X]\n\n'
            'Copy & Paste commands below to your shell:\n\n'
           f'[W0b]{init_commands}[X]\n'
        )

@cli.command()
def cli_info():
    """Get information about the TGBOX-CLI build"""

    ver = __version__.split('_')
    try:
        sp_result = subprocess_run(
            args=[tgbox.defaults.FFMPEG, '-version'],
            stdout=PIPE, stderr=None, check=True
        )
        ffmpeg_version = sp_result.stdout.split(b' ',3)[2].decode()
        ffmpeg_version = f"[G0b]YES[X]([C0b]v{ffmpeg_version}[X])"
    except CalledProcessError:
        ffmpeg_version = '[R0b]UNKNOWN[X]'
    except:
        ffmpeg_version = '[R0b]NOT FOUND[X]'

    if tgbox.crypto.FAST_ENCRYPTION:
        fast_encryption = f'[G0b]YES[X]([C0b]v{CRYPTOGRAPHY_VERSION}[X])'
    else:
        fast_encryption = '[R0b]NO[X]'

    if tgbox.crypto.FAST_TELETHON:
        fast_telethon = f'[G0b]YES[X]([C0b]v{CRYPTG_VERSION}[X])'
    else:
        fast_telethon = '[R0b]NO[X]'

    sys_ver = sys_version.split('[', 1)[0].strip()
    logfile_name = 'STDOUT' if not logfile else logfile.name

    echo(
        '\n# Copyright [W0b](c) Non [github.com/NotStatilko][X], the MIT License\n'
        '# Author Email: [W0b]thenonproton@protonmail.com[X]\n\n'

        f'TGBOX-CLI Version: [Y0b]{ver[0]}[X]\n'
        f'TGBOX Version: [M0b]{ver[1]}[X]\n\n'

        f'PYTHON: [C0b]{sys_ver}[X]\n'
        f'SYSTEM: [C0b]{platform()}[X]\n\n'

        f'FFMPEG: {ffmpeg_version}\n'
        f'FAST_ENCRYPTION: {fast_encryption}\n'
        f'FAST_TELETHON: {fast_telethon}\n\n'

        f'LOGGING: [Y0b]{logging_level}[X]([W0b]{logfile_name}[X])\n'
    )
    if getenv('X0b_SABBATH'):
        from time import sleep

        bs_ana = (
            '\nI am the world that hides the universal secret of all time\n'
            'Destruction of the empty spaces is my one and only crime\n'
            'I\'ve lived a thousand times, I found out what it means to be believed\n'
            'The thoughts and images, the unborn child that never was conceived\n'
        )
        for L in bs_ana:
            if TGBOX_CLI_NOCOLOR:
                echo(L, nl=False)
            else:
                click.secho(
                    L, fg='white', bg='bright_red',
                    bold=True, italic=True, nl=False
                )
            if L == '\n':
                sleep(0.999)
            elif L == ',':
                sleep(0.666)
            else:
                sleep(0.0666)

        echo('\n') # HAHA!!!

# ========================================================= #
# = Telegram account management commands ================== #

@cli.command()
@click.option(
    '--phone', '-p', required=True, prompt=True,
    help='Phone number of your Telegram account'
)
@click.option(
    '--api-id', type=int, help='Custom API_ID from my.telegram.org'
)
@click.option(
    '--api-hash', help='Custom API_HASH from my.telegram.org'
)
@ctx_require(session=True)
def account_connect(ctx, phone, api_id, api_hash):
    """Connect your Telegram account"""

    if any((api_id, api_hash)) and not all((api_id, api_hash)):
        echo('[R0b]You need to specify both, --api-id & --api-hash[X]')
        return

    tc = tgbox.api.TelegramClient(
        phone_number=phone,
        api_id=(api_id or API_ID),
        api_hash=(api_hash or API_HASH)
    )
    echo('[C0b]Connecting to Telegram...[X]')
    tgbox.sync(tc.connect())

    echo('[C0b]Sending code request...[X]')
    tgbox.sync(tc.send_code())

    code = click.prompt('Received code', type=int)

    password = click.prompt(
        text = 'Password',
        hide_input = (not TGBOX_CLI_SHOW_PASSWORD),
        default = '',
        show_default = False
    )
    echo('[C0b]Trying to sign-in...[X] ', nl=False)
    tgbox.sync(tc.log_in(code=code, password=password))

    echo('[G0b]Successful![X]')
    echo('[C0b]Updating local data...[X] ', nl=False)

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
                echo('[R0b]Account already added[X]')
                return

        for d_session in disconnected_sessions:
            ctx.obj.session['ACCOUNT_LIST'].remove(d_session)

        ctx.obj.session['ACCOUNT_LIST'].append(tc.session.save())
        ctx.obj.session['CURRENT_ACCOUNT'] = len(ctx.obj.session['ACCOUNT_LIST']) - 1

    ctx.obj.session.commit()
    echo('[G0b]Successful![X]')

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
        echo('[R0b]You don\'t have any connected account.[X]')

    elif number < 1 or number > len(ctx.obj.session['ACCOUNT_LIST']):
        echo(
            f'[R0b]There is no account #{number}. Use [X]'
             '[W0b]account-list[X] [R0b]command.[X]')
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
            echo('[G0b]Disconnected. No more accounts.[X]')
        else:
            ctx.obj.session['CURRENT_ACCOUNT'] = 0
            echo('[G0b]Disconnected & switched to the account #1[X]')

        ctx.obj.session.commit()

@cli.command()
@ctx_require(session=True)
def account_list(ctx):
    """List all connected accounts"""

    if ctx.obj.session['CURRENT_ACCOUNT'] is None:
        echo(
            '[R0b]You didn\'t connected any account yet. Use[X] '
            '[W0b]account-connect[X] [R0b]command firstly.[X]')
    else:
        echo(
            '\n[W0b]You\'re using account[X] [R0b]'
           f'#{str(ctx.obj.session["CURRENT_ACCOUNT"] + 1)}[X]\n'
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
                echo(f'[W0b]{count+1})[X] [B0b]{name}[X] (id{info.id})')
            except AttributeError:
                # If session was disconnected
                echo(f'[W0b]{count+1})[X] [R0b]disconnected, so removed[X]')
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
            '[R0b]You didn\'t connected any account yet. Use[X] '
            '[W0b]account-connect[X] [R0b]command firstly.[X]'
        )
    elif number < 1 or number > len(ctx.obj.session['ACCOUNT_LIST']):
        echo(
            f'[R0b]There is no account #{number}. Use [X]'
             '[W0b]account-list[X] [R0b]command.[X]'
        )
    elif number-1 == ctx.obj.session['CURRENT_ACCOUNT']:
        echo(
            '[Y0b]You already on this account. See other with[X] '
             '[W0b]account-list[X] [Y0b]command.[X]')
    else:
        ctx.obj.session['CURRENT_ACCOUNT'] = number - 1
        ctx.obj.session.commit()

        echo(f'[G0b]You switched to account #{number}[X]')

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
    full_name = f'[W0b]{me.first_name} {last_name}[X]'

    if show_phone:
        phone = f'[W0b]+{me.phone}[X]'
    else:
        phone = '[R0b]<Was hidden>[X]'

    if me.premium:
        premium = '[W0b]yes[X]'
    else:
        premium = '[R0b]no[X]'

    if me.username:
        username = f'[W0b]@{me.username}[X]'
    else:
        username = '[R0b]<Not presented>[X]'

    user_id = f'[W0b]id{me.id}[X]'

    echo(
        '\n ====== Current Account ====== \n\n'

        f'| Full name: {full_name}\n'
        f'| Username: {username}\n'
        f'| Phone: {phone}\n'
        f'| ID: {user_id}\n'
        f'| Premium: {premium}\n'

        '\n ============================= \n'
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
        echo(f'\nYour Phrase is [M0b]{phrase}[X]')

        echo(
            'Please, write it down [W0b]on paper[X] '
            'and press [R0b]Enter[X]'
            ', we will [R0b]clear[X] shell for you'
        )
        input(); clear_console()

    elif not phrase:
        phrase, phrase_repeat = 0, 1
        while phrase != phrase_repeat:
            if phrase != 0: # Init value
                echo('[R0b]Phrase mismatch! Try again[X]\n')

            phrase = click.prompt(
                text = 'Phrase',
                hide_input = (not TGBOX_CLI_SHOW_PASSWORD)
            )
            phrase_repeat = click.prompt(
                text = 'Repeat phrase',
                hide_input = (not TGBOX_CLI_SHOW_PASSWORD)
            )

    echo('[C0b]Making BaseKey...[X] ', nl=False)

    if box_salt:
        box_salt = tgbox.crypto.BoxSalt(bytes.fromhex(box_salt))

    basekey = tgbox.keys.make_basekey(
        phrase.strip().encode(),
        salt=bytes.fromhex(s),
        n=n, p=p, r=r, dklen=l
    )
    echo('[G0b]Successful![X]')

    echo('[C0b]Making RemoteBox...[X] ', nl=False)
    erb = tgbox.sync(tgbox.api.make_remotebox(
        ctx.obj.account, box_name, box_salt=box_salt)
    )
    echo('[G0b]Successful![X]')

    echo('[C0b]Making LocalBox...[X] ', nl=False)
    dlb = tgbox.sync(tgbox.api.make_localbox(
        erb, basekey, box_path=box_path, box_name=box_name))
    echo('[G0b]Successful![X]')

    echo('[C0b]Updating local data...[X] ', nl=False)

    localbox_path = str(Path(dlb.tgbox_db.db_path).resolve())

    ctx.obj.session['BOX_LIST'].append([localbox_path, basekey.key])
    ctx.obj.session['CURRENT_BOX'] = len(ctx.obj.session['BOX_LIST']) - 1

    ctx.obj.session.commit()

    tgbox.sync(erb.done())
    tgbox.sync(dlb.done())

    echo('[G0b]Successful![X]')

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
@click.option(
    '--no-switch', is_flag=True,
    help='If specified, will not switch to Box you connect'
)
@ctx_require(session=True)
def box_open(ctx, box_path, phrase, s, n, p, r, l, no_switch):
    """Decrypt & connect existing LocalBox"""

    echo('[C0b]Making BaseKey...[X] ', nl=False)

    basekey = tgbox.keys.make_basekey(
        phrase.strip().encode(),
        salt=bytes.fromhex(s),
        n=n, p=p, r=r, dklen=l
    )
    echo('[G0b]Successful![X]')

    box_path = box_path.resolve()

    echo('[C0b]Opening LocalBox...[X] ', nl=False)
    try:
        dlb = tgbox.sync(tgbox.api.get_localbox(basekey, box_path))
    except tgbox.errors.AESError:
        echo('[R0b]Incorrect passphrase![X]')
    else:
        echo('[G0b]Successful![X]')
        echo('[C0b]Updating local data...[X] ', nl=False)

        localbox_path = str(Path(dlb.tgbox_db.db_path).resolve())
        box_data = [localbox_path, basekey.key]

        for other_box_data in ctx.obj.session['BOX_LIST']:
            if other_box_data == box_data:
                echo('[R0b]This Box is already opened[X]')
                break
        else:
            ctx.obj.session['BOX_LIST'].append(box_data)

            if not no_switch:
                ctx.obj.session['CURRENT_BOX'] = len(ctx.obj.session['BOX_LIST']) - 1

            ctx.obj.session.commit()
            echo('[G0b]Successful![X]')

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
        echo('[R0b]Invalid number, see box-list[X]')
    else:
        ctx.obj.session['BOX_LIST'].pop(number-1)

        if not ctx.obj.session['BOX_LIST']:
            ctx.obj.session['CURRENT_BOX'] = None
            echo('No more Boxes, use [W0b]box-open[X].')
        else:
            ctx.obj.session['CURRENT_BOX'] = 0
            echo('[G0b]Disconnected & switched to the Box #1[X]')

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
            f'[R0b]There is no box #{number}. Use[X] '
             '[W0b]box-list[X] [R0b]command.[X]'
        )
    elif number-1 == ctx.obj.session['CURRENT_BOX']:
        echo(
            '[Y0b]You already use this box. See other with[X] '
            '[W0b]box-list[X] [Y0b]command.[X]'
        )
    else:
        ctx.obj.session['CURRENT_BOX'] = number - 1
        ctx.obj.session.commit()

        echo(f'[G0b]You switched to box #{number}[X]')

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

        echo('[Y0b]Searching...[X]')
        for chat in sync_async_gen(ctx.obj.account.iter_dialogs()):
            if prefix in chat.title and chat.is_channel:
                erb = tgbox.api.EncryptedRemoteBox(chat, ctx.obj.account)

                erb_name = tgbox.sync(erb.get_box_name())
                erb_salt = tgbox.sync(erb.get_box_salt())
                erb_salt = urlsafe_b64encode(erb_salt.salt).decode()
                erb_desc = tgbox.sync(erb.get_box_description())

                count_id = str(count+1).zfill(2)
                echo(
                    f'[W0b]{count_id}[X]) [B0b]{erb_name}[X]'
                    f'@[X1b]{erb_salt}[X]'
                )
                if erb_desc:
                    erb_desc = split_string(f'{erb_desc}', 4, '>')
                    echo(f'    Description: [Y0b]{erb_desc}[X]')
                count += 1

        echo('[Y0b]Done.[X]')
    else:
        check_ctx(ctx, session=True)

        if ctx.obj.session['CURRENT_BOX'] is None:
            echo(
                '[R0b]You didn\'t opened any box yet. Use[X] '
                '[W0b]box-open[X] [R0b]command firstly.[X]')
        else:
            echo(
                '\n[W0b]You\'re using Box[X] '
               f'[R0b]#{str(ctx.obj.session["CURRENT_BOX"]+1)}[X]\n'
            )
            lost_boxes, count = [], 0

            for box_path, basekey in ctx.obj.session['BOX_LIST']:
                try:
                    name = Path(box_path).name

                    dlb = tgbox.sync(tgbox.api.get_localbox(
                        tgbox.keys.BaseKey(basekey), box_path)
                    )
                    salt = urlsafe_b64encode(dlb.box_salt.salt).decode()

                    count_id = str(count+1).zfill(2)
                    echo(
                        f'[W0b]{count_id})[X] [B0b]{name}[X]'
                        f'@[X1b]{salt}[X]'
                    )
                    tgbox.sync(dlb.done())
                except FileNotFoundError:
                    count_id = str(count+1).zfill(2)
                    echo(
                       f'[W0b]{count_id})[X] [R0b]{name} LocalBox '
                        'file was moved, so disconnected.[X]'
                    )
                    lost_boxes.append([box_path, basekey])

                count += 1

            for lbox in lost_boxes:
                ctx.obj.session['BOX_LIST'].remove(lbox)

            if lost_boxes:
                if not ctx.obj.session['BOX_LIST']:
                    ctx.obj.session['CURRENT_BOX'] = None
                    echo('No more Boxes, use [W0b]box-open[X].')
                else:
                    ctx.obj.session['CURRENT_BOX'] = 0
                    echo(
                        'Switched to the first Box. Set other '
                        'with [W0b]box-switch[X].'
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
            '[W0b]--start-from-id[X] [R0b]can be used only '
            'with[X] [W0b]--deep[X][R0b]![X]'
        ); return

    if not deep:
        progress_callback = lambda i,a: echo(f'* [W0b]ID{i}[X]: [C0b]{a}[X]')
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
        echo(f'[R0b]{e}[X]')
    else:
        echo('[G0b]Syncing complete.[X]')

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

    You can also use it to change API_ID and API_HASH
    params of your Box if '--api-id' & '--api-hash' was
    used on the 'account-connect' command prior.
    """
    if number < 1 or number > len(ctx.obj.session['ACCOUNT_LIST']):
        echo(
            '[R0b]Invalid account number! See[X] '
            '[W0b]account-list[X] [R0b]command.[X]')
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
        echo('[G0b]Session replaced successfully[X]')

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
        '\nSend this Key to the Box owner:\n'
       f'    [W0b]{reqkey.encode()}[X]\n'
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
            '\n[R0b]You didn\'t specified requestkey.\n   You '
            'will receive decryption key IN PLAIN\n[X]'
        )
        if not click.confirm('Are you TOTALLY sure?'):
            return
    echo(
        '\nSend this Key to the Box requester:\n'
       f'    [W0b]{sharekey.encode()}[X]\n'
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

    echo('\n[C0b]Making BaseKey...[X] ', nl=False)

    basekey = tgbox.keys.make_basekey(
        phrase.strip().encode(),
        salt=bytes.fromhex(s),
        n=n, p=p, r=r, dklen=l
    )
    echo('[G0b]Successful![X]')

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
    echo('\n[C0b]Updating local data...[X] ', nl=False)

    localbox_path = str(Path(dlb.tgbox_db.db_path).resolve())
    box_data = [localbox_path, basekey.key]

    for other_box_data in ctx.obj.session['BOX_LIST']:
        if other_box_data == box_data:
            echo('[R0b]This Box is already opened[X]')
            break
    else:
        ctx.obj.session['BOX_LIST'].append(box_data)
        ctx.obj.session['CURRENT_BOX'] = len(ctx.obj.session['BOX_LIST']) - 1

        ctx.obj.session.commit()
        echo('[G0b]Successful![X]')

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
            echo(f'[G0b]Successfully changed {key} to {value}[X]')
        except AttributeError:
            echo(f'[R0b]Default {key} doesn\'t exist, skipping[X]')

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

            total_formatted = f'[B0b]{format_bytes(total_bytes)}[X]'

            if current_file_count == total_files:
                current_file = f'[G0b]{current_file_count}[X]'
            else:
                current_file = f'[Y0b]{current_file_count}[X]'

            echo_text = (
                f'@ Total [W0b]Box[X] size is {total_formatted}'
                f'({total_bytes}) [{current_file}/[G0b]{total_files}[X]]   \r'
            )
            echo(echo_text, nl=False)

        echo('\n')
    else:
        box_name = tgbox.sync(ctx.obj.drb.get_box_name())
        box_name = f'[W0b]{box_name}[X]'

        box_id = f'[W0b]id{ctx.obj.drb.box_channel_id}[X]'

        total_local = tgbox.sync(ctx.obj.dlb.get_files_total())
        total_remote = tgbox.sync(ctx.obj.drb.get_files_total())

        if total_local != total_remote:
            status = f'[R0b]Out of sync! ({total_local}L/{total_remote}R)[X]'
        else:
            status = '[G0b]Seems synchronized[X]'

        total_local = f'[W0b]{total_local}[X]'
        total_remote = f'[W0b]{total_remote}[X]'

        if ctx.obj.drb.box_channel.username:
            public_link = f'[W0b]@{ctx.obj.drb.box_channel.username}[X]'
        else:
            public_link = '[R0b]<Not presented>[X]'

        if ctx.obj.drb.box_channel.restricted:
            restricted = f'[R0b]yes: {ctx.obj.drb.box_channel.restriction_reason}[X]'
        else:
            restricted = '[W0b]no[X]'

        box_path = f'[W0b]{ctx.obj.dlb.tgbox_db.db_path.name}[X]'

        local_box_date = datetime.fromtimestamp(ctx.obj.dlb.box_cr_time).strftime('%d/%m/%Y')
        local_date_created = f'[W0b]{local_box_date}[X]'

        remote_box_date = tgbox.sync(ctx.obj.drb.tc.get_messages(
            ctx.obj.drb.box_channel, ids=1)
        )
        remote_box_date = remote_box_date.date.strftime('%d/%m/%Y')
        remote_date_created = f'[W0b]{remote_box_date}[X]'

        box_description = tgbox.sync(ctx.obj.drb.get_box_description())
        if box_description:
            box_description = break_string(box_description, 15)
            box_description = colorize(f'[Y0b]{box_description}[X]')
        else:
            box_description = colorize('[R0b]<Not presented>[X]')

        rights_interested = {
            'post_messages' : 'Upload files',
            'delete_messages' : 'Remove files',
            'edit_messages' : 'Edit files',
            'invite_users' : 'Invite users',
            'add_admins': 'Add admins'
        }
        if ctx.obj.drb.box_channel.admin_rights:
            rights = ' (+) [G0b]Fast sync files[X]\n'
        else:
            rights = ' (-) [R0b]Fast sync files[X]\n'

        rights += ' (+) [G0b]Download files[X]\n'

        for k,v in rights_interested.items():
            if ctx.obj.drb.box_channel.admin_rights and\
                getattr(ctx.obj.drb.box_channel.admin_rights, k):
                    right_status = '(+)' # User has such right
                    right = f'[G0b]{v}[X]'
            else:
                right_status = '(-)' # User hasn't such right
                right = f'[R0b]{v}[X]'

            rights += f' {right_status} {right}\n'

        echo(
            '\n ====== Current Box (remote) ======\n\n'

            f'| Box name: {box_name}\n'
            f'| Description: [Y0b]{box_description}[X]\n'
            f'| Public link: {public_link}\n'
            f'| ID: {box_id}\no\n'
            f'| Date created: {remote_date_created}\n'
            f'| Files total: {total_remote}\n'
            f'| Is restricted: {restricted}\no\n'
            f'| Your rights: \n{rights}\n'

            ' ====== Current Box (local) =======\n\n'

            f'| Box DB: {box_path}\n'
            f'| Date created: {local_date_created}\n'
            f'| Files total: {total_local}\n'

            '\n :::::::::::::::::::::::::::::::::\n\n'

            f'| Status: {status}\n'

            '\n =================================\n'
        )

@cli.command()
@ctx_require(dlb=True, drb=True)
def box_delete(ctx):
    """Completely remove your Box with all files in it"""

    dlb_box_name = Path(ctx.obj.dlb.tgbox_db.db_path).name
    drb_box_name = tgbox.sync(ctx.obj.drb.get_box_name())

    files_total = tgbox.sync(ctx.obj.drb.get_files_total())

    warning_message = (
        '    [R0b]WARNING! You are trying to COMPLETELY REMOVE your\n'
       f'    CURRENT SELECTED Box with {files_total} FILES IN IT. After this\n'
        '    operation, you WILL NOT BE ABLE to recover or download\n'
        '    your files IN ANY WAY. If you wish to remove (for some\n'
       f'    strange case) only LocalBox then remove the "{dlb_box_name}"\n'
        '    file on your Computer. This command will remove the Local &\n'
        '    Remote BOTH. Proceed only if you TOTALLY understand this![X]'
    )
    echo('\n' + warning_message)

    echo(
       f'\n@ Please enter [Y0b]{drb_box_name}[X] to '
        '[R0b]DESTROY[X] your Box or press [B0b]CTRL+C[X] to abort'
    )
    user_input = click.prompt('\nBox name')

    if user_input == drb_box_name:
        echo('You typed Box name [R0b]correctly[X].\n')

        if click.confirm('The last question: are you sure?'):
            echo('\n[C0b]Closing you LocalBox...[X] ', nl=False)
            ctx.invoke(box_close, number=ctx.obj.session['CURRENT_BOX']+1)

            echo('[C0b]Completely removing your LocalBox...[X] ', nl=False)
            tgbox.sync(ctx.obj.dlb.delete())
            echo('[G0b]Successful![X]')

            echo('[C0b]Completely removing your RemoteBox...[X] ', nl=False)
            tgbox.sync(ctx.obj.drb.delete())
            echo('[G0b]Successful![X]')
        else:
            echo('\nYou [R0b]didn\'t agreed[X]. [Y0b]Aborting[X].')

    else:
        echo(f'\nYou typed [W0b]{user_input}[X], which is incorrect. [Y0b]Aborting.[X]')

# ========================================================= #
# = Local & Remote BoxFile management commands ============ #

@cli.command()
@click.argument(
    'target', nargs=-1, required=False, default=None,
    type=click.Path(readable=None, dir_okay=True, path_type=Path)
)
@click.option(
    '--file-path', '-f', type=Path,
    help='Change file path of target in Box. System\'s if not specified'
)
@click.option(
    '--cattrs', '-c', help='File\'s CustomAttributes. Format: "key: value | key: value"'
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
    '--calculate', is_flag=True,
    help='If specified, will calculate and show a total bytesize of targets'
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
        ctx, target, file_path, cattrs, no_update,
        force_update, use_slow_upload, no_thumb,
        calculate, max_workers, max_bytes):
    """
    Upload TARGET by specified filters to the Box

    \b
    TARGET can be a path to File or a Directory.
    If TARGET is a Directory, -- this command
    will upload to Box all files from dir.
    \b
    If file was already uploaded but changed (in size)
    and --no-update is NOT specified, -- will re-upload.
    \b
    Available filters:\b
        file_path str: File path
        file_name str: File name
        mime str: File MIME type
        \b
        min_size integer/str: File Size should be > min_size
        max_size integer/str: File Size should be < max_size
        +
        min_size & max_size can be also specified as string,
            i.e "1GB" (one gigabyte), "122.45KB" or "700B"
        \b
        min_time integer/float/str: Modification Time should be > min_time
        max_time integer/float/str: Modification Time should be < max_time
        +
        min_time & max_time can be also specified as string,
            i.e "22/02/22, 22:22:22" or "22/02/22"
        \b
        re bool: Regex search for every str filter
    \b
    Please note that Filters should be placed after TARGET!
    \b
    You can also use special flags to specify
    that filters is for include or exclude search:
    \b
    Example:\b
        # An ordinary upload process (upload Music & Documents folders)
        tgbox-cli file-upload /home/user/Music /home/user/Documents
        \b
        # Include flag (upload only .DOC from Documents, ignore unmatched)
        tgbox-cli file-upload /home/non/Documents +i file_name='.doc'
        \b
        # Exclude flag (ingore .DOC, upload every single file from Documents)
        tgbox-cli file-upload /home/non/Documents +e file_name='.doc'
        \b
        You can use both, the ++include and ++exclude (+i, +e)
        in one command, but make sure to place them after TARGET!
    """
    if not target:
        target = click.prompt('Please enter target to upload')
        target = (Path(target),)
    else:
        target = tuple((str(p) for p in target))

    if '+i' in target:
        filters_pos_i = target.index('+i')

    elif '++include' in target:
        filters_pos_i = target.index('++include')
    else:
        filters_pos_i = None

    if '+e' in target:
        filters_pos_e = target.index('+e')

    elif '++exclude' in target:
        filters_pos_e = target.index('++exclude')
    else:
        filters_pos_e = None

    if all((filters_pos_i, filters_pos_e)):
        filters_pos = min(filters_pos_i, filters_pos_e)
    else:
        filters_pos = (filters_pos_i or filters_pos_e)

    if filters_pos:
        filters = filters_to_searchfilter(target[filters_pos:])
        target = target[:filters_pos]
    else:
        filters = None

    # Remove all duplicates present in Target (if any)
    target = tuple(set(Path(p) for p in target))

    current_workers = max_workers
    current_bytes = max_bytes

    if cattrs is not None and not cattrs:
        parsed_cattrs = {}

    elif cattrs is not None:
        parsed_cattrs = parse_str_cattrs(cattrs)
    else:
        parsed_cattrs = None

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
            echo(f'[Y0b]| File {file} is already uploaded. Skipping...[X]')
            return

        if cattrs is None: # CAttrs not specified
            cattrs = cattrs or dlbf.cattrs if dlbf else None

        elif not cattrs: # Can be "", then remove CAttrs
            cattrs = None
        else:
            if dlbf and dlbf.cattrs: # Combine if dlbf has CAttrs
                dlbf.cattrs.update(cattrs)
                cattrs = dlbf.cattrs
        try:
            pf = await ctx.obj.dlb.prepare_file(
                file = open(file,'rb'),
                file_path = file_path,
                cattrs = cattrs,
                make_preview = (not no_thumb),
                skip_fingerprint_check = True
            )
        except tgbox.errors.LimitExceeded as e:
            echo(f'[Y0b]{file}: {e} Skipping...[X]')
            return

        except PermissionError:
            echo(f'[R0b]{file} is not readable! Skipping...[X]')
            return

        progressbar = Progress(ctx.obj.enlighten_manager, file.name)

        file_action[1]['pf'] = pf
        file_action[1]['progress_callback'] = progressbar.update
        file_action[1]['use_slow_upload'] = use_slow_upload

        await file_action[0](**file_action[1])

    for path in target:
        if not path.exists():
            echo(f'[R0b]@ Target "{path}" doesn\'t exists! Skipping...[X]')
            continue

        if path.is_dir():
            try:
                next(path.iterdir())
            except (FileNotFoundError, PermissionError, OSError):
                echo(f'[R0b]@ Target "{path}" is not readable! Skipping...[X]')
                continue

        if path.is_dir():
            iter_over = path.rglob('*')
        else:
            iter_over = (path,)

        echo(f'[C0b]@ Working on[X] [W0b]{str(path.absolute())}[X] ...')

        # Will be used if --calculate specified
        target_files, target_files_bs = 0, 0

        to_upload = []
        for current_path in iter_over:
            try:
                if current_path.is_dir():
                    echo(f'[C0b]@ Working on[X] [W0b]{str(current_path)}[X] ...')
                    continue
            except (FileNotFoundError, PermissionError, OSError) as e:
                echo(f'[R0b]x Not Working on. {e}. Skipping...[X]')
                continue

            if filters:
                # Flags. First is for 'Include', the second
                # is for 'Exclude. Both must be 'True' to
                # start uploading process.
                yield_result = [True, True]

                # Will use Regex Search if 're' is included in Filters, "In" otherwise.
                in_func = re_search if filters.in_filters['re'] else lambda p,s: p in s

                for indx, filter in enumerate((filters.in_filters, filters.ex_filters)):
                    try:
                        if filter['min_time'] or filter['max_time']:
                            cp_st_mtime = current_path.stat().st_mtime # File Modification Time

                        if filter['min_size'] or filter['max_size']:
                            cp_st_size = current_path.stat().st_size # File Size

                        if filter['mime']:
                            file_mime = filetype_guess(current_path) # File MIME Type
                            file_mime = file_mime.mime if file_mime else ''

                        if filter['file_path']:
                            abs_path = str(current_path.absolute()) # File absolute Path

                    except (FileNotFoundError, PermissionError, OSError) as e:
                        echo(f'[R0b]x {e}. Skipping...[X]')
                        yield_result[0] = False; break

                    for filter_file_path in filter['file_path']:
                        if in_func(filter_file_path, abs_path):
                            if indx == 1:
                                yield_result[indx] = False
                            break
                    else:
                        if filter['file_path']:
                            if indx == 0:
                                yield_result[indx] = False
                                break

                    for file_name in filter['file_name']:
                        if in_func(file_name, current_path.name):
                            if indx == 1:
                                yield_result[indx] = False
                            break
                    else:
                        if filter['file_name']:
                            if indx == 0:
                                yield_result[indx] = False
                                break

                    for mime in filter['mime']:
                        if in_func(mime, file_mime):
                            if indx == 1:
                                yield_result[indx] = False
                            break
                    else:
                        if filter['mime']:
                            if indx == 0:
                                yield_result[indx] = False
                                break

                    if filter['min_time']:
                        if cp_st_mtime < filter['min_time'][-1]:
                            if indx == 0:
                                yield_result[indx] = False
                                break

                        elif cp_st_mtime >= filter['min_time'][-1]:
                            if indx == 1:
                                yield_result[indx] = False
                                break

                    if filter['max_time']:
                        if cp_st_mtime > filter['max_time'][-1]:
                            if indx == 0:
                                yield_result[indx] = False
                                break

                        elif cp_st_mtime <= filter['max_time'][-1]:
                            if indx == 1:
                                yield_result[indx] = False
                                break

                    if filter['min_size']:
                        if cp_st_size < filter['min_size'][-1]:
                            if indx == 0:
                                yield_result[indx] = False
                                break

                        elif cp_st_size >= filter['min_size'][-1]:
                            if indx == 1:
                                yield_result[indx] = False
                                break

                    if filter['max_size']:
                        if cp_st_size > filter['max_size'][-1]:
                            if indx == 0:
                                yield_result[indx] = False
                                break

                        elif cp_st_size <= filter['max_size'][-1]:
                            if indx == 1:
                                yield_result[indx] = False
                                break

                if not all(yield_result):
                    echo(
                        f'[Y0b]x Target "{current_path}" is '
                        'ignored by filters! Skipping...[X]'
                    )
                    continue

            if calculate:
                if not current_path.exists():
                    echo(
                       f'[R0b]@ Target "{current_path}" doesn\'t '
                        'exists! Skipping...[X]')
                    continue

                cp_st_size = current_path.stat().st_size

                target_files += 1; target_files_bs += cp_st_size
                target_files_bs_f = format_bytes(target_files_bs)

                echo_text = (
                    f'@ Total [W0b]targets found [X]([Y0b]{target_files}[X]) '
                    f'size is [B0b]{target_files_bs_f}[X]({target_files_bs})   \r'
                )
                echo(echo_text, nl=False)
                echo(' ' * 60 + '\r', nl=False)
            else:
                if not file_path:
                    remote_path = current_path.resolve()
                else:
                    remote_path = Path(file_path) / current_path.name

                current_bytes -= getsize(current_path)
                current_workers -= 1

                if not all((current_workers > 0, current_bytes > 0)):
                    try:
                        _upload(to_upload)
                    except tgbox.errors.NotEnoughRights as e:
                        echo(f'\n[R0b]{e}[X]')
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
                echo(f'\n[R0b]{e}[X]')

        if calculate and target_files:
            echo(' ' * 60 + '\r', nl=True)
            echo(echo_text + '\n')

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
@click.option(
    '--fetch-count', '-f', default=100,
    help='Amount of files to fetch from LocalBox before return',
)
@click.pass_context
def file_search(
        ctx, filters, force_remote, non_interactive,
        non_imported, upend, bytesize_total, fetch_count):
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
        mime str: File MIME type
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
        minor_version int: File minor version
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

        scope_path_list = (
              list(sf.in_filters['scope'])\
            + list(sf.in_filters['file_path'])
        )
        for filter_ in scope_path_list:
            if '__BOX_CHAT__' in filter_: # Remove all files in __BOX_CHAT__
                break                     # from the file-search list if
        else:                             # user didn't requested it
            sf.ex_filters['file_path'].append('__BOX_CHAT__')

    except IndexError: # Incorrect filters format
        echo('[R0b]Incorrect filters! Make sure to use format filter=value[X]')
    except KeyError as e: # Unknown filters
        echo(f'[R0b]Filter "{e.args[0]}" doesn\'t exists[X]')
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
            echo('[Y0b]\nSearching, press CTRL+C to stop...[X]')

            for xrbf in sync_async_gen(iter_over):
                if type(xrbf) is tgbox.api.EncryptedRemoteBoxFile:
                    time = datetime.fromtimestamp(xrbf.upload_time)
                    time = f"[C0b]{time.strftime('%d/%m/%y, %H:%M:%S')}[X]"

                    salt = urlsafe_b64encode(xrbf.file_salt.salt).decode()
                    idsalt = f'[[R1b]{str(xrbf.id)}[X]:'
                    idsalt += f'[X1b]{salt[:12]}[X]]'

                    size = f'[G0b]{format_bytes(xrbf.file_size)}[X]'
                    name = '[R0b][N/A: No FileKey available][X]'

                    req_key = xrbf.get_requestkey(ctx.obj.dlb._mainkey).encode()
                    req_key = f'[W0b]{req_key}[X]'

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

            if force_remote:
                iter_over = box.search_file(sf, cache_preview=False)
            else:
                iter_over = box.search_file(
                    sf, cache_preview=False,
                    fetch_count=fetch_count
                )
            for dlbf in sync_async_gen(iter_over):
                total_bytes += dlbf.size
                current_file_count += 1

                total_formatted = f'[B0b]{format_bytes(total_bytes)}[X]'
                current_file = f'[Y0b]{current_file_count}[X]'

                echo_text = (
                    f'@ Total [W0b]files found [X]({current_file}) '
                    f'size is {total_formatted}({total_bytes})   \r'
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
    '--ignore-file-path', is_flag=True,
    help='If specified, will NOT make folders from file path on download'
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
    '--omit-hmac-check', is_flag=True,
    help='If specified, will omit HMAC check on download'
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
        hide_name, hide_folder, out, ignore_file_path,
        force_remote, redownload, use_slow_download,
        offset, omit_hmac_check, max_workers, max_bytes):
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
        mime str: File MIME type
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
        minor_version int: File minor version
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
        echo('[R0b]Incorrect filters! Make sure to use format filter=value[X]')
    except KeyError as e: # Unknown filters
        echo(f'[R0b]Filter "{e.args[0]}" doesn\'t exists[X]')
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

                    if ignore_file_path:
                        outfile = downloads / file_name
                    else:
                        if hide_folder:
                            file_path = tgbox.tools.make_safe_file_path(tgbox.defaults.DEF_UNK_FOLDER)
                        else:
                            file_path = tgbox.tools.make_safe_file_path(dxbf.file_path)

                        outfile = downloads / file_path / file_name

                    outfile.parent.mkdir(exist_ok=True, parents=True)

                    preview_bytes = dxbf.preview if preview else None

                    if preview_bytes is not None:
                        if preview_bytes == b'':
                            # Drop the '.jpg' preview suffix string
                            file_name = '.'.join(file_name.split('.')[:-1])

                            if force_remote:
                                echo(f'[Y0b]{file_name} doesn\'t have preview. Skipping.[X]')
                            else:
                                echo(
                                    f'[Y0b]{file_name} doesn\'t have preview. Try '
                                     '-r flag. Skipping.[X]'
                                )
                            continue

                        with open(outfile,'wb') as f:
                            f.write(preview_bytes)

                        if show or locate:
                            click.launch(str(outfile), locate)

                        echo(
                            f'[W0b]{file_name}[X] preview downloaded '
                            f'to [W0b]{str(downloads)}[X]')
                    else:
                        if not force_remote: # box is DecryptedLocalBox
                            drbf = tgbox.sync(ctx.obj.drb.get_file(dxbf.id))

                            if not drbf:
                                echo(
                                    f'[Y0b]There is no file with ID={dxbf.id} in '
                                     'RemoteBox. Skipping.[X]'
                                )
                                continue
                            dxbf = drbf

                        write_mode = 'wb'
                        outfile_size = outfile.stat().st_size if outfile.exists() else 0

                        if not redownload and outfile.exists():
                            if outfile_size == dxbf.size:
                                echo(f'[G0b]{str(outfile)} downloaded. Skipping...[X]')
                                continue
                            else:
                                if offset:
                                    echo(
                                       f'[Y0b]{str(outfile)} is partially downloaded and '
                                        'you specified offset. This will corrupt file. Drop the '
                                        'offset or remove file from your computer. Skipping...[X]'
                                    )
                                    continue

                                if outfile_size % 524288: # Remove partially downloaded block
                                    with open(outfile, 'ab') as f:
                                        f.truncate(outfile_size - (outfile_size % 524288))

                                # File is partially downloaded, so we need to fetch left bytes
                                offset, write_mode = outfile.stat().st_size, 'ab+'

                        if offset % 4096 or offset % 524288:
                            echo('[R0b]Offset must be divisible by 4096 and by 524288.[X]')
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

                            offset = offset,
                            use_slow_download = use_slow_download,
                            omit_hmac_check = omit_hmac_check
                        )
                        to_gather_files.append(download_coroutine)

                        if write_mode == 'ab+': # Partially downloaded write
                            offset = 0 # Reset offset for the next files

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
        echo(f'[R0b]There is no file in LocalBox by ID {id}[X]')
    else:
        requestkey = requestkey if not requestkey\
            else tgbox.keys.Key.decode(requestkey)

        sharekey = dlbf.get_sharekey(requestkey)

        if not requestkey:
            echo(
                '\n[R0b]You didn\'t specified requestkey.\n   You '
                'will receive decryption key IN PLAIN[X]\n'
            )
            if not click.confirm('Are you TOTALLY sure?'):
                return
        echo(
            '\nSend this Key to the Box requester:\n'
           f'    [W0b]{sharekey.encode()}[X]\n'
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
    help='If specified, will import all files up to first error'
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
        echo(f'[R0b]There is no file in RemoteBox by ID {id}[X]')

    elif isinstance(erbf, tgbox.api.remote.DecryptedRemoteBoxFile):
        echo(f'[R0b]File ID{id} is already decrypted. Did you mistyped ID?[X]')
    else:
        try:
            key = tgbox.keys.Key.decode(key)
        except tgbox.errors.IncorrectKey:
            echo('[R0b]Specified Key is invalid[X]')
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
            echo(format_dxbf(drbf), nl=False); return drbf

        echo('\n[Y0b]Searching for files to import[X]...')

        # Import first found EncryptedRemoteBoxFile
        if not tgbox.sync(_import_wrap(erbf)):
            echo('[R0b]Can not decrypt. Specified Key is invalid[X]')
            return

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
        echo(f'ID of last uploaded to [W0b]RemoteBox[X] file is [Y0b]{lfid}[X]')
    else:
        lfid = tgbox.sync(ctx.obj.dlb.get_last_file_id())
        echo(f'ID of last saved to [W0b]LocalBox[X] file is [Y0b]{lfid}[X]')


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
@click.option(
    '--remove-empty-directories','-e', is_flag=True,
    help='If specified, will remove Directory of file If empty'
)
@click.pass_context
def file_remove(
        ctx, filters, local_only, ask_before_remove,
        remove_empty_directories):
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
        mime str: File MIME type
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
        minor_version int: File minor version
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
        echo('[R0b]Incorrect filters! Make sure to use format filter=value[X]')
    except KeyError as e: # Unknown filters
        echo(f'[R0b]Filter "{e.args[0]}" doesn\'t exists[X]')
    else:
        if not filters:
            echo(
                '\n[R0b]You didn\'t specified any search filter.\n   This '
                'will [X]REMOVE ALL FILES[W0b] in your Box[X]\n'
            )
            if not click.confirm('Are you TOTALLY sure?'):
                return

        to_remove = ctx.obj.dlb.search_file(sf, cache_preview=False)

        if ask_before_remove:
            for dlbf in sync_async_gen(to_remove):
                file_path = str(Path(dlbf.file_path) / dlbf.file_name)
                echo(f'@ [R0b]Removing[X] [W0b]Box[X]({file_path})')

                while True:
                    echo('')
                    choice = click.prompt(
                        'Are you TOTALLY sure? ([y]es | [n]o | [i]nfo | [e]xit)'
                    )
                    if choice.lower() in ('yes','y'):
                        tgbox.sync(dlbf.delete(remove_empty_directories=\
                            remove_empty_directories))

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
                        echo('[R0b]Invalid choice, try again[X]')
        else:
            echo('\n[Y0b]Searching for LocalBox files[X]...')
            to_remove = [dlbf for dlbf in sync_async_gen(to_remove)]

            if not to_remove:
                echo('[Y0b]No files to remove was found.[X]')
            else:
                echo(f'[W0b]Removing[X] [R0b]{len(to_remove)}[X] [W0b]files[X]...')

                delete_files = ctx.obj.dlb.delete_files(
                    *to_remove, rb=(None if local_only else ctx.obj.drb),
                    remove_empty_directories=remove_empty_directories
                )
                tgbox.sync(delete_files)

                echo('[G0b]Done.[X]')

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
        mime str: File MIME type
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
        minor_version int: File minor version
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
        echo('[R0b]Incorrect filters! Make sure to use format filter=value[X]')
    except KeyError as e: # Unknown filters
        echo(f'[R0b]Filter "{e.args[0]}" doesn\'t exists[X]')
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
        mime str: File MIME type
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
        minor_version int: File minor version
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
            '\n[R0b]You didn\'t specified any filter.\n   This '
            'will forward EVERY file from your Box[X]\n'
        )
        if not click.confirm('Are you TOTALLY sure?'):
            return
    try:
        sf = filters_to_searchfilter(filters)
    except IndexError: # Incorrect filters format
        echo('[R0b]Incorrect filters! Make sure to use format filter=value[X]')
    except KeyError as e: # Unknown filters
        echo(f'[R0b]Filter "{e.args[0]}" doesn\'t exists[X]')
    else:
        try:
            chat_name = chat
            chat = tgbox.sync(ctx.obj.account.get_entity(chat))
        except (UsernameNotOccupiedError, UsernameInvalidError, ValueError):
            if not chat_is_name:
                echo(f'[Y0b]Can\'t find specified chat "{chat}"[X]')
                return

            for dialogue in sync_async_gen(ctx.obj.account.iter_dialogs()):
                if chat in dialogue.title and dialogue.is_channel:
                    chat_name = dialogue.title.split(': ',1)[-1]
                    chat = dialogue; break
            else:
                echo(f'[Y0b]Can\'t find specified chat "{chat}"[X]')
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
                echo(f'[G0b]ID{dlbf.id}: {dlbf.file_name}: was forwarded to {chat_name}[X]')

        echo('[Y0b]\nSearching files to forward...[X]\n')

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
        mime str: File MIME type
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
        minor_version int: File minor version
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
        echo('[R0b]Incorrect filters! Make sure to use format filter=value[X]')
    except KeyError as e: # Unknown filters
        echo(f'[R0b]Filter "{e.args[0]}" doesn\'t exists[X]')
    else:
        if not filters:
            echo(
                '\n[R0b]You didn\'t specified any search filter.\n   This '
                'will [X]change attrs for all files[W0b] in your Box[X]\n'
            )
            if not click.confirm('Are you TOTALLY sure?'):
                return

        attr_key, attr_value = attribute.split('=',1)

        if attr_key == 'cattrs' and not attr_value:
            changes = {}

        elif attr_key == 'cattrs':
            attr_value = parse_str_cattrs(attr_value)
            changes = {attr_key: tgbox.tools.PackedAttributes.pack(**attr_value)}
        else:
            changes = {attr_key: attr_value.encode()}

        to_change = ctx.obj.dlb.search_file(sf, cache_preview=False)

        dxbf_to_update = []

        UPDATE_WHEN = 200 if not local_only else 100
        TIMEOUT = 15 if not local_only else 0

        async def _update_dxbf(dxbf_id, box):
            dlbf = await ctx.obj.dlb.get_file(dxbf_id)
            original_file_name = dlbf.file_name
            try:
                if isinstance(box, tgbox.api.local.DecryptedLocalBox):
                    await dlbf.update_metadata(changes=changes, dlb=box)
                    prefix = '[LB Only]'
                else:
                    await dlbf.update_metadata(changes=changes, drb=box)
                    prefix = '[LB & RB]'

                echo(
                    f'[X1b]{prefix}[X] ([W0b]{dlbf.id}[X]) {original_file_name} '
                    f'<= [Y0b]{attribute}[X]')
            except tgbox.errors.FingerprintExists:
                echo(
                    f'[X1b]{prefix}[X] ([R1b]{dlbf.id}[X]) {original_file_name} '
                    f'X= [R1b]{attribute}[X]. [R1]Fingerprint exists[X].')


        box = ctx.obj.dlb if local_only else ctx.obj.drb

        for dlbf in sync_async_gen(to_change):
            dxbf_to_update.append(_update_dxbf(dlbf.id, box))

            if len(dxbf_to_update) == UPDATE_WHEN:
                tgbox.sync(gather(*dxbf_to_update))
                dxbf_to_update.clear()
                sleep(TIMEOUT)

        if dxbf_to_update:
            tgbox.sync(gather(*dxbf_to_update))
            dxbf_to_update.clear()

# ========================================================= #
# = LocalBox directory management commands ================ #

@cli.command()
@click.option(
    '--cleanup','-c', is_flag=True,
    help='If specified, will remove ALL orphaned folders'
)
@click.option(
    '--show-box-chat','-s', is_flag=True,
    help='If specified, will show Box Chat dirs (if any)'
)
@ctx_require(dlb=True)
def dir_list(ctx, cleanup, show_box_chat):
    """List all directories in LocalBox"""

    if cleanup:
        echo('\n[W0b]@ Cleanup in process, please wait...[X]')
        tgbox.sync(ctx.obj.dlb.remove_empty_directories())
        echo('[G0b]Done.[X]\n')

    dirs = ctx.obj.dlb.contents(ignore_files=True)

    for dir in sync_async_gen(dirs):
        tgbox.sync(dir.lload(full=True))

        if str(dir.parts[0]) == '__BOX_CHAT__' and not show_box_chat:
            continue

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
        echo(f'[R0b]There is no dir "{directory}" in LocalBox.[X]')
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
        echo(f'[R0b]There is no dir "{directory}" in LocalBox.[X]')
    else:
        requestkey = requestkey if not requestkey \
            else tgbox.keys.Key.decode(requestkey)

        sharekey = dlbd.get_sharekey(requestkey)

        if not requestkey:
            echo(
                '\n[R0b]You didn\'t specified requestkey.\n   You '
                'will receive decryption key IN PLAIN[X]\n'
            )
            if not click.confirm('Are you TOTALLY sure?'):
                return
        echo(
            '\nSend this Key to the Box requester:\n'
            f'    [W0b]{sharekey.encode()}[X]\n'
        )

# ========================================================= #
# = Chat commands ========================================= #

@cli.command()
@click.option(
    '--topic', '-t', default='Main',
    help='Chat topic (Folder-like)'
)
@click.option(
    '--current-date', '-d',
    help='Date (format %Y/%m/%d) from which we will fetch messages'
)
@click.option(
    '--auto-mode-wait', '-w', type=click.IntRange(3, None), default=10,
    help='Seconds of Sleep before fetching Chat Updates'
)
@click.option(
    '--less-data', '-l', is_flag=True,
    help='If specified, will use less network traffic'
)
@ctx_require(dlb=True, drb=True)
def chat_open(ctx, topic, current_date, auto_mode_wait, less_data):
    """
    Launch simple Chat inside your Box

    For correctly attributing messages to Chat members
    You are recommended to enable "Sign Messages" and
    then "Show author's profiles" in your Box Channel
    settings. This command will ask you for this.

    By default Chat will fetch files from the RemoteBox
    and make Fast Sync to cache new messages. With the
    `--less-data` flag Chat will get messages from Local
    instead of Remote. This should be faster and unload
    some network usage BUT it will be impossible to know
    ACTUAL message sender if "Show author's profiles"
    option is enabled in Channel, as we will get it from
    the File (Message) CAttrs, and they can be forged.

    Verified messages have checkmark ("√") in "Author"
    field, unverified will have red "x" symbol.
    """
    chat_dir = tgbox.sync(ctx.obj.dlb.get_directory('__BOX_CHAT__'))
    if not chat_dir:
        sync_ask = colorize(
            '[W0b]@ Currently we don\'t know about Chat in this Box. Did '
            'you tried[X] [C0b]box-sync[X][W0b]? If[X] [G1b]YES[X] [W0b]'
            'and you want to create it, type [X][G1b]Y[X][W0b]. If[X] '
            '[R1b]NO[X][W0b], type[X] [R1b]N[X][W0b] and try sync.[X]'
        )
        echo(f'\n{break_string(sync_ask, 2)}\n')

        if not click.confirm('Type your choice and press Enter'):
            return

        echo('\n[W1]% We need to configure Box chat firstly..[X]')

        author_ask = colorize(
            '[W0b]@ To correctly verify and assign messages to authors we '
            'need to enable "Sign Messages" -> "Show author\'s profiles" '
            'in Box Channel settings. Please note that this will[X] '
            '[Y1b]deanonimize your profile in Channel[X]. [W0b]Are you '
            'OK with this? Type[X] [G1b]Y[X] [W0b]if[X] [G1b]yes[X], '
            '[W0b]type[W0b] [R1b]N[X] [W0b]otherwise[X].'
        )
        echo(f'\n{break_string(author_ask, 2)}\n')

        enable_profiles = click.confirm('Type your choice and press Enter')

        if enable_profiles:
            author_files = tgbox.sync(ctx.obj.drb.author_files(True))

            if author_files is False: # Not enough rights
                no_rights = colorize(
                    '[R1b]x You don\'t have enough rights to toggle '
                    'this parameter. Ask for them or Skip.[X]'
                )
                echo(f'\n{break_string(no_rights, 2)}')
        else:
            skip = colorize(
                '\n[Y1b]% Okay, skip! You can always toggle "Show authors '
                'profile\'s" in Box Channel settings within Telegram![X]'
            )
            echo(f'\n{break_string(skip, 2)}')

        echo('')
        chat_name = click.prompt('Chat name')
        description = click.prompt('Chat description', default='No Description.')

        echo('\n[W0b]@ Uploading configuration...[X]\n')

        file = BytesIO(b'')
        file.name = 'MAIN'

        config_pf = ctx.obj.dlb.prepare_file(
            file = file,
            file_path = str(Path('__BOX_CHAT__', '__CONFIG__', 'CONFIG')),
            cattrs = {
                'name': chat_name.encode(),
                'description': description.encode()
            },
            make_preview = False,
            file_size = 0
        )
        config_pf = tgbox.sync(config_pf)
        tgbox.sync(ctx.obj.drb.push_file(config_pf))

    config = ctx.obj.dlb.search_file(sf=tgbox.tools.SearchFilter(
        scope=str(Path('__BOX_CHAT__', '__CONFIG__')))
    )
    try:
        config = tgbox.sync(tgbox.tools.anext(config))
    except StopAsyncIteration:
        no_config = colorize(
            '[W0b]@ It seems that there is already Chat folder on '
            'your Box, but it does not have CONFIG. Did you tried[X] '
            '[C0b]box-sync[X][W0b]? If yes, and [X][R0b]you want to erase ALL '
            'old Chat data[X][W0b] type[X] [G1b]Y[X][W0b], otherwise '
            'type [X][R1b]N[X]'
        )
        echo(f'\n{break_string(no_config, 2)}\n')

        if not click.confirm('Do you want to erase old Chat data and make new?'):
            skip = colorize(
                '[Y1b]% Okay, skip! You can also use "dir-list --cleanup '
                '--show-box-chat" several times to remove "__BOX_CHAT__" '
                'directory.[X]'
            )
            echo(f'\n{break_string(skip, 2)}\n')
            return

        else:
            echo('\n[W0b]@ Removing Chat messages (If any)[X]')

            ctx.invoke(file_remove,
                filters=("scope=__BOX_CHAT__",),
                local_only=True,
                remove_empty_directories=True
            )
            echo('\n[W0b]@ Removing Chat Directory[X]\n')
            tgbox.sync(chat_dir.delete())

            echo('[G0b]Done.[X] [W0b]Run chat-open again![X]\n')

        return

    chat_name = config.cattrs['name'].decode()
    description = config.cattrs['description'].decode()

    auto_mode, warning_shown = False, False
    clear_console()
    while True:
        try:
            if current_date is None:
                current_date = datetime.fromtimestamp(datetime.now().timestamp())
                current_date = current_date.strftime('%Y/%m/%d')
            else:
                if not warning_shown:
                    cd_check = current_date.split('/')

                    if not all((i.isnumeric() for i in cd_check))\
                        or len(cd_check[0]) != 4 or len(cd_check) != 3:
                            echo(
                                '[Y0b]\nYou provided absolute or incorrect Date. '
                                'Sending\nMessages to it will not work as you may expect. '
                                '\nRead Only or Review your --current-date option.[X]'
                            )
                            echo(
                                '\n[W0b]Correct format is "%Y/%m/%d" '
                                '(i.e "2024/02/22")[X]'
                            )
                            click.prompt(
                                '\n@ Press ENTER to Continue (OK)',
                                default='', show_default=False
                            )
                            warning_shown = True
                            clear_console()

            topic = topic.strip('/').strip('\\') or 'Main'
            topic_path = Path('__BOX_CHAT__', '__CHAT__', topic, current_date)

            echo(f'\n# [W0b]Chat {chat_name}[X] ({description})')
            echo(f'# [W0b]Topic/{topic}, Date: {current_date}[X]')

            chat_dir = tgbox.sync(ctx.obj.dlb.get_directory(str(topic_path)))
            if not chat_dir:
                echo('\n[Y0b]@ Chat is currently empty...[X]')
                dxbf_messages = []
            else:
                contents = ctx.obj.dlb.contents(sfpid=chat_dir.part_id)

                dxbf_messages = [
                    dlbf for dlbf in sync_async_gen(contents)
                    if isinstance(dlbf, tgbox.api.local.DecryptedLocalBoxFile)
                ]

            if not less_data:
                drbfi = ctx.obj.drb.files(ids=[dlbf.id for dlbf in dxbf_messages])
                dxbf_messages = reversed([drbf for drbf in sync_async_gen(drbfi)])

            for dxbf in dxbf_messages:
                echo(format_dxbf_message(dxbf))

            if not auto_mode:
                msgcc = '[X1b]' if warning_shown else '[W0b]'
                echo(
                   f'\n{msgcc}1) Send Message;[X] [W0b]2) Auto Update; 3) Exit[X]\n'
                    '[W0b]Press ENTER to Update or Select Mode[X]', nl=False
                )
                mode = click.prompt('', default='', show_default=False)

                if mode == '1':
                    echo('')

                    msg_name = tgbox.tools.prbg(8).hex()
                    message = click.prompt('Message').encode()

                    me = tgbox.sync(ctx.obj.drb.tc.get_me())
                    author = me.username or me.first_name
                    author_id = str(me.id)

                    msg_pf = ctx.obj.dlb.prepare_file(b'',
                        file_path = str(topic_path / msg_name),
                        cattrs = {
                            'text': message,
                            'author': author.encode(),
                            'author_id': author_id.encode()
                        },
                        make_preview = False,
                        file_size = 0
                    )
                    msg_pf = tgbox.sync(msg_pf)
                    tgbox.sync(ctx.obj.drb.push_file(msg_pf))

                elif mode == '2':
                    auto_mode = True

                elif mode == '3':
                    break
                else:
                    tgbox.sync(ctx.obj.dlb.sync(ctx.obj.drb))

            else:
                time = datetime.now().strftime('%d/%m/%y, %H:%M:%S')
                echo(
                    f'\n[W0b]% ({time}) Waiting {auto_mode_wait} '
                    'seconds before Sync...[X]'
                )
                echo('[W0b]@ Press CTRL+C to Return to Input Mode\r[X]', nl=False)

                sleep(auto_mode_wait)

                time = datetime.now().strftime('%d/%m/%y, %H:%M:%S')
                echo(f'[W0b]V ({time}) Syncing your Chat with Fast Sync...[X]')

                tgbox.sync(ctx.obj.dlb.sync(ctx.obj.drb))

        except KeyboardInterrupt:
            auto_mode = False
        finally:
            clear_console()


@cli.command()
@ctx_require(dlb=True, drb=True)
def chat_info(ctx):
    """Show info about Chat on selected Box"""

    chat_dir = tgbox.sync(ctx.obj.dlb.get_directory('__BOX_CHAT__'))

    if not chat_dir:
        echo('\n[Y0b]This Box doesn\'t have Chat yet.[X]\n')
        return

    config = ctx.obj.dlb.search_file(sf=tgbox.tools.SearchFilter(
        scope=str(Path('__BOX_CHAT__', '__CONFIG__')))
    )
    try:
        config = tgbox.sync(tgbox.tools.anext(config))
    except StopAsyncIteration:
        echo('[R0b]\nChat doesn\'t have config!!! Try to reset it, error![X]\n')
        return

    chat_name = config.cattrs['name'].decode()
    description = config.cattrs['description'].decode()

    echo(f'\n# [W0b]Chat {chat_name}[X] ({description})')

    chat_dir = tgbox.sync(ctx.obj.dlb.get_directory(
        str(Path('__BOX_CHAT__', '__CHAT__')))
    )
    if not chat_dir:
        echo('\n[Y0b]This Chat doesn\'t have any Messages yet.[X]\n')
        return

    topics_dict = {}
    topics = ctx.obj.dlb.contents(chat_dir.part_id, ignore_files=True)

    for topic in sync_async_gen(topics):
        tgbox.sync(topic.lload(full=True))

        if len(topic.parts) < 3:
             continue

        if len(topic.parts) == 6:
            topic_path = Path(str(topic)).parts[2:]

            topic = topic_path[0]
            date = '/'.join(topic_path[1:])

            if topic not in topics_dict:
                topics_dict[topic] = []

            topics_dict[topic].append(date)

        for v in topics_dict.values():
            v.sort()

    for k,v in topics_dict.items():
        echo(f'\n[C0b]@ Topic[X] "[W0b]{k}[X]"')

        for date in v:
            date_dir = str(Path('__BOX_CHAT__', '__CHAT__', k, *date.split('/')))

            messages_total = tgbox.sync(ctx.obj.dlb.get_directory(date_dir))
            messages_total = tgbox.sync(messages_total.get_files_total())

            echo(
                f'[W0b]| {date}[X] ([Y0b]'
                f'{messages_total}[X])'
            )
    echo('')

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
    echo('[G0b]Done.[X]')

@cli.command()
def logfile_size():
    """Get bytesize of logfile"""
    size = format_bytes(logfile.stat().st_size)
    echo(f'[W0b]{str(logfile)}[X]: {size}')

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
            '[Y0b]You didn\'t specified any chat! Try'
            '[X] [W0b]tgbox-cli logfile-send me[X]'
        )
    elif not logfile.stat().st_size:
        echo(f'[Y0b]Logfile "{logfile.name}" is empty, so not sent.[X]')
        return

    for e in chat:
        tgbox.sync(ctx.obj.account.send_file(e, logfile))
        echo(f'[W0b]Logfile has been sent to[X] [B0b]{e}[X]')

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

        click.echo_via_pager(colorize(help_text), color=colored)

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
    echo(f'[M0b]{tgbox.keys.Phrase.generate(words)}[X]')

@cli.command(hidden=True)
@click.option(
    '--enable-logging', is_flag=True,
    help='Will enable logging for Python session'
)
@click.option(
    '--execute', help='Path to Python script to execute',
    type=click.Path(readable=True, path_type=Path)
)
@click.option(
    '--non-interactive', is_flag=True,
    help='Will disable interactive console'
)
@click.option(
    '--i-understand-risk', is_flag=True,
    help='Will disable warning prompt'
)
@click.pass_context
def python(ctx, enable_logging, execute, non_interactive, i_understand_risk):
    """Launch interactive Python console"""

    global Objects
    Objects = ctx.obj

    if not enable_logging:
        logging.disable()

    global EXEC_SCRIPT

    if execute:
        # Users are notified about all risks of exec(), so we don't need Warning.
        EXEC_SCRIPT = lambda: exec(open(execute).read()) # pylint: disable=exec-used
    else:
        EXEC_SCRIPT = lambda: None

    if execute and not i_understand_risk:
        echo(
            '\n    [R0b]You are specified some Python script with the --execute option.\n'
            '    Third-party scripts can be useful for some actions that out of\n'
            '    TGBOX-CLI abilities, however, they can do MANY BAD THINGS to your\n'
            '    Telegram account [i.e STEAL IT] (or even to your System [i.e \n'
            '    REMOVE ALL FILES]) if written by ATTACKER. NEVER execute scripts\n'
            '    you DON\'T UNDERSTAND or DON\'T TRUST. NEVER! NEVER! NEVER![X]\n'
        )
        confirm = None
        while confirm != 'YES':
            prompt = (
                'Type [G0b]YES[X] [or [R0b]NO[X]'
                '] if you understand this and want to proceed'
            )
            confirm = click.prompt(colorize(prompt))
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
            echo(f'[R0b]{traceback}[X]')

        elif e.args: # Will echo only if error have message
            echo(f'[R0b]{e}[X]')

        echo(''); exit(1)

if __name__ == '__main__':
    safe_tgbox_cli_startup()
