import click

from time import sleep
from io import BytesIO
from pathlib import Path
from datetime import datetime

from ..group import cli_group
from ..helpers import ctx_require
from ..file.remove import file_remove

from ...tools.terminal import echo, colorize, clear_console
from ...tools.other import sync_async_gen, format_dxbf_message
from ...tools.strings import break_string
from ...config import tgbox


@cli_group.command()
@click.option(
    '--topic', '-t', default='Main',
    help='Chat topic (Folder-like)'
)
@click.option(
    '--current-date', '-d',
    help='Date (format %Y/%m/%d) from which we will fetch messages'
)
@click.option(
    '--auto-mode-wait', '-w', type=click.IntRange(3, None), default=10,
    help='Seconds of Sleep before fetching Chat Updates'
)
@click.option(
    '--enable-usernames', '-u', is_flag=True,
    help = (
        'If specified, will show sender Usernames. Please note that '
        'Telegram became more aggressive on it, so you may get FloodWaitError'
    )
)
@click.option(
    '--less-data', '-l', is_flag=True,
    help='If specified, will use less network traffic'
)
@ctx_require(dlb=True, drb=True)
def chat_open(ctx, topic, current_date, auto_mode_wait, enable_usernames, less_data):
    """
    Launch simple Chat inside your Box

    For correctly attributing messages to Chat members
    You are recommended to enable "Sign Messages" and
    then "Show author's profiles" in your Box Channel
    settings. This command will ask you for this.

    By default Chat will fetch files from the RemoteBox
    and make Fast Sync to cache new messages. With the
    `--less-data` flag Chat will get messages from Local
    instead of Remote. This should be faster and unload
    some network usage BUT it will be impossible to know
    ACTUAL message sender if "Show author's profiles"
    option is enabled in Channel, as we will get it from
    the File (Message) CAttrs, and they can be forged.

    Verified messages have checkmark ("√") in "Author"
    field, unverified will have red "x" symbol.
    """
    if not ctx.obj.dlb.defaults.FAST_SYNC_ENABLED:
        fs_enable_ask = colorize(
            '\n[W0b]@[X] This Chat requires [C0b]Fast Sync[X] to be enabled on '
            'your Box, but it is [Y0b]disabled[X] in your defaults. '
            '[C0b]Fast Sync[X] is a synchronization from Channel Admin '
            'Log, it [Y0b]may add a little bit of overhead on general '
            'file uploading[X]. Typically it\'s neglectable, but can '
            'be noticed on big, batch uploading. Do you want me to enable it?'
        )
        echo(f'\n{break_string(fs_enable_ask, 2)}\n')

        if not click.confirm('\nType your choice and press Enter'):
            return

        tgbox.sync(ctx.obj.dlb.defaults.change('FAST_SYNC_ENABLED', 1))

    chat_dir = tgbox.sync(ctx.obj.dlb.get_directory('__BOX_CHAT__'))
    if not chat_dir:
        sync_ask = colorize(
            '[W0b]@[X] Currently we don\'t know about Chat in this Box. Did '
            'you tried [B0b]box-sync[X]? If [G1b]YES[X] '
            'and you want to create it, type [G1b]Y[X]. If '
            '[R1b]NO[X], type [R1b]N[X] and try [B0b]box-sync[X].'
        )
        echo(f'\n{break_string(sync_ask, 2)}\n')

        if not click.confirm('Type your choice and press Enter'):
            return

        echo('\n[W1]% We need to configure Box chat firstly..[X]')

        author_ask = colorize(
            '[W0b]@[X] To correctly verify and assign messages to authors we '
            'need to enable "Sign Messages" -> "Show author\'s profiles" '
            'in Box Channel settings. Please note that this will '
            '[Y1b]deanonimize your Telegram profile in Channel[X]. Are you '
            'OK with this? Type [G1b]Y[X] if [G1b]yes[X], '
            'type [R1b]N[X] otherwise.'
        )
        echo(f'\n{break_string(author_ask, 2)}\n')

        enable_profiles = click.confirm('Type your choice and press Enter')

        if enable_profiles:
            author_files = tgbox.sync(ctx.obj.drb.author_files(True))

            if author_files is False: # Not enough rights
                no_rights = colorize(
                    '[W0b]x[X] You [R0b]don\'t have enough rights[X] to toggle '
                    'this parameter. [W0b]Ask Admin for them or Skip.[X]'
                )
                echo(f'\n{break_string(no_rights, 2)}')
        else:
            skip = colorize(
                '\n[Y1b]% Okay, skip![X] You can always toggle [W0b]"Show authors '
                'profile\'s"[X] in Box Channel settings within Telegram!'
            )
            echo(f'\n{break_string(skip, 2)}')

        echo('')
        chat_name = click.prompt('Chat name')
        description = click.prompt('Chat description', default='No Description.')

        echo('\n[W0b]@ Uploading configuration...[X]\n')

        file = BytesIO(b'')
        file.name = 'MAIN'

        config_pf = ctx.obj.dlb.prepare_file(
            file = file,
            file_path = str(Path('__BOX_CHAT__', '__CONFIG__', 'CONFIG')),
            cattrs = {
                'name': chat_name.encode(),
                'description': description.encode()
            },
            make_preview = False,
            file_size = 0
        )
        config_pf = tgbox.sync(config_pf)
        tgbox.sync(ctx.obj.drb.push_file(config_pf))

    config = ctx.obj.dlb.search_file(sf=tgbox.tools.SearchFilter(
        scope=str(Path('__BOX_CHAT__', '__CONFIG__')))
    )
    try:
        config = tgbox.sync(tgbox.tools.anext(config))
    except StopAsyncIteration:
        no_config = colorize(
            '[W0b]@[X] It seems that there is already Chat folder on '
            'your Box, but it does not have CONFIG. Did you tried '
            '[C0b]box-sync[X]? If yes, and [R0b]you want to erase ALL '
            'old Chat data[X] type [G1b]Y[X], otherwise '
            'type [R1b]N[X]'
        )
        echo(f'\n{break_string(no_config, 2)}\n')

        if not click.confirm('Do you want to erase old Chat data and make new?'):
            skip = colorize(
                '[Y1b]% Okay, skip! You can also use "dir-list --cleanup '
                '--show-box-chat" several times to remove "__BOX_CHAT__" '
                'directory.[X]'
            )
            echo(f'\n{break_string(skip, 2)}\n')
            return

        else:
            echo('\n[W0b]@ Removing Chat messages (If any)[X]')

            ctx.invoke(file_remove,
                filters=("scope=__BOX_CHAT__",),
                local_only=True,
                remove_empty_directories=True
            )
            echo('\n[W0b]@ Removing Chat Directory[X]\n')
            tgbox.sync(chat_dir.delete())

            echo('[G0b]Done.[X] [W0b]Run chat-open again![X]\n')

        return

    chat_name = config.cattrs['name'].decode()
    description = config.cattrs['description'].decode()

    auto_mode, warning_shown = False, False
    clear_console()
    while True:
        try:
            if current_date is None:
                current_date = datetime.fromtimestamp(datetime.now().timestamp())
                current_date = current_date.strftime('%Y/%m/%d')
            else:
                if not warning_shown:
                    cd_check = current_date.split('/')

                    if not all((i.isnumeric() for i in cd_check))\
                        or len(cd_check[0]) != 4 or len(cd_check) != 3:
                            echo(
                                '[Y0b]\nYou provided absolute or incorrect Date. '
                                'Sending\nMessages to it will not work as you may expect. '
                                '\nRead Only or Review your --current-date option.[X]'
                            )
                            echo(
                                '\n[W0b]Correct format is "%Y/%m/%d" '
                                '(i.e "2024/02/22")[X]'
                            )
                            click.prompt(
                                '\n@ Press ENTER to Continue (OK)',
                                default='', show_default=False
                            )
                            warning_shown = True
                            clear_console()

            topic = topic.strip('/').strip('\\') or 'Main'
            topic_path = Path('__BOX_CHAT__', '__CHAT__', topic, current_date)

            echo(f'\n# [W0b]Chat {chat_name}[X] ({description})')
            echo(f'# [W0b]Topic/{topic}, Date: {current_date}[X]')

            chat_dir = tgbox.sync(ctx.obj.dlb.get_directory(str(topic_path)))
            if not chat_dir:
                echo('\n[Y0b]@ Chat on this date is empty...[X]')
                dxbf_messages = []
            else:
                contents = ctx.obj.dlb.contents(sfpid=chat_dir.part_id)

                dxbf_messages = [
                    dlbf for dlbf in sync_async_gen(contents)
                    if isinstance(dlbf, tgbox.api.local.DecryptedLocalBoxFile)
                ]

            if not less_data:
                drbfi = ctx.obj.drb.files(ids=[dlbf.id for dlbf in dxbf_messages])
                dxbf_messages = reversed([drbf for drbf in sync_async_gen(drbfi)])

            for dxbf in dxbf_messages:
                echo(format_dxbf_message(dxbf, show_username=enable_usernames))

            if not auto_mode:
                msgcc = '[X1b]' if warning_shown else '[W0b]'
                echo(
                   f'\n{msgcc}1) Send Message;[X] [W0b]2) Auto Update; 3) Exit[X]\n'
                    '[W0b]Press ENTER to Update or Select Mode[X]', nl=False
                )
                mode = click.prompt('', default='', show_default=False)

                if mode == '1':
                    echo('')

                    msg_name = tgbox.tools.prbg(8).hex()
                    message = click.prompt('Message').encode()

                    me = tgbox.sync(ctx.obj.drb.tc.get_me())
                    author = me.username or me.first_name
                    author_id = str(me.id)

                    msg_pf = ctx.obj.dlb.prepare_file(b'',
                        file_path = str(topic_path / msg_name),
                        cattrs = {
                            'text': message,
                            'author': author.encode(),
                            'author_id': author_id.encode()
                        },
                        make_preview = False,
                        file_size = 0
                    )
                    msg_pf = tgbox.sync(msg_pf)
                    tgbox.sync(ctx.obj.drb.push_file(msg_pf))

                elif mode == '2':
                    auto_mode = True

                elif mode == '3':
                    break
                else:
                    tgbox.sync(ctx.obj.dlb.sync(ctx.obj.drb))

            else:
                time = datetime.now().strftime('%d/%m/%y, %H:%M:%S')
                echo(
                    f'\n[W0b]% ({time}) Waiting {auto_mode_wait} '
                    'seconds before Sync...[X]'
                )
                echo('[W0b]@ Press CTRL+C to Return to Input Mode\r[X]', nl=False)

                sleep(auto_mode_wait)

                time = datetime.now().strftime('%d/%m/%y, %H:%M:%S')
                echo(f'[W0b]V ({time}) Syncing your Chat with Fast Sync...[X]')

                tgbox.sync(ctx.obj.dlb.sync(ctx.obj.drb))

        except KeyboardInterrupt:
            auto_mode = False
        finally:
            clear_console()
