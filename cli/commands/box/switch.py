import click

from ..group import cli_group
from ...tools.terminal import echo
from ..helpers import ctx_require

@cli_group.command()
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
