"""
This module contains main click CLI object which
will be used to connect all commands; as well
as some helpers for it
"""

import click

from pathlib import Path
from inspect import isfunction
from os import getenv, system as os_system
from shutil import get_terminal_size
from enlighten import get_manager as get_enlighten_manager

from .helpers import Objects
from ..tools.terminal import colorize
from ..tools.session import Session
from ..tools.convert import env_proxy_to_pysocks
from ..config import tgbox, TGBOX_CLI_NOCOLOR, API_ID, API_HASH


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
def cli_group(ctx):
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
            #       strange cases it leaves a CMD in a broken state. As
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
