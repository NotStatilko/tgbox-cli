import click

from ..group import cli_group
from ..helpers import check_ctx
from ...tools.terminal import echo
from ...config import tgbox


@cli_group.command()
@click.option(
    '--remote','-r', is_flag=True,
    help='If specified, will return ID of last file on RemoteBox'
)
@click.pass_context
def file_last_id(ctx, remote):
    """Return ID of last uploaded to Box file"""

    check_ctx(ctx, dlb=True, drb=remote)

    if remote:
        lfid = tgbox.sync(ctx.obj.drb.get_last_file_id())
        echo(f'ID of last uploaded to [W0b]RemoteBox[X] file is [Y0b]{lfid}[X]')
    else:
        lfid = tgbox.sync(ctx.obj.dlb.get_last_file_id())
        echo(f'ID of last saved to [W0b]LocalBox[X] file is [Y0b]{lfid}[X]')
