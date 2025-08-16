import click

from ..group import cli_group
from ..helpers import ctx_require
from ..file.forward import file_forward
from ...tools.terminal import echo
from ...config import tgbox


@cli_group.command()
@click.option(
    '--directory', '-d', required=True, prompt=True,
    help='Absolute path of Directory to forward'
)
@click.option(
    '--chat', '-c', required=True, prompt=True,
    help='Chat to send file to'
)
@click.option(
    '--chat-is-name', is_flag=True,
    help='Interpret --chat as Chat name and search for it'
)
@ctx_require(dlb=True, drb=True, account=True)
def dir_forward(ctx, directory, chat, chat_is_name):
    """
    Forward files from dir to specified chat
    """
    dlbd = tgbox.sync(ctx.obj.dlb.get_directory(directory.strip()))

    if not dlbd:
        echo(f'[R0b]There is no dir "{directory}" in LocalBox.[X]')
    else:
        filters = [f'scope={directory}', 'non_recursive_scope=True']
        ctx.invoke(file_forward, filters=filters, chat=chat, chat_is_name=chat_is_name)
