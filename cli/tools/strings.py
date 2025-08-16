"""Tools focused on string manipulation"""

import click
from shutil import get_terminal_size


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
