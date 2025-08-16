import click

from ..group import cli_group
from ..helpers import ctx_require
from ...tools.terminal import echo
from ...config import tgbox


@cli_group.command()
@click.option(
    '--requestkey', '-r',
    help='Requester\'s RequestKey'
)
@click.option(
    '--id', required=True, type=int,
    help='ID of file to share'
)
@click.option(
    '--directory', '-d', required=True, prompt=True,
    help='Absolute path of Directory to share'
)
@ctx_require(dlb=True)
def file_share(ctx, requestkey, id):
    """Get a ShareKey from RequestKey to share file"""

    dlbf = tgbox.sync(ctx.obj.dlb.get_file(id=id))

    if not dlbf:
        echo(f'[R0b]There is no file in LocalBox by ID {id}[X]')
    else:
        requestkey = requestkey if not requestkey\
            else tgbox.keys.Key.decode(requestkey)

        sharekey = dlbf.get_sharekey(requestkey)

        if not requestkey:
            echo(
                '\n[R0b]You didn\'t specified requestkey.\n   You '
                'will receive decryption key IN PLAIN[X]\n'
            )
            if not click.confirm('Are you TOTALLY sure?'):
                return
        echo(
            '\nSend this Key to the Box requester:\n'
           f'    [W0b]{sharekey.encode()}[X]\n'
        )
