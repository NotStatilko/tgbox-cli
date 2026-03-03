import click

from pathlib import Path

from ..group import cli_group
from ..helpers import check_ctx
from ...tools.terminal import echo
from ...tools.other import format_dxbf, sync_async_gen
from ...tools.convert import filters_to_searchfilter
from ...config import tgbox


@cli_group.command()
@click.argument('filters', nargs=-1)
@click.option(
    '--local-only','-l', is_flag=True,
    help='If specified, will remove file ONLY from LocalBox'
)
@click.option(
    '--ask-before-remove','-a', is_flag=True,
    help='If specified, will ask "Are you sure?" for each file'
)
@click.option(
    '--remove-empty-directories','-e', is_flag=True,
    help='If specified, will remove Directory of file If empty'
)
@click.option(
    '--force', is_flag=True,
    help='If specified, will not ask for confirmation'
)
@click.option(
    '--remote','-r', is_flag=True,
    help='If specified, will search for files in RemoteBox'
)
@click.pass_context
def file_remove(
        ctx, filters, local_only, ask_before_remove,
        remove_empty_directories, force, remote):
    """Remove files by selected filters

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
        # Include is used by default
        tgbox-cli file-remove min_id=3 max_id=100
        \b
        # Include flag (will ignore unmatched)
        tgbox-cli file-remove +i file_name=.png
        \b
        # Exclude flag (will ignore matched)
        tgbox-cli file-remove +e file_name=.png
        \b
        You can use both, the ++include and
        ++exclude (+i, +e) in one command.
    """
    if local_only:
        check_ctx(ctx, dlb=True)
    else:
        check_ctx(ctx, dlb=True, drb=True)
    try:
        sf = filters_to_searchfilter(filters)
    except IndexError: # Incorrect filters format
        echo('[R0b]Incorrect filters! Make sure to use format filter=value[X]')
    except KeyError as e: # Unknown filters
        echo(f'[R0b]Filter "{e.args[0]}" doesn\'t exists[X]')
    else:
        if not filters and not force:
            echo(
                '\n[R0b]You didn\'t specified any search filter.\n   This '
                'will [X]REMOVE ALL FILES[W0b] in your Box[X]\n'
            )
            if not click.confirm('Are you TOTALLY sure?'):
                return

        if remote:
            to_remove = ctx.obj.drb.search_file(sf, cache_preview=False,
                return_imported_as_erbf=True)
        else:
            to_remove = ctx.obj.dlb.search_file(sf, cache_preview=False)

        if ask_before_remove:
            for dxbf in sync_async_gen(to_remove):
                file_path = str(Path(dxbf.file_path) / dxbf.file_name)
                echo(f'@ [R0b]Removing[X] [W0b]Box[X]({file_path})')

                while True:
                    echo('')
                    choice = click.prompt(
                        'Are you TOTALLY sure? ([y]es | [n]o | [i]nfo | [e]xit)'
                    )
                    if choice.lower() in ('yes','y'):
                        if issubclass(dxbf.__class__, tgbox.api.remote.EncryptedRemoteBoxFile):
                            tgbox.sync(dxbf.delete())
                        else:
                            tgbox.sync(dxbf.delete(remove_empty_directories=\
                                remove_empty_directories))

                        if issubclass(dxbf.__class__, tgbox.api.remote.EncryptedRemoteBoxFile):
                            if (dlbf := tgbox.sync(ctx.obj.dlb.get_file(dxbf.id))):
                                tgbox.sync(dlbf.delete(remove_empty_directories=\
                                    remove_empty_directories))

                        elif not local_only:
                            drbf = tgbox.sync(ctx.obj.drb.get_file(dxbf.id))
                            tgbox.sync(drbf.delete())
                        echo('')
                        break
                    elif choice.lower() in ('no','n'):
                        echo('')
                        break
                    elif choice.lower() in ('info','i'):
                        echo(format_dxbf(dxbf).rstrip())
                    elif choice.lower() in ('exit','e'):
                        return
                    else:
                        echo('[R0b]Invalid choice, try again[X]')
        else:
            box = 'RemoteBox' if remote else 'LocalBox'

            echo(f'\n[Y0b]Searching for any files in your {box}[X]...')
            to_remove = [dxbf for dxbf in sync_async_gen(to_remove)]

            if not to_remove:
                echo(f'[Y0b]No files to remove was found in {box}[X]')
                if not remote:
                    echo('[Y0b]You can use --remote to search in Remote[X]\n')
            else:
                echo(f'[W0b]Removing[X] [R0b]{len(to_remove)}[X] [W0b]files[X]...')

                if remote:
                    delete_files = ctx.obj.drb.delete_files(*to_remove, lb=ctx.obj.dlb)
                else:
                    delete_files = ctx.obj.dlb.delete_files(
                        *to_remove, rb=(None if local_only else ctx.obj.drb),
                        remove_empty_directories=remove_empty_directories
                    )
                tgbox.sync(delete_files)
                echo('[G0b]Done.[X]')
