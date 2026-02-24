import click

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
    help='If specified, will rename file ONLY in LocalBox'
)
@click.option(
    '--new-file-name','-n', help='New name of the file'
)
@click.option(
    '--reset-file-name','-r', is_flag=True,
    help='If specified, will reset name to original'
)
@click.pass_context
def file_rename(ctx, filters, local_only, new_file_name, reset_file_name):
    """
    Find and Rename file by filters

    \b
    Please NOTE that your filters must return EXACTLY ONE
    FILE. Otherwise we will return an error to You.

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
        tgbox-cli file-rename id=22 --new-file-name "nonsense.png"
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

    to_rename = ctx.obj.dlb.search_file(sf, cache_preview=False)

    dlbf, dlbf_rename = None, None
    for dlbf in sync_async_gen(to_rename):
        if dlbf_rename:
            echo('[Y0b]\nFilters must return exactly One file![X]\n')
            return
        dlbf_rename = dlbf

    if dlbf_rename is None:
        echo('\n[R0b]No files found by specified filters.[X]')
        return

    if not new_file_name and not reset_file_name:
        new_file_name = click.prompt('Please enter new file name')

    if dlbf_rename.cattrs and '__mp_total' in dlbf_rename.cattrs:
        name = dlbf.file_name.split('-')

        if len(name) > 1:
            name = '-'.join(name[:-1])
        else:
            name = name[0]

        sf = tgbox.tools.SearchFilter(file_name=name,
            scope=str(dlbf_rename.file_path), cattrs={
                '__mp_part': b'',
                '__mp_previous': b'',
                '__mp_total': b''
            }
        )
        dlbf_parts = []
        for dlbf in enumerate(sync_async_gen(ctx.obj.dlb.search_file(sf))):
            dlbf_parts.append(dlbf[1])

        total = tgbox.tools.bytes_to_int(dlbf[1].cattrs['__mp_total'])
        if len(dlbf_parts) != total:
            echo(
                '\n[R0b]We can\'t rename Multipart file because of '
               f'missing parts. Expected {total}, got {len(dlbf_parts)}[X]')
            return
    else:
        dlbf_parts = [dlbf_rename]

    for i, dlbf in enumerate(dlbf_parts):
        previous_name = dlbf.file_name
        file_name = None if reset_file_name else new_file_name.encode()

        if file_name is not None and len(dlbf_parts) > 1:
            file_name += b'-' + str(i).encode()

        coro = dlbf.update_metadata(
            changes = {'file_name': file_name},
            drb = None if local_only else ctx.obj.drb
        )
        tgbox.sync(coro)

        if file_name is None:
            dlbf = tgbox.sync(ctx.obj.dlb.get_file(dlbf.id))
            file_name = dlbf.file_name
        else:
            file_name = file_name.decode()
        echo(
            f'[G0b]Successfully renamed [X]"[Y0b]{previous_name}[X]" '
            f'-> "[W0b]{file_name}[X]"'
        )
