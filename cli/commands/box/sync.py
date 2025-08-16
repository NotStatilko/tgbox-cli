import click

from ..group import cli_group
from ..helpers import ctx_require
from ...tools.terminal import echo, ProgressBar
from ...config import tgbox


@cli_group.command()
@click.option(
    '--start-from-id','-s', default=0,
    help='Will check files that > specified ID'
)
@click.option(
    '--deep','-d', default=False, is_flag=True,
    help='Use a deep Box syncing instead of fast'
)
@click.option(
    '--timeout','-t', default=15,
    help='Sleep timeout per every 1000 file'
)
@ctx_require(dlb=True, drb=True)
def box_sync(ctx, start_from_id, deep, timeout):
    """Synchronize your current LocalBox with RemoteBox

    After this operation, all info about your LocalFiles that are
    not in RemoteBox will be deleted from LocalBox. Files that
    not in LocalBox but in RemoteBox will be imported.

    There is two modes of sync: the Fast and the Deep. The
    "Fast" mode will fetch data from the "Recent Actions"
    Telegram channel admin log. The updates here will stay
    up to 48 hours, so this is the best option. In any other
    case specify a --deep flag to enable the "Deep" sync.

    Deep sync will iterate over each file in Remote and
    Local boxes, then compare them. This may take a
    very long time. You can track state of remote
    with the file-last-id command and specify
    the last file ID of your LocalBox as
    --start-from-id (-s) option here.

    \b
    (!) Please note that to make a fast sync you *need*\b
     |  to have access to the Channel's Admin Log. Ask
     |  the RemoteBox owner to make you Admin with (at
     |  least) zero rights or use a deep synchronization.
     |
    (?) Use tgbox-cli box-info to check your rights.

    (!) --start-from-id can be used only with --deep sync.
    """
    if start_from_id and not deep:
        echo(
            '[W0b]--start-from-id[X] [R0b]can be used only '
            'with[X] [W0b]--deep[X][R0b]![X]'
        ); return

    if not deep:
        progress_callback = lambda i,a: echo(f'* [W0b]ID{i}[X]: [C0b]{a}[X]')
    else:
        progress_callback = ProgressBar(ctx.obj.enlighten_manager,
            'Synchronizing...').update_2

    box_sync_coro = ctx.obj.dlb.sync(
        drb = ctx.obj.drb,
        deep = deep,
        start_from = start_from_id,
        fast_progress_callback = progress_callback,
        deep_progress_callback = progress_callback,
        timeout = timeout
    )
    try:
        tgbox.sync(box_sync_coro)
    except tgbox.errors.RemoteFileNotFound as e:
        echo(f'[R0b]{e}[X]')
    else:
        echo('[G0b]Syncing complete.[X]')
