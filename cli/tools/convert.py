"""Functions that convert/format stuff to other stuff"""

from urllib.parse import urlparse
from datetime import datetime
from ..config import tgbox


def format_bytes(size):
    """
    This function will convert integer bytesize to
    string, e.g 1000000000 -> 1GB (one gigabyte).
    """
    power, n = 10**3, 0
    power_labels = {0 : '', 1: 'K', 2: 'M', 3: 'G'}

    while size > power:
        size /= power
        n += 1
    return f'{round(size,1)}{power_labels[n]}B'

def formatted_bytes_to_int(formatted: str) -> int:
    """
    This function will convert string bytesize to
    integer bytesize. E.g 1GB -> 1000000000.
    """
    power_labels = {'KB': 1000, 'MB': 1e+6, 'GB': 1e+9}

    if formatted[-2:] in power_labels:
        formatted = float(formatted[:-2]) \
            * power_labels[formatted[-2:]]

    elif formatted[-1] == 'B':
        formatted = float(formatted[:-1])

    return int(formatted)

def filters_to_searchfilter(filters: tuple):
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
                if not filter[1].replace('.','',1).isdigit():
                    # Date could be also specified as string
                    # time, e.g "21/05/23, 19:51:29".
                    try:
                        filter[1] = datetime.strptime(filter[1], '%d/%m/%y, %H:%M:%S')
                    except ValueError:
                        # Maybe only Date/Month/Year string was specified?
                        filter[1] = datetime.strptime(filter[1], '%d/%m/%y')
                    filter[1] = filter[1].timestamp()
                else:
                    filter[1] = float(filter[1])

            if filter[0] in ('min_size', 'max_size'):
                if not filter[1].isdigit():
                    # These filters can be also specified as string
                    # size, i.e "1GB" or "112KB" or "100B", etc...
                    filter[1] = formatted_bytes_to_int(filter[1])
                else:
                    filter[1] = int(filter[1])

            if filter[0] not in current_filter:
                current_filter[filter[0]] = [filter[1]]
            else:
                current_filter[filter[0]].append(filter[1])

    return tgbox.tools.SearchFilter(**include).exclude(**exclude)

def env_proxy_to_pysocks(env_proxy: str) -> tuple:
    """
    This function will parse the http_proxy EnvVar format
    and convert it to the PySocks format (tuple).
    """
    p = urlparse(env_proxy)
    return (p.scheme, p.hostname, p.port, True, p.username, p.password)

def parse_str_cattrs(cattrs_str: str) -> dict:
    """
    This function can convert str CAttrs of TGBOX-CLI
    format into the dictionary. Also accepts raw
    CAttrs as hex. For example:
        cattrs="FF000004746578740000044F5A5A5900000474797065000005696D616765"
        || (or)
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
