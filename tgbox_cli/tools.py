import click
import tgbox

from typing import Union
from copy import deepcopy

from typing import AsyncGenerator
from urllib3.util import parse_url
from re import finditer as re_finditer

from base64 import urlsafe_b64encode
from shutil import get_terminal_size

from datetime import datetime, timedelta
from platform import system as platform_sys

from pathlib import Path
from os.path import expandvars
from os import system as os_system

# ---------------------------------------------- #
# Started from the CLI v1.4 we will use slightly
# different approach to colors. Now, color codes
# are named after first letter of Color name (
# except Black, it's code is 'X', because there
# is already Blue, which code is defined as 'B')
# and the next number will define if it's
# a regular (0) or a bright (1) variant.
# ---------------------------------------------- #
AVAILABLE_COLORS = {
 'B0': 'blue',
 'B1': 'bright_blue',
 'C0': 'cyan',
 'C1': 'bright_cyan',
 'G0': 'green',
 'G1': 'bright_green',
 'M0': 'magenta',
 'M1': 'bright_magenta',
 'R0': 'red',
 'R1': 'bright_red',
 'W0': 'white',
 'W1': 'bright_white',
 'X0': 'black',
 'X1': 'bright_black',
 'Y0': 'yellow',
 'Y1': 'bright_yellow'
}
# ---------------------------------------------- #
# We can also suffix Color codes with 'b' (Bold)
# or 'i' (Italic), so colorize() func will know
# what exactly we want. E.g: C0b is a regular
# cyan with bold formatting. M1i is a bright
# magenta with italic formatting. W0il is a
# regular italic white which will blink.
# ---------------------------------------------- #
# In string, we will need to specify color as
# follows (e.g): [R0i]Italic red![X]
# ---------------------------------------------- #
_color_formattings = {
 'i': 'italic',
 'b': 'bold',
 'd': 'dim',
 'u': 'underline',
 'o': 'overline',
 'r': 'reverse',
 'l': 'blink',
 'g': 'bg',
 's': 'strikethrough'
}
_COLOR_SEARCH_PATTERN = r'\[[A-Z][0-9][a-z]*\]'

def _get_color_params(color_code: str) -> tuple:
    """
    Will return formatting params for click.style.

    Arguments:
        color_code, str:
            Color code. I.e "X1ls"
    """
    params = {}
    for formatting in color_code[2:]:
        if formatting in _color_formattings:
            format_n = _color_formattings[formatting]

            if format_n not in params:
                params[format_n] = True

    color = AVAILABLE_COLORS.get(color_code[:2], None)
    return (color, params)

