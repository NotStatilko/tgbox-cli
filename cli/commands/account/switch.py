import click

from ..group import cli_group
from ..helpers import ctx_require
from ...tools.terminal import echo
from ...config import tgbox, API_ID, API_HASH


@cli_group.command()
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
