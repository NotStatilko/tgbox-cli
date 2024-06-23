import click
import tgbox

from typing import Union
from copy import deepcopy
from itertools import cycle

from typing import AsyncGenerator
from urllib3.util import parse_url

from base64 import urlsafe_b64encode
from shutil import get_terminal_size

from datetime import datetime, timedelta
from platform import system as platform_sys

from pathlib import Path
from os.path import expandvars
from os import system as os_system


AVAILABLE_COLORS = [
    'red','cyan','blue','green',
    'white','yellow','magenta',
    'bright_black','bright_red',
    'bright_magenta', 'bright_blue',
    'bright_cyan', 'bright_white',
    'bright_yellow', 'bright_green'
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
        ccolor.upper(): click.style('%', fg=ccolor, bold=True).rstrip(NOCOLOR)[:-1]
        for ccolor in AVAILABLE_COLORS
    }
    for color_, ansi_code in available.items():
        # State 0 is color, state 1 is NOCOLOR
        state = cycle(range(2))

        while f'[{color_}]' in text:
            current = NOCOLOR if next(state) else ansi_code
            text = text.replace(f'[{color_}]', current, 1)

    return text

class Progress:
    """
    This is a little wrapper around enlighten

    from enlighten import get_manager

    manager = get_manager()

    tgbox.api.DecryptedLocalBox.push_file(
        ..., progress_callback=Progress(manager).update
    )
    """
    def __init__(self, manager, desc: str=None, blocks_downloaded: int=0):
        self.desc = desc
        self.counter = None
        self.manager = manager

        # For update
        self.total_blocks = 0
        self.blocks_downloaded = blocks_downloaded

        # For update_2
        self.initialized = False
        self.last_id = None

    def __del__(self):
        if self.total_blocks: # If .update
            block_total = str(self.counter.count).zfill(4)

            self.counter.counter_format = '{desc}{desc_pad}' +\
                color(f'[{block_total} [WHITE]Chunks[WHITE] [GREEN]DONE[GREEN]],') +\
                ' {elapsed} ' + color('[WHITE]Elapsed[WHITE]')

        elif self.last_id: # If .update_2
            self.counter.counter_format = color('[WHITE]@[WHITE] ') + '{count:d} ' +\
                color('[WHITE]Files[WHITE] [GREEN]SYNCED[GREEN], ') + '{elapsed} ' +\
                color('[WHITE]Elapsed[WHITE], {rate:.0f} [WHITE]Files[WHITE]/second')

        if self.counter:
            self.counter.update()
            self.counter.close()

    def update(self, _, total):
        if not self.counter:
            BAR_FORMAT = '{desc} | {percentage:3.0f}% |{bar}| [ETA {eta}] |'

            self.total_blocks = total // 524288 - self.blocks_downloaded
            self.total_blocks = 1 if self.total_blocks == 0 else self.total_blocks

            desc = self.desc[:32]

            if desc != self.desc:
                desc = desc[:29] + '...'

            while len(desc) < 32:
                desc += ' '

            self.counter = self.manager.counter(
                total=self.total_blocks, desc=desc,
                unit='x 512KB', color='gray',
                bar_format=BAR_FORMAT
            )
        self.counter.update()

    def update_2(self, current, total):
        if not self.initialized:
            BAR = '{desc} | {percentage:3.0f}% |{bar}| ({count}/{total}) [ETA {eta}, ELA {elapsed}]'

            self.counter = self.manager.counter(
                total=total - current,
                desc=self.desc,
                unit='ID', color='gray',
                bar_format=BAR
            )
            self.counter.update()

            self.initialized = True
            self.last_id = current
        else:
            for _ in range(current - self.last_id):
                self.counter.update()

            self.last_id = current

def clear_console():
    if platform_sys().lower() == 'windows':
        clear_command = 'cls'
    else:
        clear_command = 'clear'

    os_system(clear_command)

def format_bytes(size):
    # That's not mine. Thanks to the
    # https://stackoverflow.com/a/49361727

    power, n = 10**3, 0
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

def formatted_bytes_to_int(formatted: str) -> int:
    power_labels = {
        'KB': 1000,
        'MB': 1e+6,
        'GB': 1e+9
    }
    if formatted[-2:] in power_labels:
        formatted = float(formatted[:-2]) \
            * power_labels[formatted[-2:]]

    elif formatted[-1] == 'B':
        formatted = float(formatted[:-1])

    return int(formatted)