def colorize(text: str) -> str:
    """
    Will color special formatted parts of text to the
    specified color. [R1]This will be red[X], [B0]
    and this is blue[X]. Color should be in the
    tools.AVAILABLE_COLORS list and should be
    supported by the click.style function.

    This "Color Codes" support different format
    types that you can apped after color code
    (e.g X1 -- bright_black). For example,
    'b' is bold, and 'i' is italic. 'l' will
    blink. Full code is "X1bil". Try this:

    echo(colorize('[X1bil]Black Sabbath[X]'))

    See source code of 'tools.py' for more details
    on formatting. Typical users typically would
    not use this function directly.
    """
    color_codes = {}
    for color_code in re_finditer(_COLOR_SEARCH_PATTERN, text):
        if color_code not in color_codes:
            color_code = color_code.group().lstrip('[').rstrip(']')
            color_codes[color_code] = None

    invalid_codes = []
    for c in color_codes:
        params = _get_color_params(c)

        if params[0]:
            color_codes[c] = params
        else:
            invalid_codes.append(c)

    for invalid_code in invalid_codes:
        color_codes.pop(invalid_code)

    del invalid_codes

    for color_code, params in color_codes.items():
        ansi = click.style(
            text = '',
            fg = params[0],
            reset = False,
            **params[1]
        )
        text = text.replace(f'[{color_code}]', ansi)

    text = text.replace('[X]', '\x1b[0m')
    text = text.replace(r'[\X]', '[X]') # If was escaped
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
                colorize(f'[{block_total} [W0b]Chunks[X] [G0b]DONE[X]],') +\
                ' {elapsed} ' + colorize('[W0b]Elapsed[X]')

        elif self.last_id: # If .update_2
            self.counter.counter_format = colorize('[W0b]@[X] ') + '{count:d} ' +\
                colorize('[W0b]Files[X] [G0b]SYNCED[X], ') + '{elapsed} ' +\
                colorize('[W0b]Elapsed[X], {rate:.0f} [W0b]Files[X]/second')

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
    limit = int(get_terminal_size().columns // 1.8)
    limit = 30 if limit < 30 else limit

    parts = []
    while string:
        parts.append(string[:limit] + symbol)
        string = string[limit:]

    if len(symbol):
        parts[-1] = parts[-1][:-len(symbol)]

    joinsymbols = '\n'+' '*indent
    return joinsymbols.join(parts).strip()

def break_string(string: str, indent: int=0) -> str:
    """
    This function can break long string into the
    lines separated by the whitespace. It break
    line only after space symbol, thus doesn't
    break color codes.

    'indent' == int(get_terminal_size().columns // 1.8)
    if 'indent' is not specified as optional kwarg.
    """
    result_str, cycle_str = '', ''
    string_spl = string.split()
    actual_cycle_str_len = 0

    limit = int(get_terminal_size().columns // 1.8)
    limit = 30 if limit < 30 else limit

    while string_spl:
        part = string_spl.pop(0)
        unst = click.unstyle(part)

        actual_cycle_str_len += len(unst)

        if actual_cycle_str_len > limit:
            if cycle_str:
                indentw = '\n'+' '*indent
                result_str += cycle_str + indentw

                cycle_str = ''
                actual_cycle_str_len = 0

        cycle_str += (part + ' ')

    return (result_str + cycle_str)

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
        idsalt = f'[[B1b]{str(dxbf.id)}[X]:'
    else:
        idsalt = f'[[R1b]{str(dxbf.id)}[X]:'

    idsalt += f'[X1b]{salt[:12]}[X]]'

    try:
        name = click.format_filename(dxbf.file_name)
    except UnicodeDecodeError:
        name = '[R0b][Unable to display][X]'

    size = f'[G0b]{format_bytes(dxbf.size)}[X]'

    if dxbf.duration:
        duration = str(timedelta(seconds=round(dxbf.duration,2)))
        duration = f' [C0b]({duration.split(".")[0]})[X]'
    else:
        duration = ''

    if hasattr(dxbf, '_updated_at_time'):
        time = datetime.fromtimestamp(dxbf._updated_at_time)
        time = f"* Updated at [C0b]{time.strftime('%d/%m/%y, %H:%M:%S')}[X] "
    else:
        time = datetime.fromtimestamp(dxbf.upload_time)
        time = f"* Uploaded at [C0b]{time.strftime('%d/%m/%y, %H:%M:%S')}[X] "

    version = f'v1.{dxbf.minor_version}' if dxbf.minor_version > 0 else 'ver N/A'
    time += f'[X1b]({version})[X]\n'

    mimedur = f'[W0b]{dxbf.mime}[X]' if dxbf.mime else 'regular file'
    if dxbf.preview: mimedur += '[X1b]*[X]'

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
            file_path = '[R0b][Unknown Folder][X]'
            file_path_valid = False

    if file_path_valid:
        safe_file_path = tgbox.tools.make_safe_file_path(file_path)

        path_cached = tgbox.defaults.DOWNLOAD_PATH / 'Files'
        path_cached = path_cached / safe_file_path / dxbf.file_name

        if path_cached.exists():
            if path_cached.stat().st_size == dxbf.size:
                name = f'[G0b]{name}[X]'
            else:
                name = f'[Y0b]{name}[X]'
        else:
            name = f'[W0b]{name}[X]'

    formatted = (
       f'\nFile: {idsalt} {name}\n'
       f'Path: {split_string(file_path, 6)}\n'
       f'Size: {size}({dxbf.size}), {mimedur}\n'
    )
    if cattrs:
        formatted += "* CustomAttributes:\n"
        n = 1
        for k,v in tuple(cattrs.items()):
            color_ = 'G0b' if n % 2 else 'Y0b'
            n += 1

            v = split_string(v, 6, symbol='>')
            v = v.replace('\n',f'[{color_}]\n[X]')

            formatted += (
                f'   [W0b]{k}[X]: '
                f'[{color_}]{v}[X]\n'
            )
    formatted += time

    if isinstance(dxbf, tgbox.api.remote.DecryptedRemoteBoxFile)\
        and dxbf.sender:
            formatted += f'* Author: [Y0b]{dxbf.sender}[X]'

            if dxbf.sender_id:
                if dxbf.sender_id < 0: # Channel
                    author = dxbf.sender_entity.username
                    author = f'@{author}' if author else author.title
                    id_ = f'Channel {dxbf.sender_id}'
                else: # User
                    author = dxbf.sender_entity.username
                    author = f'@{author}' if author else author.first_name

                    if dxbf.sender_entity.last_name:
                        author += f' {author.last_name}'

                    id_ = f'User {dxbf.sender_id}'

                formatted += f' [X1]({id_})[X]'

            formatted += '\n'

    return colorize(formatted)

def format_dxbf_message(
        dxbf: Union['tgbox.api.DecryptedRemoteBoxFile',
            'tgbox.api.DecryptedLocalBoxFile']) -> str:
    """
    This will make a colored information string from the
    DecryptedRemoteBoxFile or DecryptedLocalBoxFile message
    """
    salt = urlsafe_b64encode(dxbf.file_salt.salt).decode()

    if dxbf.imported:
        idsalt = f'[[B1b]{str(dxbf.id)}[X]:'
    else:
        idsalt = f'[[R1b]{str(dxbf.id)}[X]:'

    idsalt += f'[X1b]{salt[:12]}[X]]'

    try:
        name = click.format_filename(dxbf.file_name)
    except UnicodeDecodeError:
        name = '[R0b][Unable to display][X]'

    time = datetime.fromtimestamp(dxbf.upload_time)
    time = f"* Sent at [C0b]{time.strftime('%d/%m/%y, %H:%M:%S')}[X] "

    version = f'v1.{dxbf.minor_version}' if dxbf.minor_version > 0 else 'ver N/A'
    time += f'[X1b]({version})[X]'

    if dxbf.file_path:
        file_path = str(dxbf.file_path)
        topic = f'[Y0b]{Path(file_path).parts[2]}[X]'

        date = Path(*Path(file_path).parts[3:])
        date = f'[W0]{str(date)}[X]'
    else:
        if hasattr(dxbf, 'directory'):
            tgbox.sync(dxbf.directory.lload(full=True))
            topic = f'[Y0b]{str(dxbf.directory.parts[2])}[X]'

            date = Path(*dxbf.directory.parts[3:])
            date = f'[W0]{str(date)}[X]'
        else:
            topic = '[R0b][Unknown Topic][X]'

    name = f'[B0b]{dxbf.file_name}[X]'

    text = dxbf.cattrs['text'].decode()

    unformatt_text = break_string(text, 5)
    colorized_text = break_string(colorize(text), 5)

    if unformatt_text == colorized_text:
        text = f'[W0b]{unformatt_text}[X]'
    else:
        text = colorized_text

    if getattr(dxbf, 'sender_entity', None):
        if dxbf.sender_id < 0: # Channel
            author = dxbf.sender_entity.username
            author = f'@{author}' if author else author.title
            id_ = f'Channel {dxbf.sender_id}'
        else: # User
            author = dxbf.sender_entity.username
            author = f'@{author}' if author else author.first_name

            if dxbf.sender_entity.last_name:
                author += f' {author.last_name}'

            id_ = f'User {dxbf.sender_id}'

        author = f'[Y0b]{author}[X] [G0b]√[X]'
        author += f' [X1]({id_})[X]'
    else:
        author = f'@{dxbf.cattrs["author"].decode()}'
        id_ = f'{dxbf.cattrs["author_id"].decode().lstrip("id")}'

        author = f'[X1b]{author}[X] [R0b]x[X]'
        author += f' [X1](User {id_})[X]'

    formatted = (
       f'\n {idsalt} {name} ({topic}:{date})\n'
       f' * Author: {author}\n'
       f' {time}\n |\n [W0b]@[X] Message: {text}'
    )
    return colorize(formatted)
