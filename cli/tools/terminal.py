"""Tools that can be useful for Terminal (e.g `clear`)"""

import click

from platform import system as platform_system
from re import finditer as re_finditer
from os import system as os_system

from ..config import TGBOX_CLI_NOCOLOR


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

class ProgressBar:
    """
    This is a little wrapper around enlighten

    from enlighten import get_manager

    manager = get_manager()

    tgbox.api.DecryptedLocalBox.push_file(
        ..., progress_callback=ProgressBar(manager).update
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
            BAR = (
                '{desc} | {percentage:3.0f}% |{bar}| ({count}/{total}) '
                '[ETA {eta}, ELA {elapsed}]'
            )
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
    """This function will clear user Terminal"""
    if platform_system().lower() == 'windows':
        clear_command = 'cls'
    else:
        clear_command = 'clear'

    os_system(clear_command)

def echo(text: str, **kwargs):
    """
    click.echo with auto colorize(text) and disabling color
    if TGBOX_CLI_NOCOLOR is True.
    """
    click.echo(colorize(text), **kwargs, color=(not TGBOX_CLI_NOCOLOR))
