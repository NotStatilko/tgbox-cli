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
    '--directory', '-d', required=True, prompt=True,
    help='Absolute path of Directory to share'
)
@ctx_require(dlb=True)
def dir_share(ctx, requestkey, directory):
    """Get a ShareKey from RequestKey to share dir"""

    dlbd = tgbox.sync(ctx.obj.dlb.get_directory(directory.strip()))

    if not dlbd:
        echo(f'[R0b]There is no dir "{directory}" in LocalBox.[X]')
    else:
        requestkey = requestkey if not requestkey \
            else tgbox.keys.Key.decode(requestkey)

        sharekey = dlbd.get_sharekey(requestkey)

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
