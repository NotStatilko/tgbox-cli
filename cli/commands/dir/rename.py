import click

from asyncio import gather

from ..group import cli_group
from ..helpers import check_ctx
from ...tools.terminal import echo
from ...tools.other import sync_async_gen
from ...config import tgbox


@cli_group.command()
@click.argument('source_target', nargs=-1)
@click.option(
    '--local-only','-l', is_flag=True,
    help='If specified, will move files ONLY in LocalBox'
)
@click.option(
    '--reset-directory','-r', is_flag=True,
    help='If specified, will reset directory to original'
)
@click.pass_context
def dir_rename(ctx, source_target, local_only, reset_directory):
    """
    Rename Directory and move files under it

    \b
    Please note that we will NOT resolve conflicts here. If
    your Source has files with same names as in Target, you
    will receive error. You should rename files in Source
    manually before using this command.
    \b
    Example:\b
        tgbox-cli dir-rename /home/user/Downloads/Rock\b
            /home/user/Music/Rock
    """
    if local_only:
        check_ctx(ctx, dlb=True)
    else:
        check_ctx(ctx, dlb=True, drb=True)

    if not source_target:
        echo(
            '[R0b]x You should specify[X] [W0b]/source/path[X] '
            '[R0b]and[X] [W0b]/target/path[X]')
        return

    if len(source_target) == 1 and not reset_directory:
        echo(
            '[R0b]x You should specify[X] [W0b]/target/path[W0b] '
            '[R0b]or[X] [G0b]--reset-directory[X]')
        return

    from_ = str(tgbox.tools.make_general_path(source_target[0]))

    if not reset_directory:
        to = tgbox.tools.make_general_path(source_target[1])

        if from_ == str(to):
            echo('\n[Y0b]x Paths are the same.[X]\n')
            return

    if not (directory := tgbox.sync(ctx.obj.dlb.get_directory(from_))):
        echo(f'\n[Y0b]x Directory[X] [W0b]{from_}[X] [Y0b]is not found.[X]\n')
        return

    echo(f'\n@ Moving files... \r', nl=False)
    coros, total_processed = [], 0

    for dlbf in sync_async_gen(ctx.obj.dlb.contents(directory.part_id)):
        if len(coros) == 100:
            processed = tgbox.sync(gather(*coros))
            total_processed += len(tuple(r for r in processed if r == True))
            coros.clear()
            echo(f'@ Moving files... ([Y0b]{total_processed}[X])\r', nl=False)

        if isinstance(dlbf, tgbox.api.local.DecryptedLocalBoxDirectory):
            continue

        if not reset_directory:
            if (dest_path := str(dlbf.file_path).removeprefix(from_)):
                dest_path = tgbox.tools.make_general_path(dest_path)

                if dest_path.parts[0] in ('/', '\\'):
                    dest_path = type(dest_path)(*dest_path.parts[1:])

                dest_path = to / dest_path
            else:
                dest_path = to

        if reset_directory or str(dest_path) == str(dlbf._original_file_path):
            new_path = None # Same as original

        elif str(dest_path) == str(dlbf._file_path):
            echo(
               f'[Y0b]| Can not move [W0b]{dlbf.file_name}[X][W0]'
               f'(ID {dlbf.id})[X] to[X] [W0b]{directory}[X] [Y0]'
               '(Already in this Directory)[X]'
            )
            continue
        else:
            new_path = str(dest_path).encode()

        async def update_metadata(dlbf, new_path):
            try:
                await dlbf.update_metadata(
                    changes = {'file_path': new_path},
                    drb = None if local_only else ctx.obj.drb
                )
                return True
            except tgbox.errors.FingerprintExists:
                if new_path is None:
                    new_path_i = '<original dir>'
                else:
                    new_path_i = new_path.decode()

                echo(
                   f'[R0b]x Can not move [W0b]{dlbf.file_name}[X][W0]'
                   f'(ID {dlbf.id})[X] to[X] [W0b]{new_path_i}[X] [R0]'
                   '(There is already file with same name)[X]'
                )

        coros.append(update_metadata(dlbf, new_path))

    if coros:
        processed = tgbox.sync(gather(*coros))
        total_processed += len(tuple(r for r in processed if r == True))

    if not total_processed:
        echo(f'@ [Y0b]No files to move under[X] [W0b]{from_}[X]')
    else:
        echo(f'@ [G0b]{total_processed}[X] files moved [W0b]successfully![X]')

    echo('')
