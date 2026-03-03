import click

from time import sleep
from asyncio import gather

from ..group import cli_group
from ..helpers import ctx_require
from ...tools.terminal import echo
from ...tools.convert import filters_to_searchfilter
from ...tools.other import sync_async_gen
from ...config import tgbox


@cli_group.command()
@click.argument('filters', nargs=-1)
@click.option(
    '--tag', '-t', required=True,
    help='Name of tag you want to modify'
)
@click.option(
    '--data', '-d',
    help='Data you wish to assign to tag'
)
@click.option(
    '--remove-tag', '-r', is_flag=True,
    help='Specify instead of --data to remove tag from file'
)
@click.option(
    '--local-only','-l', is_flag=True,
    help='If specified, will add tag to file only in LocalBox'
)
@ctx_require(dlb=True, drb=True)
def file_tag(ctx, filters, tag, data, remove_tag, local_only):
    """Add tag with data to selected files

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
        tgbox-cli file-tag scope=/home/user/Pictures/Cats\b
            -t "Description" -d "Cute cats!!"
    """
    if not remove_tag and not data:
        data = click.prompt('Data')
    try:
        sf = filters_to_searchfilter(filters)
    except IndexError: # Incorrect filters format
        echo('[R0b]Incorrect filters! Make sure to use format filter=value[X]')
    except KeyError as e: # Unknown filters
        echo(f'[R0b]Filter "{e.args[0]}" doesn\'t exists[X]')
    else:
        if not filters:
            echo(
                '\n[R0b]You didn\'t specified any search filter.\n   This '
                'will [X]add tags to all files[W0b] in your Box[X]\n'
            )
            if not click.confirm('Are you TOTALLY sure?'):
                return

        changes = {tag: b'' if remove_tag else data.encode()}
        changes = tgbox.tools.PackedAttributes.pack(**changes)
        changes = {'cattrs': changes}

        to_tag = ctx.obj.dlb.search_file(sf, cache_preview=False)
        dxbf_to_update = []

        UPDATE_WHEN = 200 if not local_only else 100
        TIMEOUT = 15 if not local_only else 0

        async def _update_dxbf(dxbf_id, box):
            dlbf = await ctx.obj.dlb.get_file(dxbf_id)

            if isinstance(box, tgbox.api.local.DecryptedLocalBox):
                prefix = '[LB Only]'
                await dlbf.update_metadata(changes=changes, dlb=box)
            else:
                prefix = '[LB & RB]'
                await dlbf.update_metadata(changes=changes, drb=box)
            echo(
                f'[X1b]{prefix}[X] ([W0b]{dlbf.id}[X]) {dlbf.file_name} '
                f'<= [Y0b]{tag}[X]')

        box = ctx.obj.dlb if local_only else ctx.obj.drb

        for dlbf in sync_async_gen(to_tag):
            dxbf_to_update.append(_update_dxbf(dlbf.id, box))

            if len(dxbf_to_update) == UPDATE_WHEN:
                tgbox.sync(gather(*dxbf_to_update))
                dxbf_to_update.clear()
                sleep(TIMEOUT)

        if dxbf_to_update:
            tgbox.sync(gather(*dxbf_to_update))
            dxbf_to_update.clear()
