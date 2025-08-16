import click

from ..group import cli_group
from ..helpers import ctx_require
from ...tools.terminal import echo
from ...tools.other import sync_async_gen
from ...config import tgbox


@cli_group.command()
@click.option(
    '--cleanup','-c', is_flag=True,
    help='If specified, will remove ALL orphaned folders'
)
@click.option(
    '--show-box-chat','-s', is_flag=True,
    help='If specified, will show Box Chat dirs (if any)'
)
@ctx_require(dlb=True)
def dir_list(ctx, cleanup, show_box_chat):
    """List all directories in LocalBox"""

    if cleanup:
        echo('\n[W0b]@ Cleanup in process, please wait...[X]')
        tgbox.sync(ctx.obj.dlb.remove_empty_directories())
        echo('[G0b]Done.[X]\n')

    dirs = ctx.obj.dlb.contents(ignore_files=True)

    for dir in sync_async_gen(dirs):
        tgbox.sync(dir.lload(full=True))

        if str(dir.parts[0]) == '__BOX_CHAT__' and not show_box_chat:
            continue

        echo(str(dir))
