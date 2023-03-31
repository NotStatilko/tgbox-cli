import click
import tgbox

from time import sleep
from typing import Union
from pathlib import Path
from copy import deepcopy
from hashlib import sha256

from pickle import loads, dumps
from sys import platform, stdout
from base64 import urlsafe_b64encode

from traceback import format_exception
from datetime import datetime, timedelta

from subprocess import run as subprocess_run, PIPE
from os import getenv, _exit, system as os_system
from asyncio import gather, get_event_loop

from tools import (
    Progress, sync_async_gen, exit_program,
    format_bytes, splitpath, env_proxy_to_pysocks,
    filters_to_searchfilter, clear_console, color
)
from enlighten import get_manager as get_enlighten_manager

# tools.color with a click.echo function
echo = lambda t,**k: click.echo(color(t), **k)

__version__ = '1.0_' + tgbox.defaults.VERSION
tgbox.defaults.VERSION = __version__

# Please DO NOT use this parameters in your projects.
# You can get your own at my.telegram.org. Thanks.
API_ID, API_HASH = 2210681, '33755adb5ba3c296ccf0dd5220143841'

def get_sk() -> Union[str, None]:
    """
    This will return StateKey
    from env vars, if present.
    """
    return getenv('TGBOX_SK')

def check_sk():
    if not get_sk():
        echo(
            '''[RED]You should run[RED] [WHITE]tgbox-cli '''
            '''cli-init[WHITE] [RED]firstly.[RED]'''
        )
        tgbox.sync(exit_program())
    else:
        return True

def get_state(state_key: str) -> dict:
    state_enc_key = sha256(state_key.encode()).digest()
    state_file = Path('sess_' + sha256(state_enc_key).hexdigest())

    if not state_file.exists():
        return {}
    else:
        with open(state_file,'rb') as f:
            d = tgbox.crypto.AESwState(state_enc_key).decrypt(f.read())
            return loads(d)

def write_state(state: dict, state_key: str) -> None:
    state_enc_key = sha256(state_key.encode()).digest()
    state_file = Path('sess_' + sha256(state_enc_key).hexdigest())

    with open(state_file,'wb') as f:
        f.write(tgbox.crypto.AESwState(state_enc_key).encrypt(dumps(state)))

def _select_box(ignore_remote: bool=False):
    check_sk()

    state_key = get_sk()
    state = get_state(state_key)

    if 'TGBOXES' not in state:
        echo(
            '''[RED]You didn\'t connected box yet. Use[RED] '''
            '''[WHITE]box-open[WHITE] [RED]command.[RED]'''
        )
        tgbox.sync(exit_program())
    else:
        box_path = state['TGBOXES'][state['CURRENT_TGBOX']][0]
        basekey  = state['TGBOXES'][state['CURRENT_TGBOX']][1]

        dlb = tgbox.sync(tgbox.api.get_localbox(
            tgbox.keys.BaseKey(basekey), box_path)
        )
        if not ignore_remote:
            if getenv('https_proxy'):
                proxy = env_proxy_to_pysocks(getenv('https_proxy'))

            elif getenv('http_proxy'):
                proxy = env_proxy_to_pysocks(getenv('http_proxy'))
            else:
                proxy = None

            drb = tgbox.sync(tgbox.api.get_remotebox(dlb, proxy=proxy))
        else:
            drb = None

        return dlb, drb

def _select_remotebox(number: int, prefix: str):
    tc, count, erb = _select_account(), 1, None

    for d in sync_async_gen(tc.iter_dialogs()):
        if prefix in d.title and d.is_channel:
            if count != number:
                count += 1
            else:
                erb = tgbox.api.remote.EncryptedRemoteBox(d,tc)
                break

    if not erb:
        echo(f'[RED]RemoteBox by number={number} not found.[RED]')
        tgbox.sync(exit_program())
    else:
        return erb

def _select_account() -> tgbox.api.TelegramClient:
    check_sk()

    state_key, tc = get_sk(), None
    state = get_state(state_key)

    if 'ACCOUNTS' not in state and 'CURRENT_TGBOX' in state:
        echo(
            '''\nYou [RED]didn\'t connected[RED] account with '''
            '''[WHITE]account-connect, [WHITE]however, you '''
            '''already connected Box.'''
        )
        if click.confirm('\nDo you want to use its account?'):
            dlb, drb = _select_box()
            tc = drb._tc
            tgbox.sync(dlb.done())

    elif 'ACCOUNTS' in state:
        session = state['ACCOUNTS'][state['CURRENT_ACCOUNT']]

        tc = tgbox.api.TelegramClient(
            session=session,
            api_id=API_ID,
            api_hash=API_HASH
        )
    if not tc:
        echo(
          '''[RED]You should run [RED][WHITE]tgbox-cli '''
          '''account-connect [WHITE][RED]firstly.[RED]'''
        )
        tgbox.sync(exit_program())

    if getenv('https_proxy'):
        proxy = env_proxy_to_pysocks(getenv('https_proxy'))

    elif getenv('http_proxy'):
        proxy = env_proxy_to_pysocks(getenv('http_proxy'))
    else:
        proxy = None

    tc.set_proxy(proxy)
    tgbox.sync(tc.connect())
    return tc

def _format_dxbf(
        dxbf: Union[tgbox.api.DecryptedRemoteBoxFile,
            tgbox.api.DecryptedLocalBoxFile]) -> str:
    """
    This will make a colored information string from
    the DecryptedRemoteBoxFile or DecryptedLocalBoxFile
    """
    salt = urlsafe_b64encode(dxbf.file_salt).decode()

    if dxbf.imported:
        idsalt = f'[[BRIGHT_BLUE]{str(dxbf.id)}[BRIGHT_BLUE]:'
    else:
        idsalt = f'[[BRIGHT_RED]{str(dxbf.id)}[BRIGHT_RED]:'

    idsalt += f'[BRIGHT_BLACK]{salt[:12]}[BRIGHT_BLACK]]'
    try:
        name = f'[WHITE]{click.format_filename(dxbf.file_name)}[WHITE]'
    except UnicodeDecodeError:
        name = '[RED][Unable to display][RED]'

    size = f'[GREEN]{format_bytes(dxbf.size)}[GREEN]'

    if dxbf.duration:
        duration = str(timedelta(seconds=round(dxbf.duration,2)))
        duration = f'[CYAN] ({duration.split(".")[0]})[CYAN]'
    else:
        duration = ''

    time = datetime.fromtimestamp(dxbf.upload_time)
    time = f"[CYAN]{time.strftime('%d/%m/%y, %H:%M:%S')}[CYAN]"

    mimedur = f'[WHITE]{dxbf.mime}[WHITE]' if dxbf.mime else 'regular file'
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

    if dxbf.file_path:
        file_path = str(dxbf.file_path)
    else:
        if hasattr(dxbf, 'directory'):
            tgbox.sync(dxbf.directory.lload(full=True))
            file_path = str(dxbf.directory)
        else:
            file_path = '[RED][Unknown Folder][RED]'

    formatted = (
       f"""\nFile: {idsalt} {name}\n"""
       f"""Path: {splitpath(file_path, 6)}\n"""
       f"""Size: {size}({dxbf.size}), {mimedur}\n"""
    )
    if cattrs:
        formatted += "* CustomAttributes:\n"
        n = 1
        for k,v in tuple(cattrs.items()):
            color_ = 'GREEN' if n % 2 else 'YELLOW'; n+=1
            formatted += (
                f'''   [WHITE]{k}[WHITE]: '''
                f'''[{color_}]{v}[{color_}]\n'''
            )
    formatted += f"* Uploaded {time}\n"
    return color(formatted)

