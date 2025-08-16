import click

from ..group import cli_group
from ..helpers import ctx_require
from ...tools.terminal import echo
from ...config import tgbox, LOGFILE


@cli_group.command()
@click.argument('chat', nargs=-1)
@ctx_require(account=True)
def logfile_send(ctx, chat):
    """
    Send logfile to Telegram chat

    \b
    Example:\b
        tgbox-cli logfile-send @username
    """
    if not LOGFILE:
        echo('[R0b]Logfile is impossible to send[X]')
        return

    if not chat:
        echo(
            '[Y0b]You didn\'t specified any chat! Try'
            '[X] [W0b]tgbox-cli logfile-send me[X]')
        return

    if not LOGFILE.stat().st_size:
        echo(f'[Y0b]Logfile "{LOGFILE.name}" is empty, so not sent.[X]')
        return

    for e in chat:
        tgbox.sync(ctx.obj.account.send_file(e, LOGFILE))
        echo(f'[W0b]Logfile has been sent to[X] [B0b]{e}[X]')
