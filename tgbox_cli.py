import click
import tgbox

from pathlib import Path
from copy import deepcopy
from hashlib import sha256
from asyncio import gather

from ast import literal_eval
from pickle import loads, dumps
from sys import platform, stdout
from base64 import urlsafe_b64encode

from traceback import format_exception
from typing import Union, AsyncGenerator
from datetime import datetime, timedelta

from subprocess import run as subprocess_run, PIPE
from os import getenv, _exit, system as os_system

from tools import (
    Progress, sync_async_gen, exit_program,
    filters_to_searchfilter, clear_console,
    format_bytes, splitpath
)
from enlighten import get_manager


__version__ = '1.0_' + tgbox.defaults.VERSION
tgbox.defaults.VERSION = __version__

# Please DO NOT use this parameters in your projects.
# You can get your own at my.telegram.org. Thanks.
API_ID, API_HASH = 2210681, '33755adb5ba3c296ccf0dd5220143841'

COLORS = [
    'red','cyan','blue','green',
    'white','yellow','magenta',
    'bright_black','bright_red',
    'bright_magenta', 'bright_blue',
    'bright_cyan', 'bright_white'
]
for color in COLORS:
    # No problem with using exec function here
    exec(f'{color} = lambda t: click.style(t, fg="{color}", bold=True)')

def get_sk() -> Union[str, None]:
    """
    This will return StateKey
    from env vars, if present.
    """
    return getenv('TGBOX_SK')