def parse_str_cattrs(cattrs_str: str) -> dict:
    """
    This function can convert str CAttrs of TGBOX-CLI
    format into the dictionary. Also accepts raw
    CAttrs as hex. For example:
        cattrs="FF000004746578740000044F5A5A5900000474797065000005696D616765"
        &
        cattrs="type: image | text: OZZY"
        =
        return {'text': b'OZZY', 'type': b'image'}
    """
    try:
        cattrs_str = tgbox.tools.PackedAttributes.unpack(
            bytes.fromhex(cattrs_str)
        );  assert cattrs_str
    except (ValueError, AssertionError):
        try:
            cattrs_str = [
                i.strip().split(':')
                for i in cattrs_str.split('|') if i
            ]
            cattrs_str = {
                k.strip() : v.strip().encode()
                for k,v in cattrs_str
            }
        except (AttributeError, ValueError) as e:
            raise ValueError(f'Invalid cattrs! {e}') from e

    return cattrs_str

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

def convert_str_date_size(date: str=None, size: str=None) -> int:
    """
    This function convert formatted date (str) to timestamp (int)
    and formatted size (str) to regular bytesize (int).
    """
    if date:
        if not date.replace('.','',1).isdigit():
            # Date can be also specified as string
            # time, i.e "21/05/23, 19:51:29".
            try:
                date = datetime.strptime(date, '%d/%m/%y, %H:%M:%S')
            except ValueError:
                # Maybe only Date/Month/Year string was specified?
                date = datetime.strptime(date, '%d/%m/%y')
            date = date.timestamp()
        else:
            date = float(date)
        return date

    if size:
        if not size.isdigit():
            # This filters can be also specified as string
            # size, i.e "1GB" or "112KB" or "100B", etc...
            size = formatted_bytes_to_int(size)
        else:
            size = int(size)
        return size

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
                filter[1] = parse_str_cattrs(filter[1])

            if filter[0] in ('min_time', 'max_time'):
                filter[1] = convert_str_date_size(date=filter[1])

            if filter[0] in ('min_size', 'max_size'):
                filter[1] = convert_str_date_size(size=filter[1])

            if filter[0] not in current_filter:
                current_filter[filter[0]] = [filter[1]]
            else:
                current_filter[filter[0]].append(filter[1])

    return tgbox.tools.SearchFilter(**include).exclude(**exclude)

