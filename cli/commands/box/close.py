import click

from ..group import cli_group
from ..helpers import ctx_require
from ...tools.terminal import echo


@cli_group.command()
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
