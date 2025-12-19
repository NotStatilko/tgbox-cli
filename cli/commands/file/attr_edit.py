import click

from time import sleep
from asyncio import gather

from ..group import cli_group
from ..helpers import ctx_require
from ...tools.terminal import echo
from ...tools.convert import filters_to_searchfilter, parse_str_cattrs
from ...tools.other import sync_async_gen
from ...config import tgbox


@cli_group.command()
@click.argument('filters', nargs=-1)
@click.option(
    '--attribute', '-a', required=True,
    help='File attribute, e.g file_name=test.txt'
)
@click.option(
    '--local-only','-l', is_flag=True,
    help='If specified, will change attr only in LocalBox'
)
@ctx_require(dlb=True, drb=True)
def file_attr_edit(ctx, filters, attribute, local_only):
    """Change attribute value of Box files (search by filters)

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
        tgbox-cli file-attr-edit min_id=3 max_id=100 -a file_path=/home/non/
        \b
        # Include flag (will ignore unmatched)
        tgbox-cli file-attr-edit +i file_name=.png -a file_path=/home/non/Pictures
        \b
        # Exclude flag (will ignore matched)
        tgbox-cli file-attr-edit +e file_name=.png -a file_path=/home/non/NonPictures
        \b
        # Attribute without value will reset it to default
        tgbox-cli file-attr-edit id=22 -a file_name=
        \b
        You can use both, the ++include and
        ++exclude (+i, +e) in one command.
    """
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
                'will [X]change attrs for all files[W0b] in your Box[X]\n'
            )
            if not click.confirm('Are you TOTALLY sure?'):
                return

        attr_key, attr_value = attribute.split('=',1)

        if attr_key == 'cattrs' and not attr_value:
            changes = {}

        elif attr_key == 'cattrs':
            attr_value = parse_str_cattrs(attr_value)
            changes = {attr_key: tgbox.tools.PackedAttributes.pack(**attr_value)}
        else:
            changes = {attr_key: attr_value.encode()}

        to_change = ctx.obj.dlb.search_file(sf, cache_preview=False)

        dxbf_to_update = []

        UPDATE_WHEN = 200 if not local_only else 100
        TIMEOUT = 15 if not local_only else 0

        async def _update_dxbf(dxbf_id, box):
            dlbf = await ctx.obj.dlb.get_file(dxbf_id)
            original_file_name = dlbf.file_name
            try:
                if isinstance(box, tgbox.api.local.DecryptedLocalBox):
                    prefix = '[LB Only]'
                    await dlbf.update_metadata(changes=changes, dlb=box)
                else:
                    prefix = '[LB & RB]'
                    await dlbf.update_metadata(changes=changes, drb=box)
                echo(
                    f'[X1b]{prefix}[X] ([W0b]{dlbf.id}[X]) {original_file_name} '
                    f'<= [Y0b]{attribute}[X]')
            except tgbox.errors.FingerprintExists:
                echo(
                    f'[X1b]{prefix}[X] ([R1b]{dlbf.id}[X]) {original_file_name} '
                    f'X= [R1b]{attribute}[X]. [R1]Fingerprint exists[X].')


        box = ctx.obj.dlb if local_only else ctx.obj.drb

        for dlbf in sync_async_gen(to_change):
            dxbf_to_update.append(_update_dxbf(dlbf.id, box))

            if len(dxbf_to_update) == UPDATE_WHEN:
                tgbox.sync(gather(*dxbf_to_update))
                dxbf_to_update.clear()
                sleep(TIMEOUT)

        if dxbf_to_update:
            tgbox.sync(gather(*dxbf_to_update))
            dxbf_to_update.clear()