@click.group()
def cli():
   pass

def safe_cli():
    try:
        cli()
    except Exception as e:
        if getenv('TGBOX_DEBUG'):
            e = ''.join(format_exception(
                etype = None,
                value = e,
                tb = e.__traceback__
            ))
        echo(f'[RED]{e}[RED]\n')
        _exit(1)

@cli.command()
@click.option(
    '--phone', '-p', required=True, prompt=True,
    help='Phone number of your Telegram account'
)
def account_connect(phone):
    """Connect to Telegram"""
    check_sk()

    tc = tgbox.api.TelegramClient(
        phone_number=phone,
        api_id=API_ID,
        api_hash=API_HASH
    )
    echo('[CYAN]Connecting to Telegram...[CYAN]')
    tgbox.sync(tc.connect())

    echo('[CYAN]Sending code request...[CYAN]')
    tgbox.sync(tc.send_code())

    code = click.prompt('Received code', type=int)
    password = click.prompt('Password', hide_input=True)

    echo('[CYAN]Trying to sign-in...[CYAN] ', nl=False)
    tgbox.sync(tc.log_in(code=code, password=password))

    echo('[GREEN]Successful![GREEN]')
    echo('[CYAN]Updating local data...[CYAN] ', nl=False)

    state_key = get_sk()
    state = get_state(state_key)

    tc_id = tgbox.sync(tc.get_me()).id

    if 'ACCOUNTS' not in state:
        state['ACCOUNTS'] = [tc.session.save()]
        state['CURRENT_ACCOUNT'] = 0 # Index
    else:
        disconnected_sessions = []
        for session in state['ACCOUNTS']:

            other_tc = tgbox.api.TelegramClient(
                session=session,
                api_id=API_ID,
                api_hash=API_HASH
            )
            other_tc = tgbox.sync(other_tc.connect())
            try:
                other_tc_id = tgbox.sync(other_tc.get_me()).id
            except AttributeError:
                # If session was disconnected
                disconnected_sessions.append(session)
                continue

            if other_tc_id == tc_id:
                tgbox.sync(tc.log_out())
                echo('[RED]Account already added[RED]')
                tgbox.sync(exit_program())

        for d_session in disconnected_sessions:
            state['ACCOUNTS'].remove(d_session)

        state['ACCOUNTS'].append(tc.session.save())
        state['CURRENT_ACCOUNT'] = len(state['ACCOUNTS']) - 1

    write_state(state, state_key)
    echo('[GREEN]Successful![GREEN]')
    tgbox.sync(exit_program())

@cli.command()
@click.option(
    '--number','-n', required=True, type=int,
    help='Number of connected account'
)
@click.option(
    '--log-out', is_flag=True,
    help='Will log out from account if specified'
)
def account_disconnect(number, log_out):
    """Will disconnect selected account"""
    state_key = get_sk()
    state = get_state(state_key)

    if 'ACCOUNTS' not in state or not state['ACCOUNTS']:
        echo('[RED]You don\'t have any connected account.[RED]')
        tgbox.sync(exit_program())

    elif number < 1 or number > len(state['ACCOUNTS']):
        echo(
            f'''[RED]There is no account #{number}. Use [RED]'''
             '''[WHITE]account-list[WHITE] [RED]command.[RED]'''
        )
    if log_out:
        session = state['ACCOUNTS'][number-1]

        tc = tgbox.api.TelegramClient(
            session=session,
            api_id=API_ID,
            api_hash=API_HASH
        )
        tgbox.sync(tc.connect())
        tgbox.sync(tc.log_out())

    state['ACCOUNTS'].pop(number-1)

    if not state['ACCOUNTS']:
        state.pop('ACCOUNTS')
        state.pop('CURRENT_ACCOUNT')
        echo('[GREEN]Disconnected. No more accounts.[GREEN]')
    else:
        state['CURRENT_ACCOUNT'] = 0
        echo('[GREEN]Disconnected & switched to the account #1[GREEN]')
        write_state(state, state_key)
        tgbox.sync(exit_program())

@cli.command()
def account_list():
    """List all connected accounts"""
    check_sk()

    state_key = get_sk()
    state = get_state(state_key)

    if 'ACCOUNTS' not in state or not state['ACCOUNTS']:
        echo(
            '''[RED]You didn\'t connected any account yet. Use[RED] '''
            '''[WHITE]account-connect[WHITE] [RED]command firstly.[RED]'''
        )
    else:
        echo(
            '''\n[WHITE]You\'re using account[WHITE] [RED]'''
           f'''#{str(state['CURRENT_ACCOUNT'] + 1)}[RED]\n'''
        )
        disconnected_sessions = []
        for count, session in enumerate(state['ACCOUNTS']):
            try:
                tc = tgbox.api.TelegramClient(
                    session=session,
                    api_id=API_ID,
                    api_hash=API_HASH
                )
                tc = tgbox.sync(tc.connect())
                info = tgbox.sync(tc.get_me())

                name = f'@{info.username}' if info.username else info.first_name
                echo(f'[WHITE]{count+1})[WHITE] [BLUE]{name}[BLUE] (id{info.id})')
            except AttributeError:
                # If session was disconnected
                echo(f'#[WHITE]{count+1}[WHITE] [RED]disconnected, so removed[RED]')
                disconnected_sessions.append(session)

        for d_session in disconnected_sessions:
            state['ACCOUNTS'].remove(d_session)

        write_state(state, state_key)

    tgbox.sync(exit_program())

@cli.command()
@click.option(
    '--number', '-n', required=True, type=int,
    help='Number of other connected account, use account-list command'
)
def account_switch(number):
    """This will set your CURRENT_ACCOUNT to selected"""
    check_sk()

    state_key = get_sk()
    state = get_state(state_key)

    if 'ACCOUNTS' not in state:
        echo(
            '''[RED]You didn\'t connected any account yet. Use[RED] '''
            '''[WHITE]account-connect[WHITE] [RED]command firstly.[RED]'''
        )
    elif number < 1 or number > len(state['ACCOUNTS']):
        echo(
            f'''[RED]There is no account #{number}. Use [RED]'''
             '''[WHITE]account-list[WHITE] [RED]command.[RED]'''
        )
    elif number == state['CURRENT_ACCOUNT']:
        echo(
            f'''[YELLOW]You already on this account. See other with[YELLOW] '''
             '''[WHITE]account-list[WHITE] [YELLOW]command.[YELLOW]'''
        )
    else:
        state['CURRENT_ACCOUNT'] = number
        write_state(state, state_key)
        echo(f'[GREEN]You switched to account #{number}[GREEN]')

    tgbox.sync(exit_program())

