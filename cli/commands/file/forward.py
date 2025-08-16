import click

from telethon.errors.rpcerrorlist import (
    UsernameNotOccupiedError, UsernameInvalidError
)

from ..group import cli_group
from ..helpers import ctx_require
from ...tools.terminal import echo
from ...tools.convert import filters_to_searchfilter
from ...tools.other import sync_async_gen
from ...config import tgbox


@cli_group.command()
@click.argument('filters', nargs=-1)
@click.option(
    '--chat', '-c', required=True, prompt=True,
    help='Chat to send file to'
)
@click.option(
    '--chat-is-name', is_flag=True,
    help='Interpret --chat as Chat name and search for it'
)
@ctx_require(dlb=True, drb=True, account=True)
def file_forward(ctx, filters, chat, chat_is_name):
    """
    Forward files by filters to specified chat

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
        tgbox-cli file-forward scope=/home/non/Documents -e @username
        \b
        # Include flag (will ignore unmatched)
        tgbox-cli file-forward +i id=22 --chat me
        \b
        # Exclude flag (will ignore matched)
        tgbox-cli file-forward +e mime=audio --chat @channel
        \b
        You can use both, the ++include and
        ++exclude (+i, +e) in one command.
    """
    if not filters:
        echo(
            '\n[R0b]You didn\'t specified any filter.\n   This '
            'will forward EVERY file from your Box[X]\n'
        )
        if not click.confirm('Are you TOTALLY sure?'):
            return
    try:
        sf = filters_to_searchfilter(filters)
    except IndexError: # Incorrect filters format
        echo('[R0b]Incorrect filters! Make sure to use format filter=value[X]')
    except KeyError as e: # Unknown filters
        echo(f'[R0b]Filter "{e.args[0]}" doesn\'t exists[X]')
    else:
        try:
            chat_name = chat
            chat = tgbox.sync(ctx.obj.account.get_entity(chat))
        except (UsernameNotOccupiedError, UsernameInvalidError, ValueError):
            if not chat_is_name:
                echo(f'[Y0b]Can\'t find specified chat "{chat}"[X]')
                return

            for dialogue in sync_async_gen(ctx.obj.account.iter_dialogs()):
                if chat in dialogue.title and dialogue.is_channel:
                    chat_name = dialogue.title.split(': ',1)[-1]
                    chat = dialogue; break
            else:
                echo(f'[Y0b]Can\'t find specified chat "{chat}"[X]')
                return

        to_forward = ctx.obj.dlb.search_file(sf)
        FORWARD_STACK, FORWARD_WHEN = [], 100

        def _forward(stack: list):
            forward = ctx.obj.account.forward_messages(
                entity=chat,
                messages=[dlbf.id for dlbf in stack],
                from_peer=ctx.obj.drb.box_channel
            )
            tgbox.sync(forward)

            for dlbf in stack:
                echo(f'[G0b]ID{dlbf.id}: {dlbf.file_name}: was forwarded to {chat_name}[X]')

        echo('[Y0b]\nSearching files to forward...[X]\n')

        for dlbf in sync_async_gen(to_forward):
            if len(FORWARD_STACK) == FORWARD_WHEN:
                _forward(FORWARD_STACK)
                FORWARD_STACK.clear()

            FORWARD_STACK.append(dlbf)

        if FORWARD_STACK: # If any left
            _forward(FORWARD_STACK)
        echo('')
