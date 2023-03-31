import tgbox

from sys import exit
from click import style
from typing import Union
from itertools import cycle

from typing import AsyncGenerator
from urllib3.util import parse_url
from shutil import get_terminal_size
from os import system, name as os_name

clear_console = lambda: system('cls' if os_name in ('nt','dos') else 'clear')

AVAILABLE_COLORS = [
    'red','cyan','blue','green',
    'white','yellow','magenta',
    'bright_black','bright_red',
    'bright_magenta', 'bright_blue',
    'bright_cyan', 'bright_white'
]
def color(text: Union[str, bytes]) -> Union[str, bytes]:
    """
    Will color special formatted parts of text to the
    specified color. [RED]This will be red[RED], [BLUE]
    and this is blue[BLUE]. Color should be in uppercase
    and should be in the tools.AVAILABLE_COLORS list
    and should be supported by the click.style function.
    """
    NOCOLOR = '\x1b[0m'

    available = {
        ccolor.upper(): style('%', fg=ccolor, bold=True).rstrip(NOCOLOR)[:-1]
        for ccolor in AVAILABLE_COLORS
    }
    for color_, ansi_code in available.items():
        # State 0 is color, state 1 is NOCOLOR
        state = cycle(range(2))

        while f'[{color_}]' in text:
            current = NOCOLOR if next(state) else ansi_code
            text = text.replace(f'[{color_}]', current, 1)

    return text

async def exit_program(*, dlb=None, drb=None):
    if dlb:
        await dlb.done()
    if drb:
        await drb.done()
    exit(0)

class Progress:
    """
    This is a little wrapper around enlighten

    from enlighten import get_manager

    manager = get_manager()

    tgbox.api.DecryptedLocalBox.push_file(
        ..., progress_callback=Progress(manager).update
    )
    """
    def __init__(self, manager, desc: str=None):
        self.desc = desc
        self.counter = None
        self.manager = manager

        # For update
        self.total_blocks = 0

        # For update_2
        self.initialized = False

        self.BAR_FORMAT = '{desc} {percentage:3.0f}%|{bar}| [ETA {eta}]'

    def update(self, _, total):
        if not self.total_blocks:
            self.total_blocks = total / 524288

            if int(self.total_blocks) != self.total_blocks:
                self.total_blocks = int(self.total_blocks) + 1

            desc = self.desc[:40]

            if desc != self.desc:
                desc = desc[:37] + '...'

            while len(desc) < 40:
                desc += ' '

            self.counter = self.manager.counter(
                total=self.total_blocks, desc=desc,
                unit='x 512KB', color='gray',
                bar_format=self.BAR_FORMAT
            )
        self.counter.update()

    def update_2(self, current, total):
        if not self.initialized:
            self.counter = self.manager.counter(
                total=total, desc=self.desc,
                unit='ID', color='gray',
                bar_format=self.BAR_FORMAT
            )
            for _ in range(current):
                self.counter.update()
            self.initialized = True
        else:
            self.counter.update()

def format_bytes(size):
    # That's not mine. Thanks to the
    # https://stackoverflow.com/a/49361727

    power, n = 2**10, 0
    power_labels = {
        0 : '',
        1: 'K',
        2: 'M',
        3: 'G'
    }
    while size > power:
        size /= power
        n += 1
    return f'{round(size,1)}{power_labels[n]}B'

def sync_async_gen(async_gen: AsyncGenerator):
    """
    This will make async generator to sync
    generator, so we can write "for" loop.
    """
    try:
        while True:
            yield tgbox.sync(tgbox.tools.anext(async_gen))
    except StopAsyncIteration:
        return

def filters_to_searchfilter(filters: tuple) -> tgbox.tools.SearchFilter:
    """
    This function will make SearchFilter from
    tuple like ('id=5', 'max_size='1024', ...)
    """
    include = {}
    exclude = {}

    # Zero is Include,
    # One is Exclude
    current = 0

    for filter in filters:
        if filter in ('+i', '++include'):
            current = 0
        elif filter in ('+e', '++exclude'):
            current = 1
        else:
            current_filter = exclude if current else include
            filter = filter.split('=',1)

            if filter[0] == 'cattrs':
                try:
                    filter[1] = tgbox.tools.PackedAttributes.unpack(
                        bytes.fromhex(filter[1])
                    );  assert filter[1]
                except (ValueError, AssertionError):
                    # Specified value isn't a hexed PackedAttributes
                    cattrs = {}
                    for items in filter[1].split():
                        items = items.split(':',1)
                        cattrs[items[0]] = items[1].encode()

                    filter[1] = cattrs

            if filter[0] not in current_filter:
                current_filter[filter[0]] = [filter[1]]
            else:
                current_filter[filter[0]].append(filter[1])

    return tgbox.tools.SearchFilter(**include).exclude(**exclude)

def splitpath(path: str, indent: int=0) -> str:
    available = int(get_terminal_size().columns // 1.8)
    available = 30 if available < 30 else available

    parts = []
    while path:
        parts.append(path[:available] + '->')
        path = path[available:]

    parts[-1] = parts[-1][:-2]

    joinsymbols = '\n'+' '*indent
    return joinsymbols.join(parts).strip()

def env_proxy_to_pysocks(env_proxy: str) -> tuple:
    p = parse_url(env_proxy)

    if p.auth:
        username, password = p.auth.split(':')
    else:
        username, password = None, None

    return (
        p.scheme,
        p.host,
        p.port,
        True,
        username,
        password
    )