@cli.command()
@click.option(
    '--box-name', '-b', required=True,
    prompt=True, help='Name of your Box'
)
@click.option(
    '--box-salt', help='BoxSalt as hexadecimal'
)
@click.option(
    '--phrase', '-p',
    help='Passphrase to your Box. Keep it secret'
)
@click.option(
    '--scrypt-salt', 's',
    default=hex(tgbox.defaults.Scrypt.SALT)[2:],
    help='Scrypt salt as hexadecimal'
)
@click.option(
    '--scrypt-n', '-N', 'n', help='Scrypt N',
    default=int(tgbox.defaults.Scrypt.N)
)
@click.option(
    '--scrypt-p', '-P', 'p', help='Scrypt P',
    default=int(tgbox.defaults.Scrypt.P)
)
@click.option(
    '--scrypt-r', '-R', 'r', help='Scrypt R',
    default=int(tgbox.defaults.Scrypt.R)
)
@click.option(
    '--scrypt-dklen', '-L', 'l', help='Scrypt key length',
    default=int(tgbox.defaults.Scrypt.DKLEN)
)
def box_make(box_name, box_salt, phrase, s, n, p, r, l):
    """Create new TGBOX, the Remote and Local"""

    tc = _select_account()

    state_key = get_sk()
    state = get_state(state_key)

    if not phrase and click.confirm('Generate passphrase for you?'):
        phrase = tgbox.keys.Phrase.generate().phrase.decode()
        echo(f'\nYour Phrase is [MAGENTA]{phrase}[MAGENTA]')

        echo(
            '''Please, write it down [WHITE]on paper[WHITE] '''
            '''and press [RED]Enter[RED]'''
            ''', we will [RED]clear[RED] shell for you'''
        )
        input(); clear_console()

    elif not phrase:
        phrase, phrase_repeat = 0, 1
        while phrase != phrase_repeat:
            if phrase != 0: # Init value
                echo('[RED]Phrase mismatch! Try again[RED]\n')

            phrase = click.prompt('Phrase', hide_input=True)
            phrase_repeat = click.prompt('Repeat phrase', hide_input=True)

    echo('[CYAN]Making BaseKey...[CYAN] ', nl=False)

    box_salt = bytes.fromhex(box_salt) if box_salt else None

    basekey = tgbox.keys.make_basekey(
        phrase.encode(),
        salt=bytes.fromhex(s),
        n=n, p=p, r=r, dklen=l
    )
    echo('[GREEN]Successful![GREEN]')

    echo('[CYAN]Making RemoteBox...[CYAN] ', nl=False)
    erb = tgbox.sync(tgbox.api.make_remotebox(
        tc, box_name, box_salt=box_salt)
    )
    echo('[GREEN]Successful![GREEN]')

    echo('[CYAN]Making LocalBox...[CYAN] ', nl=False)
    dlb = tgbox.sync(tgbox.api.make_localbox(erb, basekey))
    echo('[GREEN]Successful![GREEN]')

    echo('[CYAN]Updating local data...[CYAN] ', nl=False)

    if 'TGBOXES' not in state:
        state['TGBOXES'] = [[box_name, basekey.key]]
        state['CURRENT_TGBOX'] = 0
    else:
        state['TGBOXES'].append([box_name, basekey.key])
        state['CURRENT_TGBOX'] = len(state['TGBOXES']) - 1

    write_state(state, state_key)
    echo('[GREEN]Successful![GREEN]')

    tgbox.sync(exit_program(dlb=dlb, drb=erb))

@cli.command()
@click.option(
    '--box-path', '-b', required=True,
    prompt=True, help='Path to the LocalBox database',
    type=click.Path(writable=True, readable=True, path_type=Path)
)
@click.option(
    '--phrase', '-p', required=True,
    prompt=True, hide_input=True,
    help='Passphrase of encrypted Box.'
)
@click.option(
    '--salt', '-s', 's',
    default=hex(tgbox.defaults.Scrypt.SALT)[2:],
    help='Scrypt salt as hexadecimal number'
)
@click.option(
    '--scrypt-n', '-N', 'n', help='Scrypt N',
    default=int(tgbox.defaults.Scrypt.N)
)
@click.option(
    '--scrypt-p', '-P', 'p', help='Scrypt P',
    default=int(tgbox.defaults.Scrypt.P)
)
@click.option(
    '--scrypt-r', '-R', 'r', help='Scrypt R',
    default=int(tgbox.defaults.Scrypt.R)
)
@click.option(
    '--scrypt-dklen', '-L', 'l', help='Scrypt key length',
    default=int(tgbox.defaults.Scrypt.DKLEN)
)
def box_open(box_path, phrase, s, n, p, r, l):
    """Decrypt & connect existing LocalTgbox"""
    check_sk()

    state_key = get_sk()
    state = get_state(state_key)

    echo('[CYAN]Making BaseKey...[CYAN] ', nl=False)

    basekey = tgbox.keys.make_basekey(
        phrase.encode(),
        salt=bytes.fromhex(s),
        n=n, p=p, r=r, dklen=l
    )
    echo('[GREEN]Successful![GREEN]')

    echo('[CYAN]Opening LocalBox...[CYAN] ', nl=False)
    try:
        dlb = tgbox.sync(tgbox.api.get_localbox(basekey, box_path))
    except tgbox.errors.IncorrectKey:
        echo('[RED]Incorrect passphrase![RED]')
        tgbox.sync(exit_program())

    echo('[GREEN]Successful![GREEN]')

    echo('[CYAN]Updating local data...[CYAN] ', nl=False)

    if 'TGBOXES' not in state:
        state['TGBOXES'] = [[box_path, basekey.key]]
        state['CURRENT_TGBOX'] = 0
    else:
        for _, other_basekey in state['TGBOXES']:
            if basekey.key == other_basekey:
                echo('[RED]This Box is already opened[RED]')
                tgbox.sync(exit_program(dlb=dlb))

        state['TGBOXES'].append([box_path, basekey.key])
        state['CURRENT_TGBOX'] = len(state['TGBOXES']) - 1

    write_state(state, state_key)
    echo('[GREEN]Successful![GREEN]')
    tgbox.sync(exit_program(dlb=dlb))

@cli.command()
@click.option(
    '--number', '-n', required=True, type=int,
    help='Number of other connected box, use box-list command'
)
def box_close(number):
    """Will disconnect selected LocalBox"""
    check_sk()

    state_key = get_sk()
    state = get_state(state_key)

    if 'TGBOXES' not in state or not state['TGBOXES']:
        echo('[RED]You don\'t have any connected Box.[RED]')
    elif number < 1 or number > len(state['TGBOXES']):
        echo('[RED]Invalid number, see box-list[RED]')
    else:
        state['TGBOXES'].pop(number-1)
        if not state['TGBOXES']:
            state.pop('TGBOXES')
            state.pop('CURRENT_TGBOX')
            echo('[GREEN]Disconnected. No more Boxes.[GREEN]')
        else:
            state['CURRENT_TGBOX'] = 0
            echo('[GREEN]Disconnected & switched to the Box #1[GREEN]')
            tgbox.sync(exit_program())

        write_state(state, state_key)

@cli.command()
@click.option(
    '--number', '-n', required=True, type=int,
    help='Number of other connected box, use box-list command'
)
def box_switch(number):
    """This will set your CURRENT_TGBOX to selected"""
    check_sk()

    state_key = get_sk()
    state = get_state(state_key)
    number -= 1

    if 'TGBOXES' not in state:
        echo(
            '''[RED]You didn\'t connected box yet. Use[RED] '''
            '''[WHITE]box-open[WHITE] [RED]command.[RED]'''
        )
    elif number < 0 or number > len(state['TGBOXES'])-1:
        echo(
            f'''[RED]There is no box #{number+1}. Use[RED] '''
             '''[WHITE]box-list[WHITE] [RED]command.[RED]'''
        )
    elif number == state['CURRENT_TGBOX']:
        echo(
            '''[YELLOW]You already use this box. See other with[YELLOW] '''
            '''[WHITE]box-list[WHITE] [YELLOW]command.[YELLOW]'''
        )
    else:
        state['CURRENT_TGBOX'] = number
        write_state(state, state_key)
        echo(f'[GREEN]You switched to box #{number+1}[GREEN]')

    tgbox.sync(exit_program())

