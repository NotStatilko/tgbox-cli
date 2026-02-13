import click

from asyncio import gather

from ..group import cli_group
from ..helpers import check_ctx
from ...tools.terminal import echo
from ...tools.other import sync_async_gen
from ...tools.convert import filters_to_searchfilter
from ...config import tgbox


@cli_group.command()
@click.argument('filters', nargs=-1)
@click.option(
    '--local-only','-l', is_flag=True,
    help='If specified, will remove file ONLY from LocalBox'
)
@click.option(
    '--directory','-d', help='Directory to move files to'
)
@click.option(
    '--reset-directory','-r', is_flag=True,
    help='If specified, will reset directory to original'
)
@click.pass_context
def file_move(ctx, filters, local_only, directory, reset_directory):
    """
    Move files to another Directory by filters

    \b
    Available filters:\b
        scope: Define a path as search scope
               -----------------------------
               The *scope* is an absolute directory in which
               we will search your file by other filters. By
               default, the tgbox.api.utils.search_generator
               will search over the entire LocalBox. This can
               be slow if you're have too many files.
               \b
               Example: let's imagine that You're a Linux user which
               share it's Box with the Windows user. In this case,
               Your LocalBox will contain a path parts on the
               '/' (Linux) and 'C:\\' (Windows) roots. If You
               know that some file was uploaded by Your friend,
               then You can specify a scope='C:\\' to ignore
               all files uploaded from the Linux machine. This
               will significantly fasten the search process,
               because almost all filters require to select
               row from the LocalBox DB, decrypt Metadata and
               compare its values with ones from SearchFilter.
               \b
               !: The scope will be ignored on RemoteBox search.
               !: The min_id & max_id will be ignored if scope used.
        \b
        id integer: File’s ID
        mime str: File MIME type
        \b
        cattrs: File CAttrs
                -----------
                Can be used hexed PackedAttributes
                or special CLI format alternatively:
                cattrs="comment:test type:message"
        \b
        file_path str: File path
        file_name str: File name
        file_salt str: File salt
        \b
        min_id integer: File ID should be > min_id
        max_id integer: File ID should be < max_id
        \b
        min_size integer/str: File Size should be > min_size
        max_size integer/str: File Size should be < max_size
        +
        min_size & max_size can be also specified as string,
            i.e "1GB" (one gigabyte), "122.45KB" or "700B"
        \b
        min_time integer/float/str: Upload Time should be > min_time
        max_time integer/float/str: Upload Time should be < max_time
        +
        min_time & max_time can be also specified as string,
            i.e "22/02/22, 22:22:22" or "22/02/22"
               ("%d/%m/%y, %H:%M:%S" or "%d/%m/%y")
        \b
        minor_version int: File minor version
        imported bool: Yield only imported files
        re       bool: Regex search for every str filter
        \b
        non_recursive_scope bool: Ignore scope subdirectories
    \b
    See tgbox.readthedocs.io/en/indev/
        tgbox.html#tgbox.tools.SearchFilter
    \b
    You can also use special flags to specify
    that filters is for include or exclude search.
    \b
    Example:\b
        tgbox-cli file-move scope=/home/user/Downloads/MP3\b
            --directory /home/user/Music/MP3
    """
    if local_only:
        check_ctx(ctx, dlb=True)
    else:
        check_ctx(ctx, dlb=True, drb=True)
    try:
        sf = filters_to_searchfilter(filters)
    except IndexError: # Incorrect filters format
        echo('[R0b]Incorrect filters! Make sure to use format filter=value[X]')
        return
    except KeyError as e: # Unknown filters
        echo(f'[R0b]Filter "{e.args[0]}" doesn\'t exists[X]')
        return

    if not filters:
        echo('\n[R0b]You didn\'t specified any search filter.[X]')
        return

    if not directory and not reset_directory:
        directory = click.prompt('Please enter Directory to move')

    to_move = ctx.obj.dlb.search_file(sf, cache_preview=False)

    echo(f'\n@ Moving files... \r', nl=False)
    coros, total_processed = [], 0

    for dlbf in sync_async_gen(to_move):
        if len(coros) == 100:
            if len(coros) == 100:
                processed = tgbox.sync(gather(*coros))
                total_processed += len(tuple(r for r in processed if r == True))
                coros.clear()
                echo(f'@ Moving files... ([Y0b]{total_processed}[X])\r', nl=False)

        if reset_directory or str(directory) == str(dlbf._original_file_path):
            directory = None # Same as original

        elif str(directory) == str(dlbf._file_path):
                echo(
                   f'[Y0b]| Can not move [W0b]{dlbf.file_name}[X][W0]'
                   f'(ID {dlbf.id})[X] to[X] [W0b]{directory}[X] [Y0]'
                   '(Already in this Directory)[X]'
                )
                continue
        else:
            directory = str(directory).encode()

        async def update_metadata(dlbf, directory):
            try:
                await dlbf.update_metadata(
                    changes = {'file_path': directory},
                    drb = None if local_only else ctx.obj.drb
                )
                return True
            except tgbox.errors.FingerprintExists:
                if not reset_directory:
                    if directory is None:
                        directory_i = '<original dir>'
                    else:
                        directory_i = directory
                    echo(
                       f'[R0b]x Can not move [W0b]{dlbf.file_name}[X][W0]'
                       f'(ID {dlbf.id})[X] to[X] [W0b]{directory_i}[X] [R0]'
                       '(There is already file with same name)[X]'
                    )

        coros.append(update_metadata(dlbf, directory))

    if coros:
        processed = tgbox.sync(gather(*coros))
        total_processed += len(tuple(r for r in processed if r == True))

    if not total_processed:
        echo('@ [Y0b]No files to move under your filters[X]')
    else:
        file = 'file' if total_processed == 1 else 'files'
        echo(f'@ [G0b]{total_processed}[X] {file} moved [W0b]successfully![X]')

    echo('')
