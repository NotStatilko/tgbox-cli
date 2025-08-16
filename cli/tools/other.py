"""Other tools and helpers"""

import click

from typing import Union, AsyncGenerator
from datetime import datetime, timedelta
from base64 import urlsafe_b64encode
from copy import deepcopy
from pathlib import Path

from .strings import split_string, break_string
from .convert import format_bytes
from .terminal import colorize
from ..config import tgbox


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