@cli.command()
def box_list():
    """List all connected boxes"""
    check_sk()

    state_key = get_sk()
    state = get_state(state_key)

    if 'CURRENT_TGBOX' in state:
        echo(
            ''''\n[WHITE]You\'re using Box[WHITE] '''
           f'''[RED]#{str(state['CURRENT_TGBOX']+1)}[RED]\n'''
        )
    else:
        echo('[YELLOW]You don\'t have any connected Box.[YELLOW]')
        tgbox.sync(exit_program())

    lost_boxes, count = [], 0

    for box_path, basekey in state['TGBOXES']:
        try:
            dlb = tgbox.sync(tgbox.api.get_localbox(
                tgbox.keys.BaseKey(basekey), box_path)
            )
            name = Path(box_path).name
            salt = urlsafe_b64encode(dlb.box_salt).decode()

            echo(
                f'''[WHITE]{count+1})[WHITE] [BLUE]{name}[BLUE]'''
                f'''@[BRIGHT_BLACK]{salt}[BRIGHT_BLACK]'''
            )
            tgbox.sync(dlb.done())
        except FileNotFoundError:
            echo(f'#[WHITE]{count+1}[WHITE] [RED]Moved, so removed.[RED]')
            lost_boxes.append([box_path, basekey])

        count += 1

    for lbox in lost_boxes:
        state['TGBOXES'].remove(lbox)

    if lost_boxes:
        if not state['TGBOXES']:
            state.pop('TGBOXES')
            state.pop('CURRENT_TGBOX')
            echo('No more Boxes, use [WHITE]box-open[WHITE].')
        else:
            state['CURRENT_TGBOX'] = -1
            echo(
                '''Switched to the last Box. Set other '''
                '''with [WHITE]box-switch[WHITE].'''
            )
    write_state(state, state_key)
    tgbox.sync(exit_program())

@cli.command()
@click.option(
    '--prefix', '-p', default=tgbox.defaults.REMOTEBOX_PREFIX,
    help='Telegram channels with this prefix will be searched'
)
def box_list_remote(prefix):
    """List all RemoteBoxes on account"""

    tc, count = _select_account(), 0

    echo('[YELLOW]Searching...[YELLOW]')

    for dialogue in sync_async_gen(tc.iter_dialogs()):
        if prefix in dialogue.title and dialogue.is_channel:
            erb = tgbox.api.EncryptedRemoteBox(dialogue, tc)

            erb_name = tgbox.sync(erb.get_box_name())
            erb_salt = tgbox.sync(erb.get_box_salt())
            erb_salt = urlsafe_b64encode(erb_salt).decode()

            echo(
                f'''[WHITE]{count+1}[WHITE]) [BLUE]{erb_name}[BLUE]'''
                f'''@[BRIGHT_BLACK]{erb_salt}[BRIGHT_BLACK]'''
            )
            count += 1

    echo('[YELLOW]Done.[YELLOW]')
    tgbox.sync(exit_program())

@cli.command()
@click.option(
    '--start-from-id','-s', default=0,
    help='Will check files that > specified ID'
)
def box_sync(start_from_id):
    """Will synchronize your current LocalBox with RemoteBox

    After this operation, all info about your LocalFiles that are
    not in RemoteBox will be deleted from LocalBox. Files that
    not in LocalBox but in RemoteBox will be imported.
    """
    dlb, drb = _select_box()
    manager = get_enlighten_manager()

    tgbox.sync(dlb.sync(drb, start_from_id,
        Progress(manager, 'Synchronizing...').update_2)
    )
    manager.stop()

    echo('[GREEN]Syncing complete.[GREEN]')
    tgbox.sync(exit_program(dlb=dlb, drb=drb))

@cli.command()
@click.option(
    '--number','-n', required=True, type=int,
    help='Number of connected account. We will take session from it.'
)
def box_replace_account(number):
    """Will replace Telegram account of your current Box

    This can be useful if you disconnected your TGBOX in
    Telegram settings (Privacy & Security > Devices) or
    your local TGBOX was too long offline.
    """
    state_key = get_sk()
    state = get_state(state_key)

    dlb, _ = _select_box(ignore_remote=True)

    if number < 1 or number > len(state['ACCOUNTS']):
        echo(
            '''[RED]Invalid account number! See[RED] '''
            '''[WHITE]account-list[WHITE] [RED]command.[RED]'''
        )
        tgbox.sync(exit_program(dlb=dlb))

    session = state['ACCOUNTS'][number-1]

    tc = tgbox.api.TelegramClient(
        session=session,
        api_id=API_ID,
        api_hash=API_HASH
    )
    tgbox.sync(tc.connect())

    basekey = tgbox.keys.BaseKey(
        state['TGBOXES'][state['CURRENT_TGBOX']][1]
    )
    tgbox.sync(dlb.replace_session(basekey, tc))
    echo('[GREEN]Session replaced successfully[GREEN]')

    tgbox.sync(exit_program(dlb=dlb))

@cli.command()
@click.option(
    '--number', '-n', required=True, type=int,
    help='Number of RemoteBox, use box-list-remote command'
)
@click.option(
    '--phrase', '-p', required=True, hide_input=True,
    help='To request Box you need to specify phrase to it',
    prompt='Phrase to your future cloned Box'
)
@click.option(
    '--salt', '-s', 's',
    default=hex(tgbox.defaults.Scrypt.SALT)[2:],
    help='Scrypt salt as hexadecimal number'
)
@click.option(
    '--scrypt-n', '-N', 'n', help='Scrypt N',
    default=int(tgbox.defaults.Scrypt.N)
)
@click.option(
    '--scrypt-p', '-P', 'p', help='Scrypt P',
    default=int(tgbox.defaults.Scrypt.P)
)
@click.option(
    '--scrypt-r', '-R', 'r', help='Scrypt R',
    default=int(tgbox.defaults.Scrypt.R)
)
@click.option(
    '--scrypt-dklen', '-L', 'l', help='Scrypt key length',
    default=int(tgbox.defaults.Scrypt.DKLEN)
)
@click.option(
    '--prefix', default=tgbox.defaults.REMOTEBOX_PREFIX,
    help='Telegram channels with this prefix will be searched'
)
def box_request(number, phrase, s, n, p, r, l, prefix):
    """Command to receive RequestKey for other Box"""
    erb = _select_remotebox(number, prefix)

    basekey = tgbox.keys.make_basekey(
        phrase.encode(),
        salt=bytes.fromhex(s),
        n=n, p=p, r=r, dklen=l
    )
    reqkey = tgbox.sync(erb.get_requestkey(basekey))
    echo(
        '''\nSend this Key to the Box owner:\n'''
       f'''    [WHITE]{reqkey.encode()}[WHITE]\n'''
    )
    tgbox.sync(exit_program(drb=erb))

