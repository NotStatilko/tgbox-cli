import click

from asyncio import gather

from ..group import cli_group
from ..helpers import check_ctx
from ...tools.terminal import echo
from ...tools.other import sync_async_gen
from ...config import tgbox


@cli_group.command()
@click.argument('source_target', nargs=2)
@click.option(
    '--local-only','-l', is_flag=True,
    help='If specified, will move files ONLY in LocalBox'
)
@click.pass_context
def dir_rename(ctx, source_target, local_only):
    """
    Rename Directory and move files under it

    \b
    Please note that we will NOT resolve conflicts here. If
    your Source has files with same names as in Target, you
    will receive error. You should rename files in Source
    manually before using this command.
    \b
    Example:\b
        tgbox-cli dir-rename /home/user/Downloads/Rock \ \b
            /home/user/Music/Rock
    """
    if local_only:
        check_ctx(ctx, dlb=True)
    else:
        check_ctx(ctx, dlb=True, drb=True)

    from_ = str(tgbox.tools.make_general_path(source_target[0]))
    to = tgbox.tools.make_general_path(source_target[1])

    if from_ == str(to):
        echo('[R0b]x Paths are the same.[X]')
        return

    if not (directory := tgbox.sync(ctx.obj.dlb.get_directory(from_))):
        echo(f'[R0b]x Directory[X] [W0b]{from_}[X] [R0b]is not found.[X]')
        return

    echo(f'\n@ Moving files... \r', nl=False)
    coros, total_processed = [], 0

    for dlbf in sync_async_gen(ctx.obj.dlb.contents(directory.part_id)):
        if len(coros) == 100:
            tgbox.sync(gather(*coros))
            total_processed += len(coros)
            coros.clear()
            echo(f'@ Moving files... ([Y0b]{total_processed}[X])\r', nl=False)

        if isinstance(dlbf, tgbox.api.local.DecryptedLocalBoxDirectory):
            continue

        if (dest_path := str(dlbf.file_path).removeprefix(from_)):
            dest_path = tgbox.tools.make_general_path(dest_path)

            if dest_path.parts[0] in ('/', '\\'):
                dest_path = type(dest_path)(*dest_path.parts[1:])

            dest_path = to / dest_path
        else:
            dest_path = to

        if str(dest_path) == str(dlbf._original_file_path):
            new_path = None # Same as original
        else:
            new_path = str(dest_path).encode()

        coro = dlbf.update_metadata(
            changes = {'file_path': new_path},
            drb = None if local_only else ctx.obj.drb
        )
        coros.append(coro)

    if coros:
        tgbox.sync(gather(*coros))
        total_processed += len(coros)

    if not total_processed:
        echo(f'@ [Y0b]No files to move under[X] [W0b]{from_}[X]')
    else:
        echo(f'@ [G0b]{total_processed}[X] files moved [W0b]successfully![X]')