def split_string(string: str, indent: int=0, symbol: str='->') -> str:
    """
    This function can split long string into the
    lines separated by the 'symbol' kwarg.

    'indent' == int(get_terminal_size().columns // 1.8)
    if 'indent' is not specified as optional kwarg.
    """
    available = int(get_terminal_size().columns // 1.8)
    available = 30 if available < 30 else available

    parts = []
    while string:
        parts.append(string[:available] + symbol)
        string = string[available:]

    if len(symbol):
        parts[-1] = parts[-1][:-len(symbol)]

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

def get_cli_folder() -> Path:
    """
    This function will return a Path to platform-
    specific .tgbox-cli data/cache folder.
    """
    cli_folders = {
        'windows': Path(str(expandvars('%APPDATA%'))) / '.tgbox-cli',
        '_other_os': Path.home() / '.tgbox-cli'
    }
    cli_folder = cli_folders.get(platform_sys().lower(), cli_folders['_other_os'])
    cli_folder.mkdir(parents=True, exist_ok=True)

    return cli_folder

def format_dxbf(
        dxbf: Union['tgbox.api.DecryptedRemoteBoxFile',
            'tgbox.api.DecryptedLocalBoxFile']) -> str:
    """
    This will make a colored information string from
    the DecryptedRemoteBoxFile or DecryptedLocalBoxFile
    """
    salt = urlsafe_b64encode(dxbf.file_salt.salt).decode()

    if dxbf.imported:
        idsalt = f'[[BRIGHT_BLUE]{str(dxbf.id)}[BRIGHT_BLUE]:'
    else:
        idsalt = f'[[BRIGHT_RED]{str(dxbf.id)}[BRIGHT_RED]:'

    idsalt += f'[BRIGHT_BLACK]{salt[:12]}[BRIGHT_BLACK]]'

    try:
        name = click.format_filename(dxbf.file_name)
    except UnicodeDecodeError:
        name = '[RED][Unable to display][RED]'

    size = f'[GREEN]{format_bytes(dxbf.size)}[GREEN]'

    if dxbf.duration:
        duration = str(timedelta(seconds=round(dxbf.duration,2)))
        duration = f' [CYAN]({duration.split(".")[0]})[CYAN]'
    else:
        duration = ''

    if hasattr(dxbf, '_updated_at_time'):
        time = datetime.fromtimestamp(dxbf._updated_at_time)
        time = f"* Updated at [CYAN]{time.strftime('%d/%m/%y, %H:%M:%S')}[CYAN] "
    else:
        time = datetime.fromtimestamp(dxbf.upload_time)
        time = f"* Uploaded at [CYAN]{time.strftime('%d/%m/%y, %H:%M:%S')}[CYAN] "

    version = f'v1.{dxbf.minor_version}' if dxbf.minor_version > 0 else 'ver N/A'
    time += f'[BRIGHT_BLACK]({version})[BRIGHT_BLACK]\n'

    mimedur = f'[WHITE]{dxbf.mime}[WHITE]' if dxbf.mime else 'regular file'
    if dxbf.preview: mimedur += '[BRIGHT_BLACK]*[BRIGHT_BLACK]'

    mimedur += duration

    if dxbf.cattrs:
        cattrs = deepcopy(dxbf.cattrs)
        for k,v in tuple(cattrs.items()):
            try:
                cattrs[k] = v.decode()
            except:
                cattrs[k] = '<HEXED>' + v.hex()
    else:
        cattrs = None

    file_path_valid = True
    if dxbf.file_path:
        file_path = str(dxbf.file_path)
    else:
        if hasattr(dxbf, 'directory'):
            tgbox.sync(dxbf.directory.lload(full=True))
            file_path = str(dxbf.directory)
        else:
            file_path = '[RED][Unknown Folder][RED]'
            file_path_valid = False

    if file_path_valid:
        safe_file_path = tgbox.tools.make_safe_file_path(file_path)

        path_cached = tgbox.defaults.DOWNLOAD_PATH / 'Files'
        path_cached = path_cached / safe_file_path / dxbf.file_name

        if path_cached.exists():
            if path_cached.stat().st_size == dxbf.size:
                name = f'[GREEN]{name}[GREEN]'
            else:
                name = f'[YELLOW]{name}[YELLOW]'
        else:
            name = f'[WHITE]{name}[WHITE]'

    formatted = (
       f"""\nFile: {idsalt} {name}\n"""
       f"""Path: {split_string(file_path, 6)}\n"""
       f"""Size: {size}({dxbf.size}), {mimedur}\n"""
    )
    if cattrs:
        formatted += "* CustomAttributes:\n"
        n = 1
        for k,v in tuple(cattrs.items()):
            color_ = 'GREEN' if n % 2 else 'YELLOW'
            n += 1

            v = split_string(v, 6, symbol='>')
            v = v.replace('\n',f'[{color_}]\n[{color_}]')

            formatted += (
                f'''   [WHITE]{k}[WHITE]: '''
                f'''[{color_}]{v}[{color_}]\n'''
            )
    formatted += time

    if isinstance(dxbf, tgbox.api.remote.DecryptedRemoteBoxFile)\
        and dxbf.sender:
            formatted += f'* Author: [YELLOW]{dxbf.sender}[YELLOW]\n'

    return color(formatted)


def format_dxbf_message(
        dxbf: Union['tgbox.api.DecryptedRemoteBoxFile',
            'tgbox.api.DecryptedLocalBoxFile']) -> str:
    """
    This will make a colored information string from the
    DecryptedRemoteBoxFile or DecryptedLocalBoxFile message
    """
    salt = urlsafe_b64encode(dxbf.file_salt.salt).decode()

    if dxbf.imported:
        idsalt = f'[[BRIGHT_BLUE]{str(dxbf.id)}[BRIGHT_BLUE]:'
    else:
        idsalt = f'[[BRIGHT_RED]{str(dxbf.id)}[BRIGHT_RED]:'

    idsalt += f'[BRIGHT_BLACK]{salt[:12]}[BRIGHT_BLACK]]'

    try:
        name = click.format_filename(dxbf.file_name)
    except UnicodeDecodeError:
        name = '[RED][Unable to display][RED]'

    time = datetime.fromtimestamp(dxbf.upload_time)
    time = f"* Sent at [CYAN]{time.strftime('%d/%m/%y, %H:%M:%S')}[CYAN] "

    version = f'v1.{dxbf.minor_version}' if dxbf.minor_version > 0 else 'ver N/A'
    time += f'[BRIGHT_BLACK]({version})[BRIGHT_BLACK]'

    if dxbf.file_path:
        file_path = str(dxbf.file_path)
        topic = f'[YELLOW]{Path(file_path).parts[2]}[YELLOW]'

        date = Path(*Path(file_path).parts[3:])
        date = f'[WHITE]{str(date)}[WHITE]'
    else:
        if hasattr(dxbf, 'directory'):
            tgbox.sync(dxbf.directory.lload(full=True))
            topic = f'[YELLOW]{str(dxbf.directory.parts[2])}[YELLOW]'

            date = Path(*dxbf.directory.parts[3:])
            date = f'[WHITE]{str(date)}[WHITE]'
        else:
            topic = '[RED][Unknown Topic][RED]'

    name = f'[BLUE]{dxbf.file_name}[BLUE]'

    text = split_string(dxbf.cattrs['text'].decode(), 5)
    text = f'[WHITE]{text}[WHITE]'

    author = f'[YELLOW]{dxbf.cattrs["author"].decode()}[YELLOW]'
    author += f' [BRIGHT_BLACK]({dxbf.cattrs["author_id"].decode()})[BRIGHT_BLACK]'

    formatted = (
       f"""\n {idsalt} {name} ({topic}:{date})\n"""
       f""" * Author: {author}\n"""
       f""" {time}\n |\n [WHITE]@[WHITE] Message: {text}"""
    )
    return color(formatted)