@cli.command()
@click.option(
    '--requestkey', '-r',
    help='Requester\'s RequestKey, by box-request command'
)
def box_share(requestkey):
    """Command to make ShareKey & to share Box"""
    dlb, _ = _select_box(ignore_remote=True)

    requestkey = requestkey if not requestkey\
        else tgbox.keys.Key.decode(requestkey)

    sharekey = dlb.get_sharekey(requestkey)

    if not requestkey:
        echo(
            '''\n[RED]You didn\'t specified requestkey.\n   You '''
            '''will receive decryption key IN PLAIN\n[RED]'''
        )
        if not click.confirm('Are you TOTALLY sure?'):
            tgbox.sync(exit_program(dlb=dlb))

    echo(
        '''\nSend this Key to the Box requester:\n'''
       f'''    [WHITE]{sharekey.encode()}[WHITE]\n'''
    )
    tgbox.sync(exit_program(dlb=dlb))

@cli.command()
@click.option(
    '--box-path', '-b', help='Path to which we will clone',
    type=click.Path(writable=True, readable=True, path_type=Path)
)
@click.option(
    '--box-filename', '-f',
    help='Filename of cloned DecryptedLocalBox',
)
@click.option(
    '--box-number', '-n', required=True, type=int,
    prompt=True, help='Number of Box you want to clone',
)
@click.option(
    '--prefix', default=tgbox.defaults.REMOTEBOX_PREFIX,
    help='Telegram channels with this prefix will be searched'
)
@click.option(
    '--key', '-k', help='ShareKey/ImportKey received from Box owner.'
)
@click.option(
    '--phrase', '-p', prompt='Phrase to your cloned Box',
    help='To clone Box you need to specify phrase to it',
    hide_input=True, required=True
)
@click.option(
    '--salt', '-s', 's',
    default=hex(tgbox.defaults.Scrypt.SALT)[2:],
    help='Scrypt salt as hexadecimal number'
)
@click.option(
    '--scrypt-n', '-N', 'n', help='Scrypt N',
    default=int(tgbox.defaults.Scrypt.N)
)
@click.option(
    '--scrypt-p', '-P', 'p', help='Scrypt P',
    default=int(tgbox.defaults.Scrypt.P)
)
@click.option(
    '--scrypt-r', '-R', 'r', help='Scrypt R',
    default=int(tgbox.defaults.Scrypt.R)
)
@click.option(
    '--scrypt-dklen', '-L', 'l', help='Scrypt key length',
    default=int(tgbox.defaults.Scrypt.DKLEN)
)
def box_clone(
        box_path, box_filename,
        box_number, prefix, key,
        phrase, s, n, p, r, l):
    """
    Will clone RemoteBox to LocalBox by your passphrase
    """
    state_key = get_sk()
    state = get_state(state_key)
    erb = _select_remotebox(box_number, prefix)

    try:
        key = tgbox.keys.Key.decode(key)
    except tgbox.errors.IncorrectKey:
        pass

    echo('\n[CYAN]Making BaseKey...[CYAN] ', nl=False)

    basekey = tgbox.keys.make_basekey(
        phrase.encode(),
        salt=bytes.fromhex(s),
        n=n, p=p, r=r, dklen=l
    )
    echo('[GREEN]Successful![GREEN]')

    if key is None:
        key = basekey
    else:
        key = tgbox.keys.make_importkey(
            key=basekey, sharekey=key,
            box_salt=tgbox.sync(erb.get_box_salt())
        )
    drb = tgbox.sync(erb.decrypt(key=key))

    if box_path is None:
        if box_filename:
            box_path = box_filename
        else:
            box_path = tgbox.sync(drb.get_box_name())
    else:
        box_path += tgbox.sync(drb.get_box_name())\
            if not box_filename else box_filename

    manager = get_enlighten_manager()

    tgbox.sync(drb.clone(
        basekey=basekey, box_path=box_path,
        progress_callback=Progress(manager, 'Cloning...').update_2
    ))
    manager.stop()

    echo('\n[CYAN]Updating local data...[CYAN] ', nl=False)

    if 'TGBOXES' not in state:
        state['TGBOXES'] = [[box_path, basekey.key]]
        state['CURRENT_TGBOX'] = 0
    else:
        for _, other_basekey in state['TGBOXES']:
            if basekey.key == other_basekey:
                echo('[RED]This Box is already opened[RED]')
                tgbox.sync(exit_program(drb=drb))

        state['TGBOXES'].append([box_path, basekey.key])
        state['CURRENT_TGBOX'] = len(state['TGBOXES']) - 1

    write_state(state, state_key)
    echo('[GREEN]Successful![GREEN]')
    tgbox.sync(exit_program(drb=drb))

@cli.command()
@click.argument('defaults',nargs=-1)
def box_default(defaults):
    """Change the TGBOX default values to your own

    \b
    I.e:\b
        # Change METADATA_MAX to the max allowed size
        tgbox-cli box-default METADATA_MAX=1677721
        \b
        # Change download path from DownloadsTGBOX to Downloads
        tgbox-cli box-default DOWNLOAD_PATH=Downloads
    """
    dlb, _ = _select_box(ignore_remote=True)

    for default in defaults:
        try:
            key, value = default.split('=',1)
            tgbox.sync(dlb.defaults.change(key, value))
            echo(f'[GREEN]Successfuly changed {key} to {value}[GREEN]')
        except AttributeError as e:
            echo(f'[RED]Default {key} doesn\'t exist, skipping[RED]')

    tgbox.sync(exit_program(dlb=dlb))

@cli.command()
@click.option(
    '--path', '-p', required=True, prompt=True,
    help='Will upload specified path. If directory, upload all files in it',
    type=click.Path(readable=True, dir_okay=True, path_type=Path)
)
@click.option(
    '--file-path', '-f', type=Path,
    help='File path. Will be system\'s if not specified'
)
@click.option(
    '--cattrs', '-c', help='File\'s CustomAttributes. Format: "key:value key:value"'
)
@click.option(
    '--thumb/--no-thumb', default=True,
    help='Add thumbnail or not, boolean'
)
@click.option(
    '--max-workers', default=10, type=click.IntRange(1,50),
    help='Max amount of files uploaded at the same time, default=10',
)
@click.option(
    '--max-bytes', default=1000000000,
    type=click.IntRange(1000000, 10000000000),
    help='Max amount of bytes uploaded at the same time, default=1000000000',
)
def file_upload(path, file_path, cattrs, thumb, max_workers, max_bytes):
    """Will upload specified path to the Box"""
    dlb, drb = _select_box()

    current_workers = max_workers
    current_bytes = max_bytes

    def _upload(to_upload: list):
        try:
            tgbox.sync(gather(*to_upload))
            to_upload.clear()
        except tgbox.errors.NotEnoughRights as e:
            echo(f'\n[RED]{e}[RED]')
            manager.stop()
            tgbox.sync(exit_program(dlb=dlb, drb=drb))

    if path.is_dir():
        iter_over = path.rglob('*')
    else:
        iter_over = (path,)

    manager, to_upload = get_enlighten_manager(), []
    for current_path in iter_over:

        if current_path.is_dir():
            continue

        if not file_path:
            remote_path = current_path.absolute()
        else:
            remote_path = Path(file_path) / current_path.name

        if cattrs:
            try:
                parsed_cattrs = [
                    i.strip().split(':')
                    for i in cattrs.split() if i
                ]
                parsed_cattrs = {
                    k.strip():v.strip().encode()
                    for k,v in parsed_cattrs
                }
            except ValueError as e:
                raise ValueError('Invalid cattrs!', e) from None
        else:
            parsed_cattrs = None
        try:
            pf = tgbox.sync(dlb.prepare_file(
                file = open(current_path,'rb'),
                file_path = remote_path,
                cattrs = parsed_cattrs,
                make_preview = thumb
            ))
        except tgbox.errors.InvalidFile as e:
            echo(f'[YELLOW]{current_path} is empty. Skipping.[YELLOW]')
            continue
        except tgbox.errors.FingerprintExists as e:
            echo(f'[YELLOW]{current_path} already uploaded. Skipping.[YELLOW]')
            continue

        current_bytes -= pf.filesize
        current_workers -= 1

        if not all((current_workers, current_bytes)):
            _upload(to_upload)

            current_workers = max_workers - 1
            current_bytes = max_bytes - pf.filesize

        to_upload.append(drb.push_file(pf, Progress(
            manager, current_path.name).update))

    if to_upload: # If any files left
        _upload(to_upload)

    manager.stop()
    tgbox.sync(exit_program(dlb=dlb, drb=drb))

