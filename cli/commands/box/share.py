import click

from ..group import cli_group
from ...tools.terminal import echo
from ..helpers import ctx_require
from ...config import tgbox


@cli_group.command()
@click.option(
    '--requestkey', '-r',
    help='Requester\'s RequestKey, by box-request command'
)
@ctx_require(dlb=True)
def box_share(ctx, requestkey):
    """Command to make ShareKey & to share Box"""

    requestkey = requestkey if not requestkey\
        else tgbox.keys.Key.decode(requestkey)

    sharekey = ctx.obj.dlb.get_sharekey(requestkey)

    if not requestkey:
        echo(
            '\n[R0b]You didn\'t specified requestkey.\n   You '
            'will receive decryption key IN PLAIN\n[X]'
        )
        if not click.confirm('Are you TOTALLY sure?'):
            return
    echo(
        '\nSend this Key to the Box requester:\n'
       f'    [W0b]{sharekey.encode()}[X]\n'
    )
