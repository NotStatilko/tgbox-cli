import click

from ..group import cli_group
from ..helpers import ctx_require
from ...config import tgbox, API_ID, API_HASH, TGBOX_CLI_SHOW_PASSWORD
from ...tools.terminal import echo


@cli_group.command()
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