@cli.command()
@click.argument('filters',nargs=-1)
@click.option(
    '--force-remote','-r', is_flag=True,
    help='If specified, will fetch files from RemoteBox'
)
@click.option(
    '--non-interactive', is_flag=True,
    help='If specified, will echo to shell instead of pager'
)
def file_search(filters, force_remote, non_interactive):
    """Will list files by filters

    \b
    Available filters:\b
        id integer: File’s ID
        mime str: File mime type
        \b
        cattrs: File CAttrs
                -----------
                Can be used hexed PackedAttributes
                or special CLI format alternatively:
                cattrs="comment:test type:message"
        \b
        file_path str: File path
        file_name str: File name
        file_salt str: File salt
        \b
        min_id integer: File ID should be > min_id
        max_id integer: File ID should be < max_id
        \b
        min_size integer: File Size should be > min_size
        max_size integer: File Size should be < max_size
        \b
        min_time integer/float: Upload Time should be > min_time
        max_time integer/float: Upload Time should be < max_time
        \b
        imported bool: Yield only imported files
        re       bool: re_search for every bytes filter
    \b
    See tgbox.readthedocs.io/en/indev/
        tgbox.html#tgbox.tools.SearchFilter
    \b
    You can also use special flags to specify
    that filters is for include or exclude search.
    \b
    Example:\b
        # Include is used by default
        tgbox-cli file-search min_id=3 max_id=100
        \b
        # Include flag (will ignore unmatched)
        tgbox-cli file-search +i file_name=.png
        \b
        # Exclude flag (will ignore matched)
        tgbox-cli file-search +e file_name=.png
        \b
        You can use both, the ++include and
        ++exclude (+i, +e) in one command.
    """
    if force_remote:
        dlb, drb = _select_box()
    else:
        dlb, drb = _select_box(ignore_remote=True)

    def bfi_gen(search_file_gen):
        for bfi in sync_async_gen(search_file_gen):
            yield _format_dxbf(bfi)
    try:
        sf = filters_to_searchfilter(filters)
    except ZeroDivisionError:#IndexError: # Incorrect filters format
        echo('[RED]Incorrect filters! Make sure to use format filter=value[RED]')
        tgbox.sync(exit_program(dlb=dlb, drb=drb))
    except KeyError as e: # Unknown filters
        echo(f'[RED]Filter "{e.args[0]}" doesn\'t exists[RED]')
        tgbox.sync(exit_program(dlb=dlb, drb=drb))

    box = drb if force_remote else dlb

    if non_interactive:
        for dxbfs in bfi_gen(box.search_file(sf, cache_preview=False)):
            echo(dxbfs, nl=False)
        echo('')
    else:
        click.echo_via_pager(bfi_gen(
            box.search_file(sf, cache_preview=False)
        ))
    tgbox.sync(exit_program(dlb=dlb, drb=drb))

@cli.command()
@click.argument('filters', nargs=-1)
@click.option(
    '--preview', '-p', is_flag=True,
    help='If specified, will download ONLY thumbnails'
)
@click.option(
    '--show', '-s', is_flag=True,
    help='If specified, will open file on downloading'
)
@click.option(
    '--locate', '-l', is_flag=True,
    help='If specified, will open file path in file manager'
)
@click.option(
    '--hide-name', is_flag=True,
    help='If specified, will hide file name'
)
@click.option(
    '--hide-folder', is_flag=True,
    help='If specified, will hide folder'
)
@click.option(
    '--out','-o',
    help='Download path. ./BoxDownloads by default',
    type=click.Path(writable=True, path_type=Path)
)
@click.option(
    '--force-remote','-r', is_flag=True,
    help='If specified, will fetch file data from RemoteBox'
)
@click.option(
    '--max-workers', default=10, type=click.IntRange(1,50),
    help='Max amount of files downloaded at the same time, default=10',
)
@click.option(
    '--max-bytes', default=1000000000,
    type=click.IntRange(1000000, 10000000000),
    help='Max amount of bytes downloaded at the same time, default=1000000000',
)
def file_download(
        filters, preview, show, locate,
        hide_name, hide_folder, out,
        force_remote, max_workers, max_bytes):
    """Will download files by filters

    \b
    Available filters:\b
        id integer: File’s ID
        mime str: File mime type
        \b
        cattrs: File CAttrs
                -----------
                Can be used hexed PackedAttributes
                or special CLI format alternatively:
                cattrs="comment:test type:message"
        \b
        file_path str: File path
        file_name str: File name
        file_salt str: File salt
        \b
        min_id integer: File ID should be > min_id
        max_id integer: File ID should be < max_id
        \b
        min_size integer: File Size should be > min_size
        max_size integer: File Size should be < max_size
        \b
        min_time integer/float: Upload Time should be > min_time
        max_time integer/float: Upload Time should be < max_time
        \b
        imported bool: Yield only imported files
        re       bool: re_search for every bytes filter
    \b
    See tgbox.readthedocs.io/en/indev/
        tgbox.html#tgbox.tools.SearchFilter
    \b
    You can also use special flags to specify
    that filters is for include or exclude search.
    \b
    Example:\b
        # Include is used by default
        tgbox-cli file-download min_id=3 max_id=100
        \b
        # Include flag (will ignore unmatched)
        tgbox-cli file-download +i file_name=.png
        \b
        # Exclude flag (will ignore matched)
        tgbox-cli file-download +e file_name=.png
        \b
        You can use both, the ++include and
        ++exclude (+i, +e) in one command.
    """
    if preview and not force_remote:
        dlb, drb = _select_box(ignore_remote=True)
    else:
        dlb, drb = _select_box()
    try:
        sf = filters_to_searchfilter(filters)
    except ZeroDivisionError:#IndexError: # Incorrect filters format
        echo('[RED]Incorrect filters! Make sure to use format filter=value[RED]')
        tgbox.sync(exit_program(dlb=dlb, drb=drb))
    except KeyError as e: # Unknown filters
        echo(f'[RED]Filter "{e.args[0]}" doesn\'t exists[RED]')
        tgbox.sync(exit_program(dlb=dlb, drb=drb))

    manager, to_upload = get_enlighten_manager(), []

    current_workers = max_workers
    current_bytes = max_bytes

    to_download = dlb.search_file(sf)
    while True:
        try:
            to_gather_files = []
            while all((current_workers, current_bytes)):
                dlbfi = tgbox.sync(tgbox.tools.anext(to_download))
                preview_bytes = None

                if preview and not force_remote:
                    tgbox.sync(dlbfi.directory.lload(full=True))

                    file_name = dlbfi.file_name
                    folder = str(dlbfi.directory)
                    preview_bytes = dlbfi.preview

                elif preview and force_remote:
                    drbfi = tgbox.sync(drb.get_file(dlbfi.id))

                    file_name = drbfi.file_name
                    folder = str(drbfi.file_path)
                    preview_bytes = drbfi.preview

                if preview_bytes is not None:
                    if preview_bytes == b'':
                        echo(
                            f'''[YELLOW]{file_name} doesn\'t have preview. Try '''
                             '''-r flag. Skipping.[YELLOW]'''
                        )
                        continue

                    if not out:
                        outpath = tgbox.defaults.DOWNLOAD_PATH\
                            / 'Previews' / folder.lstrip('/')
                        outpath.mkdir(parents=True, exist_ok=True)
                    else:
                        outpath = out

                    file_path = outpath / (file_name+'.jpg')

                    with open(file_path, 'wb') as f:
                        f.write(preview_bytes)

                    if show or locate:
                        click.launch(str(file_path), locate)

                    echo(
                        f'''[WHITE]{file_name}[WHITE] preview downloaded '''
                        f'''to [WHITE]{str(outpath)}[WHITE]''')
                else:
                    drbfi = tgbox.sync(drb.get_file(dlbfi.id))

                    if not drbfi:
                        echo(
                            f'''[YELLOW]There is no file with ID={dlbfi.id} in '''
                             '''RemoteBox. Skipping.[YELLOW]''')
                    else:
                        current_workers -= 1
                        current_bytes -= drbfi.file_size

                        if not out:
                            tgbox.sync(dlbfi.directory.lload(full=True))

                            outpath = tgbox.defaults.DOWNLOAD_PATH / 'Files' / '@'
                            outpath = outpath / str(dlbfi.directory).strip('/')
                            outpath.mkdir(parents=True, exist_ok=True)

                            outpath = open(outpath / dlbfi.file_name, 'wb')
                        else:
                            outpath = out

                        p_file_name = '<Filename hidden>' if hide_name\
                            else drbfi.file_name

                        download_coroutine = drbfi.download(
                            outfile = outpath,
                            progress_callback = Progress(
                                manager, p_file_name).update,
                            hide_folder = hide_folder,
                            hide_name = hide_name
                        )
                        to_gather_files.append(download_coroutine)

                        if show or locate:
                            def _launch(path: str, locate: bool, size: int) -> None:
                                while (Path(path).stat().st_size+1) / size * 100 < 5:
                                    sleep(1)
                                click.launch(path, locate=locate)

                            loop = get_event_loop()

                            to_gather_files.append(loop.run_in_executor(
                                None, lambda: _launch(outpath.name, locate, dlbfi.size))
                            )
            if to_gather_files:
                tgbox.sync(gather(*to_gather_files))

            current_workers = max_workers
            current_bytes = max_bytes

        except StopAsyncIteration:
            break

    if to_gather_files: # If any files left
        tgbox.sync(gather(*to_gather_files))

    manager.stop()
    tgbox.sync(exit_program(dlb=dlb, drb=drb))

