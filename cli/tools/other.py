"""Other tools and helpers"""

import click

from typing import Optional, Union, AsyncGenerator, List
from datetime import datetime, timedelta
from base64 import urlsafe_b64encode
from copy import deepcopy
from pathlib import Path

from .strings import split_string, break_string
from .convert import format_bytes
from .terminal import colorize
from ..config import tgbox, HIDDEN_CATTRS


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

def _construct_formatted_dxbf(
        id: int, name: str, path: str, path_valid: bool, size: int,
        salt: bytes, time: int, has_preview: bool, duration: int,
        mime: Optional[str], cattrs: Optional[dict], minor_version: int,
        imported: bool, sender: Optional[str], sender_id: Optional[int],
        chunks_downloaded: int, is_remote: bool, multipart: bool) -> str:
    """

    if chunks_downloaded is 0, -- no chunks downloaded, if 1 -- some chunks
    downloaded, if 2 -- all chunks downloaded (file is fully downloaded).
    """
    salt = urlsafe_b64encode(salt).decode()

    if imported:
        idsalt = f'[[B1b]{id}[X]:'
    elif multipart:
        idsalt = f'[[Y1b]{id}[X]:'
    else:
        idsalt = f'[[R1b]{id}[X]:'

    idsalt += f'[X1b]{salt[:12]}[X]]'
    try:
        name = click.format_filename(name)
    except UnicodeDecodeError:
        name = '[R0b][Unable to display][X]'

    fsize = f'[G0b]{format_bytes(size)}[X]'

    if duration:
        duration = str(timedelta(seconds=round(duration,2)))
        duration = f' [C0b]({duration.split(".")[0]})[X]'
    else:
        duration = ''

    time = datetime.fromtimestamp(time)
    if is_remote:
        time = f"* Updated at [C0b]{time.strftime('%d/%m/%y, %H:%M:%S')}[X] "
    else:
        time = f"* Uploaded at [C0b]{time.strftime('%d/%m/%y, %H:%M:%S')}[X] "

    version = f'v1.{minor_version}' if minor_version > 0 else 'ver N/A'
    time += f'[X1b]({version})[X]\n'

    mimedur = f'[W0b]{mime}[X]' if mime else 'regular file'
    if has_preview:
        mimedur += '[X1b]*[X]'

    mimedur += duration

    if cattrs:
        cattrs = deepcopy(cattrs)
        for k,v in tuple(cattrs.items()):
            try:
                cattrs[k] = v.decode()
            except:
                cattrs[k] = '<HEXED>' + v.hex()
    else:
        cattrs = None

    name = f'[W0b]{name}[X]'
    if path_valid:
        if chunks_downloaded == 2:
            name = f'[G0b]{name}[X]'
        elif chunks_downloaded == 1:
            name = f'[Y0b]{name}[X]'
    else:
        path = '[R0b][Unknown Folder][X]'

    formatted = (
       f'\nFile: {idsalt} {name}\n'
       f'Path: {split_string(path, 6)}\n'
       f'Size: {fsize}({size}), {mimedur}\n'
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

    if sender:
        formatted += f'* Author: [Y0b]{sender}[X]'

        if sender_id:
            if sender_id < 0: # Channel
                fsender_id = f'Channel {sender_id}'
            else: # User
                fsender_id = f'User {sender_id}'

            formatted += f' [X1]({fsender_id})[X]'

        formatted += '\n'

    return colorize(formatted)

def format_dxbf(
        dxbf: Union['tgbox.api.DecryptedRemoteBoxFile',
            'tgbox.api.DecryptedLocalBoxFile']) -> str:
    """
    This will make a colored information string from
    the DecryptedRemoteBoxFile or DecryptedLocalBoxFile
    """
    if dxbf.cattrs:
        cattrs = deepcopy(dxbf.cattrs)

        for cattr in HIDDEN_CATTRS:
            if cattr in cattrs:
                cattrs.pop(cattr)
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
            file_path = ''
            file_path_valid = False

    chunks_downloaded = 0

    if file_path_valid:
        safe_file_path = tgbox.tools.make_safe_file_path(file_path)

        path_cached = tgbox.defaults.DOWNLOAD_PATH / 'Files'
        path_cached = path_cached / safe_file_path / dxbf.file_name

        if path_cached.exists():
            if path_cached.stat().st_size == dxbf.size:
                chunks_downloaded = 2
            else:
                chunks_downloaded = 1

    return _construct_formatted_dxbf(
        id = dxbf.id,
        name = dxbf.file_name,
        path = file_path,
        path_valid = file_path_valid,
        size = dxbf.size,
        salt = dxbf.file_salt.salt,
        time = getattr(dxbf, 'updated_at_time', dxbf.upload_time),
        has_preview = bool(dxbf.preview),
        duration = dxbf.duration,
        mime = dxbf.mime,
        cattrs = cattrs,
        minor_version = dxbf.minor_version,
        imported = dxbf.imported,
        sender = getattr(dxbf, 'sender', None),
        sender_id = getattr(dxbf, 'sender_id', None),
        chunks_downloaded = chunks_downloaded,
        is_remote = hasattr(dxbf, 'updated_at_time'),
        multipart = False
    )

def format_dxbf_multipart(
        dxbf_list: List[Union['tgbox.api.DecryptedRemoteBoxFile',
            'tgbox.api.DecryptedLocalBoxFile']]) -> str:
    """
    This will make a colored information string from
    the DecryptedRemoteBoxFile or DecryptedLocalBoxFile
    multipart file.
    """
    # If (for some reason), multipart file will miss
    # one of its parts, the whole formatted DXBF will
    # be red, because we can not get actual size and
    # data. User will not be able to download such
    # file as full, but only in parts.
    MULTIPART_VALID = True

    total_size = 0
    for dxbf in dxbf_list:
        total_size += dxbf.size

    dxbf = dxbf_list[0]
    if dxbf.cattrs:
        cattrs = deepcopy(dxbf.cattrs)

        total = tgbox.tools.bytes_to_int(cattrs.pop('__mp_total'))
        if len(dxbf_list) != total:
            MULTIPART_VALID = False

        cattrs.pop('__mp_previous')
        cattrs.pop('__mp_part')
    else:
        cattrs = None

    file_name = dxbf_list[0].file_name
    file_name = '-'.join(file_name.split('-')[:-1])

    file_path_valid = True

    if dxbf.file_path:
        file_path = str(dxbf.file_path)
    else:
        if hasattr(dxbf, 'directory'):
            tgbox.sync(dxbf.directory.lload(full=True))
            file_path = str(dxbf.directory)
        else:
            file_path = ''
            file_path_valid = False

    chunks_downloaded = 0

    if file_path_valid:
        safe_file_path = tgbox.tools.make_safe_file_path(file_path)

        path_cached = tgbox.defaults.DOWNLOAD_PATH / 'Files'
        path_cached = path_cached / safe_file_path / file_name

        if path_cached.exists():
            if path_cached.stat().st_size == dxbf.size:
                chunks_downloaded = 2
            else:
                chunks_downloaded = 1

    formatted =_construct_formatted_dxbf(
        id = dxbf.id,
        name = file_name,
        path = file_path,
        path_valid = file_path_valid,
        size = total_size,
        salt = dxbf.file_salt.salt,
        time = getattr(dxbf, 'updated_at_time', dxbf.upload_time),
        has_preview = bool(dxbf.preview),
        duration = dxbf.duration,
        mime = dxbf.mime,
        cattrs = cattrs,
        minor_version = dxbf.minor_version,
        imported = dxbf.imported,
        sender = getattr(dxbf, 'sender', None),
        sender_id = getattr(dxbf, 'sender_id', None),
        chunks_downloaded = chunks_downloaded,
        is_remote = hasattr(dxbf, 'updated_at_time'),
        multipart = True
    )
    if not MULTIPART_VALID:
        formatted = click.unstyle(formatted)
        formatted += 'x File is broken (missing parts!)\n'

        formatted = formatted.split('\n')
        for indx, f in enumerate(formatted):
            formatted[indx] = f'[R1]{f}[X]'

        return colorize('\n'.join(formatted))

    return formatted

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