def check_sk():
    if not get_sk():
        click.echo(
              red('You should run ')\
            + white('tgbox-cli cli-start ')\
            + red('firstly.')
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
        click.echo(
            red('You didn\'t connected box yet. Use ')\
            + white('box-connect ') + red('command')
        )
        tgbox.sync(exit_program())
    else:
        box_path = state['TGBOXES'][state['CURRENT_TGBOX']][0]
        basekey  = state['TGBOXES'][state['CURRENT_TGBOX']][1]

        dlb = tgbox.sync(tgbox.api.get_localbox(
            tgbox.keys.BaseKey(basekey), box_path)
        )
        if not ignore_remote:
            drb = tgbox.sync(tgbox.api.get_remotebox(dlb))
        else:
            drb = None

        return dlb, drb

def _select_remotebox(number: int, prefix: str):
    tc, count, erb = _select_account(), 0, None
    iter_over = tc.tgboxes(yield_with=prefix)

    while True:
        try:
            count += 1

            erb = tgbox.sync(tgbox.tools.anext(iter_over))
            if count == number:
                break
        except StopAsyncIteration:
            break

    if not erb:
        click.echo(
        )
        tgbox.sync(exit_program())
    else:
        return erb

def _select_account() -> tgbox.api.TelegramClient:
    check_sk()

    state_key, tc = get_sk(), None
    state = get_state(state_key)

    if 'ACCOUNTS' not in state and 'CURRENT_TGBOX' in state:
        click.echo(
            '\nYou ' + red('didn\'t connected') + ' account with '\
            + white('account-connect, ') + 'however, you already connected Box.'\
        )
        if click.confirm('\nDo you want to use its account?'):
            dlb, drb = _select_box()
            tc = drb._tc
            tgbox.sync(dlb.done())
    if tc:
        tgbox.sync(tc.connect())
        return tc

    elif 'ACCOUNTS' in state:
        session = state['ACCOUNTS'][state['CURRENT_ACCOUNT']]

        tc = tgbox.api.TelegramClient(
            session=session,
            api_id=API_ID,
            api_hash=API_HASH
        )
        tgbox.sync(tc.connect())
        return tc
    else:
        click.echo(
              red('You should run ')\
            + white('tgbox-cli account-connect ')\
            + red('firstly.')
        )
        tgbox.sync(exit_program())

def _format_dxbf(
        dxbf: Union[tgbox.api.DecryptedRemoteBoxFile,
                    tgbox.api.DecryptedLocalBoxFile]) -> str:

    salt = urlsafe_b64encode(dxbf.file_salt).decode()

    idsalt = '[' + bright_red(f'{str(dxbf.id)}') + ':'
    idsalt += (bright_black(f'{salt[:12]}') + ']')
    try:
        name = white(dxbf.file_name)
    except UnicodeDecodeError:
        name = red('[Unable to display]')

    size = green(format_bytes(dxbf.size))

    if dxbf.duration:
        duration = cyan(str(timedelta(seconds=round(dxbf.duration,2))))
        duration = f' ({duration.split(".")[0]})'
    else:
        duration = ''

    time = datetime.fromtimestamp(dxbf.upload_time)
    time = cyan(time.strftime('%d/%m/%y, %H:%M:%S'))

    mimedur = white(dxbf.mime if dxbf.mime else 'regular file')
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
            file_path = red('[Unknown Folder]')

    formatted = (
       f"""\nFile: {idsalt} {name}\n"""
       f"""Path: {splitpath(file_path, 6)}\n"""
       f"""Size: {size}({dxbf.size}), {mimedur}\n"""
    )
    if cattrs:
        formatted += "* CustomAttributes:\n"
        n = 1
        for k,v in tuple(cattrs.items()):
            color = green if n % 2 else yellow; n+=1
            formatted += f'   {white(k)}: {color(v)}\n'

    formatted += f"* Uploaded {time}\n"
    return formatted

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
        click.echo(red(e))
        tgbox.sync(exit_program())

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
    click.echo(cyan('Connecting to Telegram...'))
    tgbox.sync(tc.connect())

    click.echo(cyan('Sending code request...'))
    tgbox.sync(tc.send_code())

    code = click.prompt('Received code', type=int)
    password = click.prompt('Password', hide_input=True)

    click.echo(cyan('Trying to sign-in... '), nl=False)
    tgbox.sync(tc.log_in(code=code, password=password))

    click.echo(green('Successful!'))
    click.echo(cyan('Updating local data... '), nl=False)

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
                other_ta_id = tgbox.sync(other_tc.get_me()).id
            except AttributeError:
                # If session was disconnected
                disconnected_sessions.append(session)
                continue

            if other_tc_id == tc_id:
                tgbox.sync(tc.log_out())
                click.echo(red('Account already added'))
                tgbox.sync(exit_program())

        for d_session in disconnected_sessions:
            state['ACCOUNTS'].remove(d_session)

        state['ACCOUNTS'].append(tc.session.save())
        state['CURRENT_ACCOUNT'] = len(state['ACCOUNTS']) - 1

    write_state(state, state_key)
    click.echo(green('Successful!'))
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
        click.echo(red('You don\'t have any connected account.'))
        tgbox.sync(exit_program())

    elif number < 1 or number > len(state['ACCOUNTS']):
        click.echo(
            red(f'There is no account #{number}. Use ')\
            + white('account-list ') + red('command')
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
        click.echo(green('Disconnected. No more accounts.'))
    else:
        state['CURRENT_ACCOUNT'] = 0
        click.echo(green('Disconnected & switched to the account #1'))
        write_state(state, state_key)
        tgbox.sync(exit_program())

@cli.command()
def account_list():
    """List all connected accounts"""
    check_sk()

    state_key = get_sk()
    state = get_state(state_key)

    if 'ACCOUNTS' not in state or not state['ACCOUNTS']:
        click.echo(
              red('You didn\'t connect any account yet. Run ')\
            + white('tgbox-cli account-connect ') + red('firstly.')
        )
    else:
        click.echo(
            white('\nYou\'re using account ')\
          + red('#' + str(state['CURRENT_ACCOUNT'] + 1)) + '\n'
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
                click.echo(white(f'{count+1}) ') + blue(name) + f' (id{info.id})')
            except AttributeError: # TODO: Info is invalid?
                # If session was disconnected
                click.echo(white(f'{count+1}) ') + red('disconnected, so removed'))
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
        click.echo(
            red('You didn\'t connected account yet. Use ')\
            + white('account-connect ') + red('command')
        )
    elif number < 1 or account > len(state['ACCOUNTS']):
        click.echo(
            red(f'There is no account #{account}. Use ')\
            + white('account-list ') + red('command')
        )
    elif number == state['CURRENT_ACCOUNT']:
        click.echo(
            yellow(f'You already on this account. See other with ')\
            + white('account-list ') + yellow('command')
        )
    else:
        state['CURRENT_ACCOUNT'] = number
        write_state(state, state_key)
        click.echo(green(f'You switched to account #{number}'))

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

        click.echo('\nYour Phrase is ' + magenta(phrase))
        click.echo(
            'Please, write it down on paper and press ' + red('Enter')\
            + ', we will ' + red('clear ') + 'shell for you'
        )
        input(); clear_console()

    elif not phrase:
        phrase, phrase_repeat = 0, 1
        while phrase != phrase_repeat:
            if phrase != 0: # Init value
                click.echo(red('Phrase mismatch! Try again\n'))

            phrase = click.prompt('Phrase', hide_input=True)
            phrase_repeat = click.prompt('Repeat phrase', hide_input=True)

    click.echo(cyan('Making BaseKey... '), nl=False)

    box_salt = bytes.fromhex(box_salt) if box_salt else None

    basekey = tgbox.keys.make_basekey(
        phrase.encode(),
        salt=bytes.fromhex(s),
        n=n, p=p, r=r, dklen=l
    )
    click.echo(green('Successful!'))

    click.echo(cyan('Making RemoteBox... '), nl=False)
    erb = tgbox.sync(tgbox.api.make_remotebox(
        tc, box_name, box_salt=box_salt)
    )
    click.echo(green('Successful!'))

    click.echo(cyan('Making LocalBox... '), nl=False)
    dlb = tgbox.sync(tgbox.api.make_localbox(erb, basekey))
    click.echo(green('Successful!'))

    click.echo(cyan('Updating local data... '), nl=False)

    if 'TGBOXES' not in state:
        state['TGBOXES'] = [[box_name, basekey.key]]
        state['CURRENT_TGBOX'] = 0
    else:
        state['TGBOXES'].append([box_name, basekey.key])
        state['CURRENT_TGBOX'] = len(state['TGBOXES']) - 1

    write_state(state, state_key)
    click.echo(green('Successful!'))

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
def box_connect(box_path, phrase, s, n, p, r, l):
    """Decrypt & connect existing LocalTgbox"""
    check_sk()

    state_key = get_sk()
    state = get_state(state_key)

    click.echo(cyan('Making BaseKey... '), nl=False)

    basekey = tgbox.keys.make_basekey(
        phrase.encode(),
        salt=bytes.fromhex(s),
        n=n, p=p, r=r, dklen=l
    )
    click.echo(green('Successful!'))

    click.echo(cyan('Opening LocalBox... '), nl=False)
    try:
        dlb = tgbox.sync(tgbox.api.get_localbox(basekey, box_path))
    except tgbox.errors.IncorrectKey:
        click.echo(red('Incorrect passphrase!'))
        tgbox.sync(exit_program())

    click.echo(green('Successful!'))

    click.echo(cyan('Updating local data... '), nl=False)

    if 'TGBOXES' not in state:
        state['TGBOXES'] = [[box_path, basekey.key]]
        state['CURRENT_TGBOX'] = 0
    else:
        for _, other_basekey in state['TGBOXES']:
            if basekey.key == other_basekey:
                click.echo(red('This Box is already opened'))
                tgbox.sync(exit_program(dlb=dlb))

        state['TGBOXES'].append([box_path, basekey.key])
        state['CURRENT_TGBOX'] = len(state['TGBOXES']) - 1

    write_state(state, state_key)
    click.echo(green('Successful!'))
    tgbox.sync(exit_program(dlb=dlb))

@cli.command()
@click.option(
    '--number', '-n', required=True, type=int,
    help='Number of other connected box, use box-list command'
)
def box_disconnect(number):
    """Will disconnect selected LocalBox"""
    check_sk()

    state_key = get_sk()
    state = get_state(state_key)

    if 'TGBOXES' not in state or not state['TGBOXES']:
        click.echo(red('You don\'t have any connected Box.'))
    elif number < 1 or number > len(state['TGBOXES']):
        click.echo(red('Invalid number, see box-list'))
    else:
        state['TGBOXES'].pop(number-1)
        if not state['TGBOXES']:
            state.pop('TGBOXES')
            state.pop('CURRENT_TGBOX')
            click.echo(green('Disconnected. No more Boxes.'))
        else:
            state['CURRENT_TGBOX'] = 0
            click.echo(green('Disconnected & switched to the Box #1'))
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
        click.echo(
            red('You didn\'t connected box yet. Use ')\
            + white('box-connect ') + red('command')
        )
    elif number < 0 or number > len(state['TGBOXES'])-1:
        click.echo(
            red(f'There is no box #{number+1}. Use ')\
            + white('box-list ') + red('command')
        )
    elif number == state['CURRENT_TGBOX']:
        click.echo(
            yellow(f'You already use this box. See other with ')\
            + white('box-list ') + yellow('command')
        )
    else:
        state['CURRENT_TGBOX'] = number
        write_state(state, state_key)
        click.echo(green(f'You switched to box #{number+1}'))

    tgbox.sync(exit_program())

@cli.command()
def box_list():
    """List all connected boxes"""
    check_sk()

    state_key = get_sk()
    state = get_state(state_key)

    if 'CURRENT_TGBOX' in state:
        click.echo(
            white('\nYou\'re using Box ')\
          + red('#' + str(state['CURRENT_TGBOX'] + 1)) + '\n'
        )
    else:
        click.echo(yellow('You don\'t have any connected Box.'))
        tgbox.sync(exit_program())

    lost_boxes, count = [], 0

    for box_path, basekey in state['TGBOXES']:
        try:
            dlb = tgbox.sync(tgbox.api.get_localbox(
                tgbox.keys.BaseKey(basekey), box_path)
            )
            name = Path(box_path).name
            salt = urlsafe_b64encode(dlb.box_salt).decode()

            click.echo(white(f'{count+1}) ') + blue(name) + '@' + bright_black(salt))
            tgbox.sync(dlb.done())
        except FileNotFoundError:
            click.echo(white(f'{count+1}) ') + red('Moved, so removed'))
            lost_boxes.append([box_path, basekey])

        count += 1

    for lbox in lost_boxes:
        state['TGBOXES'].remove(lbox)

    if lost_boxes:
        if not state['TGBOXES']:
            state.pop('TGBOXES')
            state.pop('CURRENT_TGBOX')
            click.echo('No more Boxes, use ' + white('box-connect'))
        else:
            state['CURRENT_TGBOX'] = -1
            click.echo(
                'Switched to the last Box. Set other with ' + white('box-switch')
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
    iter_over = tc.iter_dialogs()

    click.echo(yellow('Searching...'))
    while True:
        try:
            dialogue = tgbox.sync(tgbox.tools.anext(iter_over))
            if prefix in dialogue.title and dialogue.is_channel:
                erb = tgbox.api.EncryptedRemoteBox(dialogue, tc)

                erb_name = tgbox.sync(erb.get_box_name())
                erb_salt = tgbox.sync(erb.get_box_salt())
                erb_salt = urlsafe_b64encode(erb_salt).decode()

                click.echo(
                    white(f'{count+1}) ') + blue(erb_name)\
                    + '@' + bright_black(erb_salt)
                )
                count += 1
        except StopAsyncIteration:
            break

    click.echo(yellow('Done.'))
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
    manager = get_manager()

    tgbox.sync(dlb.sync(drb, start_from_id,
        Progress(manager, 'Synchronizing...').update_2)
    )
    manager.stop()

    click.echo(green('Syncing complete'))
    tgbox.sync(exit_program(dlb=dlb, drb=drb))

@cli.command()
@click.option(
    '--number','-n', required=True, type=int,
    help='Number of connected account. We will take session from it.'
)
def box_replace_session(number):
    """Will replace Telegram session of your current Box

    This can be useful if you disconnected your TGBOX in
    Telegram settings (Privacy & Security > Devices) or
    your local TGBOX was too long offline.
    """
    state_key = get_sk()
    state = get_state(state_key)

    dlb, _ = _select_box(ignore_remote=True)

    if number < 1 or number > len(state['ACCOUNTS']):
        click.echo(
            red('Invalid account number! See ')\
          + white('account-list ') + red('command')
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
    click.echo(green('Session replaced successfully'))

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
    click.echo(
        '''\nSend this Key to the Box owner:\n'''
        f'''    {white(reqkey.encode())}\n'''
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
        click.echo(
            red('\nYou didn\'t specified requestkey.\n   You ')\
            + red('will receive decryption key IN PLAIN\n')
        )
        if not click.confirm('Are you TOTALLY sure?'):
            tgbox.sync(exit_program(dlb=dlb))

    click.echo(
        '''\nSend this Key to the Box requester:\n'''
        f'''    {white(sharekey.encode())}\n'''
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

    click.echo(cyan('\nMaking BaseKey... '), nl=False)

    basekey = tgbox.keys.make_basekey(
        phrase.encode(),
        salt=bytes.fromhex(s),
        n=n, p=p, r=r, dklen=l
    )
    click.echo(green('Successful!'))

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

    manager = get_manager()

    tgbox.sync(drb.clone(
        basekey=basekey, box_path=box_path,
        progress_callback=Progress(manager, 'Cloning...').update_2
    ))
    manager.stop()

    click.echo(cyan('\nUpdating local data... '), nl=False)

    if 'TGBOXES' not in state:
        state['TGBOXES'] = [[box_path, basekey.key]]
        state['CURRENT_TGBOX'] = 0
    else:
        for _, other_basekey in state['TGBOXES']:
            if basekey.key == other_basekey:
                click.echo(red('This Box is already opened'))
                tgbox.sync(exit_program(drb=drb))

        state['TGBOXES'].append([box_path, basekey.key])
        state['CURRENT_TGBOX'] = len(state['TGBOXES']) - 1

    write_state(state, state_key)
    click.echo(green('Successful!'))
    tgbox.sync(exit_program(drb=drb))

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
    '--max-workers', '-w', default=10, type=click.IntRange(1,50),
    help='Max amount of files uploaded at the same time',
)
@click.option(
    '--max-bytes', '-w', default=1000000000,
    type=click.IntRange(1000000, 10000000000),
    help='Max amount of bytes uploaded at the same time',
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
            click.echo('\n' + red(e))
            manager.stop()
            tgbox.sync(exit_program(dlb=dlb, drb=drb))

    if path.is_dir():
        iter_over = path.rglob('*')
    else:
        iter_over = (path,)

    manager, to_upload = get_manager(), []
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

        pf = tgbox.sync(dlb.prepare_file(
            file = open(current_path,'rb'),
            file_path = remote_path,
            cattrs = parsed_cattrs,
            make_preview = thumb
        ))
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
        click.echo(red('Incorrect filters! Make sure to use format filter=value'))
        tgbox.sync(exit_program(dlb=dlb, drb=drb))
    except KeyError as e: # Unknown filters
        click.echo(red(f'Filter "{e.args[0]}" doesn\'t exists'))
        tgbox.sync(exit_program(dlb=dlb, drb=drb))

    box = drb if force_remote else dlb

    if non_interactive:
        for dxbfs in bfi_gen(box.search_file(sf, cache_preview=False)):
            click.echo(dxbfs, nl=False)
        click.echo()
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
    '--max-workers', '-w', default=10, type=click.IntRange(1,50),
    help='Max amount of files uploaded at the same time',
)
@click.option(
    '--max-bytes', '-w', default=1000000000,
    type=click.IntRange(1000000, 10000000000),
    help='Max amount of bytes uploaded at the same time',
)
def file_download(
        filters, preview, hide_name,
        hide_folder, out, force_remote,
        max_workers, max_bytes):
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
    dlb, drb = _select_box()
    try:
        sf = filters_to_searchfilter(filters)
    except ValueError as e: # Unsupported filters
        click.echo(red(e.args[0]))
        tgbox.sync(exit_program(dlb=dlb, drb=drb))

    manager, to_upload = get_manager(), []

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
                    file_name = dlbfi.file_name
                    folder = dlbfi.foldername.decode()
                    preview_bytes = tgbox.sync(dlbfi.get_preview())

                elif preview and force_remote:
                    drbfi = tgbox.sync(drb.get_file(dlbfi.id))

                    file_name = drbfi.file_name
                    folder = drbfi.foldername.decode()

                    preview_bytes = tgbox.sync(drbfi.get_preview())

                if preview_bytes is not None:
                    if not out:
                        outpath = tgbox.defaults.DOWNLOAD_PATH\
                            / 'Previews' / folder.lstrip('/')
                        outpath.mkdir(parents=True, exist_ok=True)
                    else:
                        outpath = out

                    with open(outpath/(file_name+'.jpg'), 'wb') as f:
                        f.write(preview_bytes)

                    click.echo(
                        f'''{white(file_name)} preview downloaded '''
                        f'''to {white(str(outpath))}''')
                else:
                    drbfi = tgbox.sync(drb.get_file(dlbfi.id))
                    if not drbfi:
                        click.echo(yellow(
                            f'There is no file with ID={dlbfi.id} in RemoteBox, skipping.'
                        ))
                    else:
                        current_workers -= 1
                        current_bytes -= drbfi.file_size

                        if not out:
                            outpath = tgbox.defaults.DOWNLOAD_PATH / 'Files'
                            outpath.mkdir(parents=True, exist_ok=True)
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
def file_list_forwarded():
    """Will list forwarded from other Box files

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
    while True:
        try:
            xrbf = tgbox.sync(tgbox.tools.anext(iter_over))
            if isinstance(xrbf, tgbox.api.EncryptedRemoteBoxFile):
                time = datetime.fromtimestamp(xrbf.upload_time)
                time = cyan(time.strftime('%d/%m/%y, %H:%M:%S'))

                salt = urlsafe_b64encode(xrbf.file_salt).decode()
                idsalt = '[' + bright_red(f'{str(xrbf.id)}') + ':'
                idsalt += (bright_black(f'{salt[:12]}') + ']')

                size = green(format_bytes(xrbf.file_size))
                name = red('[N\A: No FileKey available]')

                req_key = white(xrbf.get_requestkey(dlb._mainkey).encode())

                formatted = (
                   f"""\nFile: {idsalt} {name}\n"""
                   f"""Size, Time: {size}({xrbf.file_size}), {time}\n"""
                   f"""RequestKey: {req_key}"""
                )
                click.echo(formatted)
        except StopAsyncIteration:
            click.echo()
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
    dlb, _ = _select_box(ignore_remote=True)
    dlbf = tgbox.sync(dlb.get_file(id=id))

    if not dlbf:
        click.echo(red(f'There is no file in LocalBox by ID {id}'))
        tgbox.sync(exit_program(dlb=dlb))

    requestkey = requestkey if not requestkey\
        else tgbox.keys.Key.decode(requestkey)

    sharekey = dlbf.get_sharekey(requestkey)

    if not requestkey:
        click.echo(
            red('\nYou didn\'t specified requestkey.\n   You ')\
            + red('will receive decryption key IN PLAIN\n')
        )
        if not click.confirm('Are you TOTALLY sure?'):
            tgbox.sync(exit_program(dlb=dlb))

    click.echo(
        '''\nSend this Key to the Box requester:\n'''
        f'''    {white(sharekey.encode())}\n'''
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
        click.echo(red(f'There is no file in RemoteBox by ID {id}'))
        tgbox.sync(exit_program(dlb=dlb, drb=drb))
    try:
        key = tgbox.keys.Key.decode(key)
    except tgbox.errors.IncorrectKey:
        click.echo(red(f'Specified Key is invalid'))
    else:
        if isinstance(key, tgbox.keys.ShareKey):
            key = tgbox.keys.make_importkey(
                key=dlb._mainkey, sharekey=key,
                box_salt=erbf.file_salt
            )
        drbf = tgbox.sync(erbf.decrypt(key))
        dlbf = tgbox.sync(dlb.import_file(drbf, file_path))

        click.echo(_format_dxbf(drbf))

    tgbox.sync(exit_program(dlb=dlb, drb=drb))

@cli.command()
def dir_list():
    """List all directories in LocalBox"""

    dlb, _ = _select_box(ignore_remote=True)
    dirs = dlb.contents(ignore_files=True)

    while True:
        try:
            dir = tgbox.sync(tgbox.tools.anext(dirs))
            tgbox.sync(dir.lload(full=True))
            click.echo(str(dir))
        except StopAsyncIteration:
            break

    tgbox.sync(exit_program(dlb=dlb))

@cli.command()
def cli_start():
    """Get commands for initializing TGBOX-CLI"""
    if get_sk():
        click.echo(white('CLI is already initialized.'))
    else:
        state_key = urlsafe_b64encode(
            tgbox.crypto.get_rnd_bytes(32)
        )
        if platform in ('win32', 'cygwin', 'cli'):
            commands = (
                '''%__APPDIR__%doskey.exe /listsize=0 # Disable shell history\n'''
               f'''set TGBOX_SK={state_key.decode()}\n'''
                '''%__APPDIR__%doskey.exe /listsize=50 # Enable shell history\n'''
                '''cls # Clear this shell\n'''
            )
        else:
            click.echo(blue('\n# (Execute commands below if eval doesn\'t work)\n'))

            real_commands = (
                '''set +o history # Disable shell history\n'''
               f'''export TGBOX_SK={state_key.decode()}\n'''
                '''set -o history # Enable shell history\n'''
                '''clear # Clear this shell'''
            )
            click.echo(real_commands)
            commands = 'eval "$(!!)" || true && clear\n'

        click.echo(
            yellow('\nWelcome to the TGBOX-CLI!\n\n')\
            + 'Copy & Paste below commands to your shell:\n\n'\
            + white(commands)
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
        ffmpeg_version = green(sp_result.stdout.split(b' ',3)[2].decode())
    except:
        ffmpeg_version = red('NO')

    click.echo(
        f'''\n# Copyright {white('(c) Non [github.com/NotStatilko]')}, the MIT License\n'''
        f'''# Author Email: {white('thenonproton@protonmail.com')}\n\n'''
        f'''TGBOX-CLI Version: {yellow(ver[0])}\n'''
        f'''TGBOX Version: {magenta(ver[1])}\n\n'''
        f'''FFMPEG: {ffmpeg_version}\n'''
        f'''FAST_ENCRYPTION: {green('YES') if tgbox.crypto.FAST_ENCRYPTION else red('NO')}\n'''
        f'''FAST_TELETHON: {green('YES') if tgbox.crypto.FAST_TELETHON else red('NO')}\n'''
    )
@cli.command()
@click.argument('defaults',nargs=-1)
def cli_default(defaults):
    """Change the TGBOX default values to your own

    \b
    I.e:\b
        # Change METADATA_MAX to the max allowed size
        tgbox-cli cli-default METADATA_MAX=1677721
        \b
        # Change download path from DownloadsTGBOX to Downloads
        tgbox-cli cli-default DOWNLOAD_PATH=Downloads
    """
    dlb, _ = _select_box(ignore_remote=True)

    for default in defaults:
        try:
            key, value = default.split('=',1)
            tgbox.sync(dlb.defaults.change(key, value))
            click.echo(green(f'Successfuly changed {key} to {value}'))
        except AttributeError as e:
            click.echo(red(f'Default {key} doesn\'t exist, skipping'))

    tgbox.sync(exit_program(dlb=dlb))

if __name__ == '__main__':
    safe_cli()
