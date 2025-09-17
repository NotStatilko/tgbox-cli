"""This module contains some helpers for CLI"""

import click

from functools import wraps
from inspect import iscoroutine, isfunction

from .errors import CheckCTXFailed
from ..tools.terminal import echo
from ..tools.other import sync_async_gen
from ..config import tgbox


class Objects:
    """
    This class will be used inside the group.py:cli_group()
    function to keep track of DLB/DRB as well as lazy-load
    DRB (if it's not necessary). We will access them inside
    the actual commands from CTX, as ctx.obj.
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
            # pylint: disable=pointless-statement
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

@ctx_require(account=True)
def select_remotebox(ctx, number: int, prefix: str):
    """
    This function will be used for searching all
    RemoteBox objects on User account
    """
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
