import click

from os import getenv
from base64 import urlsafe_b64encode
from datetime import datetime

from ..group import cli_group
from ..helpers import check_ctx
from ...tools.terminal import echo
from ...tools.other import format_dxbf, format_dxbf_multipart, sync_async_gen
from ...tools.convert import format_bytes, filters_to_searchfilter
from ...config import tgbox, TGBOX_CLI_NOCOLOR


@cli_group.command()
@click.argument('filters',nargs=-1)
@click.option(
    '--force-remote','-r', is_flag=True,
    help='If specified, will fetch files from RemoteBox'
)
@click.option(
    '--upend', '-u', is_flag=True,
    help='If specified, will search in reverse order'
)
@click.option(
    '--non-interactive', is_flag=True,
    help='If specified, will echo to shell instead of pager'
)
@click.option(
    '--non-imported', is_flag=True,
    help='If specified, will search for non-imported files only'
)
@click.option(
    '--bytesize-total', is_flag=True,
    help='If specified, will calc a total size of filtered files'
)
@click.option(
    '--fetch-count', '-f', default=100,
    help='Amount of files to fetch from LocalBox before return',
)
@click.option(
    '--split-multipart', '-s', is_flag=True,
    help='If specified, will not collect Multipart file in one entry',
)
@click.pass_context
def file_search(
        ctx, filters, force_remote, non_interactive, non_imported,
        upend, bytesize_total, fetch_count, split_multipart):
    """List files by selected filters

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
        tgbox-cli file-search min_id=3 max_id=100
        \b
        # Include flag (will ignore unmatched)
        tgbox-cli file-search +i file_name=.png
        \b
        # Exclude flag (will ignore matched)
        tgbox-cli file-search +e file_name=.png
        \b
        You can use both, the ++include and
        ++exclude (+i, +e) in one command.
    """
    if force_remote or non_imported:
        check_ctx(ctx, dlb=True, drb=True)
    else:
        check_ctx(ctx, dlb=True)
    try:
        sf = filters_to_searchfilter(filters)

        scope_path_list = (
              list(sf.in_filters['scope'])\
            + list(sf.in_filters['file_path'])
        )
        for filter_ in scope_path_list:
            if '__BOX_CHAT__' in filter_: # Remove all files in __BOX_CHAT__
                break                     # from the file-search list if
        else:                             # user didn't requested it
            sf.ex_filters['file_path'].append('__BOX_CHAT__')

    except IndexError: # Incorrect filters format
        echo('[R0b]Incorrect filters! Make sure to use format filter=value[X]')
        return
    except KeyError as e: # Unknown filters
        echo(f'[R0b]Filter "{e.args[0]}" doesn\'t exists[X]')
        return

    box = ctx.obj.drb if force_remote else ctx.obj.dlb

    if non_imported:
        iter_over = ctx.obj.drb.search_file(
            sf=sf, reverse=True,
            cache_preview=False,
            return_imported_as_erbf=True
        )
        echo('[Y0b]\nSearching, press CTRL+C to stop...[X]')

        for xrbf in sync_async_gen(iter_over):
            if type(xrbf) is tgbox.api.EncryptedRemoteBoxFile:
                time = datetime.fromtimestamp(xrbf.upload_time)
                time = f"[C0b]{time.strftime('%d/%m/%y, %H:%M:%S')}[X]"

                salt = urlsafe_b64encode(xrbf.file_salt.salt).decode()
                idsalt = f'[[R1b]{str(xrbf.id)}[X]:'
                idsalt += f'[X1b]{salt[:12]}[X]]'

                size = f'[G0b]{format_bytes(xrbf.file_size)}[X]'
                name = '[R0b][N/A: No FileKey available][X]'

                req_key = xrbf.get_requestkey(ctx.obj.dlb._mainkey).encode()
                req_key = f'[W0b]{req_key}[X]'

                formatted = (
                   f"""\nFile: {idsalt} {name}\n"""
                   f"""Size, Time: {size}({xrbf.file_size}), {time}\n"""
                   f"""RequestKey: {req_key}"""
                )
                echo(formatted)
        echo('')
        return

    if bytesize_total:
        total_bytes, current_file_count = 0, 0

        echo('')

        if force_remote:
            iter_over = box.search_file(sf, cache_preview=False)
        else:
            iter_over = box.search_file(
                sf, cache_preview=False,
                fetch_count=fetch_count
            )
        for dlbf in sync_async_gen(iter_over):
            total_bytes += dlbf.size
            current_file_count += 1

            total_formatted = f'[B0b]{format_bytes(total_bytes)}[X]'
            current_file = f'[Y0b]{current_file_count}[X]'

            echo_text = (
                f'@ Total [W0b]files found [X]({current_file}) '
                f'size is {total_formatted}({total_bytes})   \r'
            )
            echo(echo_text, nl=False)

        echo('\n')
        return

    def bfi_gen(search_file_gen):
        # We will construct (format) dxbf only for first
        # multipart file part and skip its parts. Here
        # we will cache ids to omit
        multipart_ignore = set()

        for bfi in sync_async_gen(search_file_gen):
            if bfi.id in multipart_ignore:
                multipart_ignore.remove(bfi.id)
                continue

            # We concat multipart into one entry-file only on LocalBox
            # file search, because we can not do it reliably on Remote
            # in the same way as with Local (through search).
            is_dlbf = isinstance(bfi, tgbox.api.local.DecryptedLocalBoxFile)

            if not split_multipart and is_dlbf:
                if bfi.cattrs and '__mp_part' in bfi.cattrs:
                    name = '-'.join(bfi.file_name.split('-')[:-1])
                    # The most straightforward solution to get all parts of
                    # one multipart file is to search for them. We can NOT
                    # just blindly assume that "next file is the next part";
                    # though yes, we upload parts from first to last one-
                    # by-one, in case when multiple Users share one Box,
                    # file of Bob can be in a way of multipart file of
                    # Alice, like [part, part, Bob file, part, ...], so
                    # it's only safe for us to request them directly. If
                    # scope (directory of file) doesn't have enormous
                    # amount of files, search should be lightning fast.
                    sf = tgbox.tools.SearchFilter(file_name=name,
                        scope=str(bfi.file_path), cattrs={
                            '__mp_part': b'',
                            '__mp_previous': b'',
                            '__mp_total': b''
                        }
                    )
                    parts = []
                    for i, dlbf in enumerate(sync_async_gen(box.search_file(sf))):
                        if i > 0: # skip first id as we show it
                            multipart_ignore.add(dlbf.id)
                        parts.append(dlbf)

                    parts.sort(key=lambda d: d.cattrs['__mp_part'])
                    yield format_dxbf_multipart(parts)
                else:
                    yield format_dxbf(bfi)
            else:
                yield format_dxbf(bfi)

    sgen = box.search_file(
        sf=sf, reverse=upend,
        cache_preview=True
    )
    sgen = bfi_gen(sgen)

    if non_interactive:
        for dxbfs in sgen:
            echo(dxbfs, nl=False)
        echo('')
    else:
        colored = False if TGBOX_CLI_NOCOLOR else None

        if getenv('TGBOX_CLI_FORCE_PAGER_COLOR'):
            colored = True

        click.echo_via_pager(sgen, color=colored)