@cli.command()
def file_list_non_imported():
    """Will list files not imported to your
    DecryptedLocalBox from other RemoteBox

    Will also show a RequestKey. Send it to the
    file owner. He will use a file-share command
    and will send you a ShareKey. You can use
    it with file-import to decrypt and save
    forwarded RemoteBoxFile to your LocalBox.
    """
    dlb, drb = _select_box()

    iter_over = drb.files(
        return_imported_as_erbf=True,
        min_id=tgbox.sync(dlb.get_last_file_id())
    )
    for xrbf in sync_async_gen(iter_over):
        if isinstance(xrbf, tgbox.api.EncryptedRemoteBoxFile):
            time = datetime.fromtimestamp(xrbf.upload_time)
            time = f"[CYAN]{time.strftime('%d/%m/%y, %H:%M:%S')}[CYAN]"

            salt = urlsafe_b64encode(xrbf.file_salt).decode()
            idsalt = f'[[BRIGHT_RED]{str(xrbf.id)}[BRIGHT_RED]:'
            idsalt += f'[BRIGHT_BLACK]{salt[:12]}[BRIGHT_BLACK]]'

            size = f'[GREEN]{format_bytes(xrbf.file_size)}[GREEN]'
            name = '[RED][N/A: No FileKey available][RED]'

            req_key = xrbf.get_requestkey(dlb._mainkey).encode()
            req_key = f'[WHITE]{req_key}[WHITE]'

            formatted = (
               f"""\nFile: {idsalt} {name}\n"""
               f"""Size, Time: {size}({xrbf.file_size}), {time}\n"""
               f"""RequestKey: {req_key}"""
            )
            echo(formatted)
    echo('')
    tgbox.sync(exit_program(dlb=dlb, drb=drb))

@cli.command()
@click.option(
    '--requestkey', '-r',
    help='Requester\'s RequestKey'
)
@click.option(
    '--id', required=True, type=int,
    help='ID of file to share'
)
def file_share(requestkey, id):
    """Use this command to get a ShareKey to your file"""

    dlb, _ = _select_box(ignore_remote=True)
    dlbf = tgbox.sync(dlb.get_file(id=id))

    if not dlbf:
        echo(f'[RED]There is no file in LocalBox by ID {id}[RED]')
        tgbox.sync(exit_program(dlb=dlb))

    requestkey = requestkey if not requestkey\
        else tgbox.keys.Key.decode(requestkey)

    sharekey = dlbf.get_sharekey(requestkey)

    if not requestkey:
        echo(
            '''\n[RED]You didn\'t specified requestkey.\n   You '''
            '''will receive decryption key IN PLAIN[RED]\n'''
        )
        if not click.confirm('Are you TOTALLY sure?'):
            tgbox.sync(exit_program(dlb=dlb))
    echo(
        '''\nSend this Key to the Box requester:\n'''
       f'''    [WHITE]{sharekey.encode()}[WHITE]\n'''
    )
    tgbox.sync(exit_program(dlb=dlb))

@cli.command()
@click.option(
    '--key', '-k', required=True,
    help='File\'s ShareKey/ImportKey/FileKey'
)
@click.option(
    '--id', required=True, type=int,
    help='ID of file to import'
)
@click.option(
    '--file-path', '-f', type=Path,
    help='Imported file\'s path.'
)
def file_import(key, id, file_path):
    """Will import RemoteBoxFile to your LocalBox"""
    dlb, drb = _select_box()
    erbf = tgbox.sync(drb.get_file(
        id, return_imported_as_erbf=True))

    if not erbf:
        echo(f'[RED]There is no file in RemoteBox by ID {id}[RED]')
        tgbox.sync(exit_program(dlb=dlb, drb=drb))
    try:
        key = tgbox.keys.Key.decode(key)
    except tgbox.errors.IncorrectKey:
        echo(f'[RED]Specified Key is invalid[RED]')
    else:
        if isinstance(key, tgbox.keys.ShareKey):
            key = tgbox.keys.make_importkey(
                key=dlb._mainkey, sharekey=key,
                box_salt=erbf.file_salt
            )
        drbf = tgbox.sync(erbf.decrypt(key))
        dlbf = tgbox.sync(dlb.import_file(drbf, file_path))

        echo(_format_dxbf(drbf))

    tgbox.sync(exit_program(dlb=dlb, drb=drb))

