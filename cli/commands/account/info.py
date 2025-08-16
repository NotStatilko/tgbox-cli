import click

from ..group import cli_group
from ..helpers import ctx_require
from ...tools.terminal import echo
from ...config import tgbox


@cli_group.command()
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

