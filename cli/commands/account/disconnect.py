import click

from ..group import cli_group
from ..helpers import ctx_require
from ...config import tgbox, API_ID, API_HASH
from ...tools.terminal import echo


@cli_group.command()
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