@cli.command()
@click.option(
    '--remote','-r', is_flag=True,
    help='If specified, will return ID of last file on RemoteBox'
)
def file_last_id(remote):
    """Will return ID of last uploaded to Box file"""
    dlb, drb = _select_box(ignore_remote=False if remote else True)
    lfid = tgbox.sync((drb if remote else dlb).get_last_file_id())

    sbox = 'Remote' if remote else 'Local'
    echo(f'ID of last uploaded to {sbox}Box file is [GREEN]{lfid}[GREEN]')
    tgbox.sync(exit_program(drb=drb, dlb=dlb))


@cli.command()
@click.argument('filters', nargs=-1)
@click.option(
    '--local-only','-l', is_flag=True,
    help='If specified, will remove file ONLY from LocalBox'
)
@click.option(
    '--ask-before-remove','-a', is_flag=True,
    help='If specified, will ask "Are you sure?" for each file'
)
def file_remove(filters, local_only, ask_before_remove):
    """Will remove files by filters

    \b
    Available filters:\b
        id integer: File’s ID
        mime str: File mime type
        \b
        cattrs: File CAttrs
                -----------
                Can be used hexed PackedAttributes
                or special CLI format alternatively:
                cattrs="comment:test type:message"
        \b
        file_path str: File path
        file_name str: File name
        file_salt str: File salt
        \b
        min_id integer: File ID should be > min_id
        max_id integer: File ID should be < max_id
        \b
        min_size integer: File Size should be > min_size
        max_size integer: File Size should be < max_size
        \b
        min_time integer/float: Upload Time should be > min_time
        max_time integer/float: Upload Time should be < max_time
        \b
        imported bool: Yield only imported files
        re       bool: re_search for every bytes filter
    \b
    See tgbox.readthedocs.io/en/indev/
        tgbox.html#tgbox.tools.SearchFilter
    \b
    You can also use special flags to specify
    that filters is for include or exclude search.
    \b
    Example:\b
        # Include is used by default
        tgbox-cli file-remove min_id=3 max_id=100
        \b
        # Include flag (will ignore unmatched)
        tgbox-cli file-remove +i file_name=.png
        \b
        # Exclude flag (will ignore matched)
        tgbox-cli file-remove +e file_name=.png
        \b
        You can use both, the ++include and
        ++exclude (+i, +e) in one command.
    """
    dlb, drb = _select_box()
    try:
        sf = filters_to_searchfilter(filters)
    except ZeroDivisionError:#IndexError: # Incorrect filters format
        echo('[RED]Incorrect filters! Make sure to use format filter=value[RED]')
        tgbox.sync(exit_program(dlb=dlb, drb=drb))
    except KeyError as e: # Unknown filters
        echo(f'[RED]Filter "{e.args[0]}" doesn\'t exists[RED]')
        tgbox.sync(exit_program(dlb=dlb, drb=drb))

    if not filters:
        echo(
            '''\n[RED]You didn\'t specified any search filter.\n   This '''
            '''will [WHITE]REMOVE ALL FILES[WHITE] in your Box[RED]\n'''
        )
        if not click.confirm('Are you TOTALLY sure?'):
            tgbox.sync(exit_program(dlb=dlb, drb=drb))

    to_remove = dlb.search_file(sf, cache_preview=False)
    for dlbf in sync_async_gen(to_remove):
        tgbox.sync(dlbf.directory.lload(full=True))

        file_path = str(Path(str(dlbf.directory)) / dlbf.file_name)
        echo(f'@ [RED]Removing[RED] [WHITE]Box[WHITE]({file_path})')

        if ask_before_remove:
            while True:
                echo('')
                choice = click.prompt(
                    'Are you TOTALLY sure? ([y]es | [n]o | [i]nfo | [e]xit)'
                )
                if choice.lower() in ('yes','y'):
                    tgbox.sync(dlbf.delete())
                    if not local_only:
                        drbf = tgbox.sync(drb.get_file(dlbf.id))
                        tgbox.sync(drbf.delete())
                    echo('')
                    break
                elif choice.lower() in ('no','n'):
                    echo('')
                    break
                elif choice.lower() in ('info','i'):
                    echo(_format_dxbf(dlbf).rstrip())
                elif choice.lower() in ('exit','e'):
                    tgbox.sync(exit_program(dlb=dlb, drb=drb))
                else:
                    echo('[RED]Invalid choice, try again[RED]')
        else:
            tgbox.sync(dlbf.delete())
            if not local_only:
                drbf = tgbox.sync(drb.get_file(dlbf.id))
                tgbox.sync(drbf.delete())

    tgbox.sync(exit_program(dlb=dlb, drb=drb))

@cli.command()
def dir_list():
    """List all directories in LocalBox"""

    dlb, _ = _select_box(ignore_remote=True)
    dirs = dlb.contents(ignore_files=True)

    for dir in sync_async_gen(dirs):
        tgbox.sync(dir.lload(full=True))
        echo(str(dir))

    tgbox.sync(exit_program(dlb=dlb))

@cli.command()
def cli_init():
    """Get commands for initializing TGBOX-CLI"""
    if get_sk():
        echo('[WHITE]CLI is already initialized.[WHITE]')
    else:
        state_key = urlsafe_b64encode(
            tgbox.crypto.get_rnd_bytes(32)
        )
        if platform in ('win32', 'cygwin', 'cli'):
            commands = 'echo off && (for /f %i in (\'tgbox-cli sk-gen\') '\
                'do set "TGBOX_SK=%i") && echo on'
        else:
            commands = 'export TGBOX_SK="$(tgbox-cli sk-gen)"'

        echo(
            '''\n[YELLOW]Welcome to the TGBOX-CLI![YELLOW]\n\n'''
            '''Copy & Paste below commands to your shell:\n\n'''
           f'''[WHITE]{commands}[WHITE]\n'''
        )

@cli.command()
def cli_info():
    """Get base information about TGBOX-CLI"""

    ver = __version__.split('_')
    try:
        sp_result = subprocess_run(
            args=[tgbox.defaults.FFMPEG, '-version'],
            stdout=PIPE, stderr=None
        )
        ffmpeg_version = f"[GREEN]{sp_result.stdout.split(b' ',3)[2].decode()}[GREEN]"
    except:
        ffmpeg_version = '[RED]NO[RED]'

    if tgbox.crypto.FAST_ENCRYPTION:
        fast_encryption = '[GREEN]YES[GREEN]'
    else:
        fast_encryption = '[RED]NO[RED]'

    if tgbox.crypto.FAST_TELETHON:
        fast_telethon = '[GREEN]YES[GREEN]'
    else:
        fast_telethon = '[RED]NO[RED]'

    echo(
        '''\n# Copyright [WHITE](c) Non [github.com/NotStatilko][WHITE], the MIT License\n'''
        '''# Author Email: [WHITE]thenonproton@protonmail.com[WHITE]\n\n'''
        f'''TGBOX-CLI Version: [YELLOW]{ver[0]}[YELLOW]\n'''
        f'''TGBOX Version: [MAGENTA]{ver[1]}[MAGENTA]\n\n'''
        f'''FFMPEG: {ffmpeg_version}\n'''
        f'''FAST_ENCRYPTION: {fast_encryption}\n'''
        f'''FAST_TELETHON: {fast_telethon}\n'''
    )

@cli.command(hidden=True)
@click.option(
    '--size', '-s', default=32,
    help='SessionKey bytesize'
)
def sk_gen(size: int):
    """Generate random urlsafe b64encoded SessionKey"""
    echo(urlsafe_b64encode(tgbox.crypto.get_rnd_bytes(size)).decode())

if __name__ == '__main__':
    safe_cli()
