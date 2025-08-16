import click

from ..group import cli_group
from ..helpers import ctx_require
from ...tools.terminal import echo
from ...config import tgbox, API_ID, API_HASH


@cli_group.command()
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
