from pathlib import Path

from ..group import cli_group
from ..helpers import ctx_require
from ...tools.terminal import echo
from ...tools.other import sync_async_gen
from ...config import tgbox


@cli_group.command()
@ctx_require(dlb=True, drb=True)
def chat_info(ctx):
    """Show info about Chat on selected Box"""

    chat_dir = tgbox.sync(ctx.obj.dlb.get_directory('__BOX_CHAT__'))

    if not chat_dir:
        echo('\n[Y0b]This Box doesn\'t have Chat yet.[X]\n')
        return

    config = ctx.obj.dlb.search_file(sf=tgbox.tools.SearchFilter(
        scope=str(Path('__BOX_CHAT__', '__CONFIG__')))
    )
    try:
        config = tgbox.sync(tgbox.tools.anext(config))
    except StopAsyncIteration:
        echo('[R0b]\nChat doesn\'t have config!!! Try to reset it, error![X]\n')
        return

    chat_name = config.cattrs['name'].decode()
    description = config.cattrs['description'].decode()

    echo(f'\n# [W0b]Chat {chat_name}[X] ({description})')

    chat_dir = tgbox.sync(ctx.obj.dlb.get_directory(
        str(Path('__BOX_CHAT__', '__CHAT__')))
    )
    if not chat_dir:
        echo('\n[Y0b]This Chat doesn\'t have any Messages yet.[X]\n')
        return

    topics_dict = {}
    topics = ctx.obj.dlb.contents(chat_dir.part_id, ignore_files=True)

    for topic in sync_async_gen(topics):
        tgbox.sync(topic.lload(full=True))

        if len(topic.parts) < 3:
             continue

        if len(topic.parts) == 6:
            topic_path = Path(str(topic)).parts[2:]

            topic = topic_path[0]
            date = '/'.join(topic_path[1:])

            if topic not in topics_dict:
                topics_dict[topic] = []

            topics_dict[topic].append(date)

        for v in topics_dict.values():
            v.sort()

    for k,v in topics_dict.items():
        echo(f'\n[C0b]@ Topic[X] "[W0b]{k}[X]"')

        for date in v:
            date_dir = str(Path('__BOX_CHAT__', '__CHAT__', k, *date.split('/')))

            messages_total = tgbox.sync(ctx.obj.dlb.get_directory(date_dir))
            messages_total = tgbox.sync(messages_total.get_files_total())

            echo(
                f'[W0b]| {date}[X] ([Y0b]'
                f'{messages_total}[X])'
            )
    echo('')
