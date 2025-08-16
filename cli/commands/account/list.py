import click

from ..group import cli_group
from ..helpers import ctx_require
from ...tools.terminal import echo
from ...config import tgbox, API_ID, API_HASH


@cli_group.command()
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
