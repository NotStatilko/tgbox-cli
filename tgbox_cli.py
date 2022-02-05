import click
import tgbox

from pathlib import Path
from hashlib import sha256
from asyncio import gather

from ast import literal_eval
from pickle import loads, dumps

from base64 import urlsafe_b64encode
from traceback import format_exception
from typing import Union, AsyncGenerator
from datetime import datetime, timedelta

from os import (
    getenv, _exit, 
    name as os_name,
    system as os_system
)
from tools import (
    Progress, format_bytes, sync_async_gen,
    filters_to_searchfilter, clear_console,
    exit_program
)
from enlighten import get_manager

COLORS = [
    'red','cyan','blue','green',
    'white','yellow','magenta',
    'bright_black','bright_red'
]
for color in COLORS:
    # No problem with using exec function here
    exec(f'{color} = lambda t: click.style(t, fg="{color}", bold=True)')

def get_sk() -> Union[str, None] :
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
        exit_program()
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

def _select_box():
    check_sk()

    state_key = get_sk()
    state = get_state(state_key)
    
    if 'TGBOXES' not in state:
        click.echo(
            red('You didn\'t connected box yet. Use ')\
            + white('box-connect ') + red('command')
        )
        exit_program()
    else:
        box_path = state['TGBOXES'][state['CURRENT_TGBOX']][0]
        basekey  = state['TGBOXES'][state['CURRENT_TGBOX']][1]

        dlb = tgbox.sync(tgbox.api.get_local_box(
            tgbox.keys.BaseKey(basekey), box_path)
        )
        drb = tgbox.sync(tgbox.api.get_remote_box(dlb))

        return dlb, drb

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
        exit_program()

@cli.command()
@click.option(
    '--phone', '-p', required=True, prompt=True,
    help='Phone number of your Telegram account'
)
def account_connect(phone):
    """Connect to Telegram"""
    check_sk()

    ta = tgbox.api.TelegramAccount(phone_number=phone)
    
    click.echo(cyan('Connecting to Telegram...'))
    tgbox.sync(ta.connect())

    click.echo(cyan('Sending code request...'))
    tgbox.sync(ta.send_code_request())

    code = click.prompt('Received code', type=int)
    password = click.prompt('Password', hide_input=True)

    click.echo(cyan('Trying to sign-in... '), nl=False)
    tgbox.sync(ta.sign_in(code=code, password=password))
    
    click.echo(green('Successful!'))
    click.echo(cyan('Updating local data... '), nl=False)
    
    state_key = get_sk()
    state = get_state(state_key)

    if 'ACCOUNTS' not in state:
        state['ACCOUNTS'] = [ta.get_session()]
        state['CURRENT_ACCOUNT'] = 0 # Index
    else:
        disconnected_sessions = []
        for session in state['ACCOUNTS']:
            other_ta = tgbox.sync(
                tgbox.api.TelegramAccount(session=session).connect()
            )
            try:
                other_ta_id = tgbox.sync(other_ta.TelegramClient.get_me()).id
                ta_id = tgbox.sync(other_ta.TelegramClient.get_me()).id
            except AttributeError:
                # If session was disconnected
                disconnected_sessions.append(session)
                continue
            
            if other_ta_id == ta_id:
                tgbox.sync(ta.log_out())
                click.echo(red('Account already added')); exit_program()

        for d_session in disconnected_sessions:
            state['ACCOUNTS'].remove(d_session)
            
        state['ACCOUNTS'].append(ta.get_session())
        state['CURRENT_ACCOUNT'] = len(state['ACCOUNTS']) - 1 
        
    write_state(state, state_key)
    click.echo(green('Successful!'))
    exit_program()

@cli.command()
def account_list():
    """List all connected accounts"""
    check_sk()

    state_key = get_sk()
    state = get_state(state_key)
        
    disconnected_sessions = []
    for count, session in enumerate(state['ACCOUNTS']):
        try:
            ta = tgbox.sync(tgbox.api.TelegramAccount(session=session).connect())
            info = tgbox.sync(ta.TelegramClient.get_me())

            name = f'@{info.username}' if info.username else info.first_name
            click.echo(white(f'{count+1}) ') + blue(name) + f' (id{info.id})')
        except AttributeError:
            # If session was disconnected
            click.echo(white(f'{count+1}) ') + red('disconnected, so removed'))
            disconnected_sessions.append(session)

    for d_session in disconnected_sessions:
        state['ACCOUNTS'].remove(d_session)
        
    write_state(state, state_key); exit_program()

@cli.command()
@click.option(
    '--number', '-n', required=True, type=int,
    help='Switch to another connected account'
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
    elif number < 1 or number > len(state['ACCOUNTS']):
        click.echo(
            red(f'There is no account #{number}. Use ')\
            + white('account-list ') + red('command')
        )
    elif number == state['CURRENT_ACCOUNT']:
        click.echo(
            blue(f'You already on this account. See other with ')\
            + white('account-list ') + blue('command')
        )
    else:
        state['CURRENT_ACCOUNT'] = number
        write_state(state, state_key)
        click.echo(green(f'You switched to account #{number}'))

    exit_program()

@cli.command()
@click.option(
    '--box-name', '-b', required=True, 
    prompt=True, help='Name of your Box'
)
@click.option(
    '--phrase', '-p', 
    help='Passphrase to your Box. Keep it secret'
)
@click.option(
    '--salt', '-s', 's', 
    default=tgbox.constants.SCRYPT_SALT.hex(),
    help='Scrypt salt as hexadecimal number'
)
@click.option(
    '--scrypt-n', '-N', 'n', help='Scrypt N',
    default=tgbox.constants.SCRYPT_N
)
@click.option(
    '--scrypt-p', '-P', 'p', help='Scrypt P',
    default=tgbox.constants.SCRYPT_P
)
@click.option(
    '--scrypt-r', '-R', 'r', help='Scrypt R',
    default=tgbox.constants.SCRYPT_R
)
@click.option(
    '--scrypt-dklen', '-L', 'l', help='Scrypt key length',
    default=tgbox.constants.SCRYPT_DKLEN
)
def box_make(box_name, phrase, s, n, p, r, l):
    """Create new TGBOX, the Remote and Local"""

    state_key = get_sk()
    state = get_state(state_key)

    if check_sk() and 'ACCOUNTS' in state:
        if not phrase and click.confirm('Do you want generated phrase?'):
            phrase = tgbox.keys.Phrase.generate().phrase.decode()

            click.echo('\nYour Phrase is ' + magenta(phrase))
            click.echo(
                'Please, write it down on paper and press ' + red('Enter')\
                + ', we will ' + red('clear ') + 'shell for you'
            )
            input(); clear_console()
        else:
            if not phrase:
                click.echo(
                    red('Phrase is required. Use ')\
                    + white('--phrase ') + red('kwarg.')
                )
        if phrase:
            click.echo(cyan('Connecting to Telegram... '), nl=False) 
            
            session = state['ACCOUNTS'][state['CURRENT_ACCOUNT']]
            ta = tgbox.api.TelegramAccount(session=session)

            tgbox.sync(ta.connect())
            click.echo(green('Successful!'))

            click.echo(cyan('Making BaseKey... '), nl=False) 
            
            basekey = tgbox.keys.make_basekey(
                phrase.encode(), 
                salt=bytes.fromhex(s), 
                n=n, p=p, r=r, dklen=l
            )
            click.echo(green('Successful!'))

            click.echo(cyan('Making RemoteBox... '), nl=False) 
            erb = tgbox.sync(tgbox.api.make_remote_box(ta, box_name))
            click.echo(green('Successful!'))

            click.echo(cyan('Making LocalBox... '), nl=False) 
            dlb = tgbox.sync(tgbox.api.make_local_box(erb, ta, basekey))
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
            exit_program()
    else:
        click.echo(
              red('You should run ')\
            + white('tgbox-cli connect ')\
            + red('firstly.')
        )

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
    default=tgbox.constants.SCRYPT_SALT.hex(),
    help='Scrypt salt as hexadecimal number'
)
@click.option(
    '--scrypt-n', '-N', 'n', help='Scrypt N',
    default=tgbox.constants.SCRYPT_N
)
@click.option(
    '--scrypt-p', '-P', 'p', help='Scrypt P',
    default=tgbox.constants.SCRYPT_P
)
@click.option(
    '--scrypt-r', '-R', 'r', help='Scrypt R',
    default=tgbox.constants.SCRYPT_R
)
@click.option(
    '--scrypt-dklen', '-L', 'l', help='Scrypt key length',
    default=tgbox.constants.SCRYPT_DKLEN
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
    dlb = tgbox.sync(tgbox.api.get_local_box(basekey, box_path))
    click.echo(green('Successful!'))
    
    click.echo(cyan('Updating local data... '), nl=False)

    if 'TGBOXES' not in state:
        state['TGBOXES'] = [[box_path, basekey.key]]
        state['CURRENT_TGBOX'] = 0
    else:
        for _, other_basekey in state['TGBOXES']:
            if basekey.key == other_basekey:
                click.echo(red('This Box is already opened'))
                exit_program()

        state['TGBOXES'].append([box_path, basekey.key])
        state['CURRENT_TGBOX'] = len(state['TGBOXES']) - 1 
        
    write_state(state, state_key)
    click.echo(green('Successful!'))
    exit_program()


@cli.command()
@click.option(
    '--number', '-n', required=True, type=int,
    help='Switch to another connected box'
)
def box_switch(number):
    """This will set your CURRENT_BOX to selected"""
    check_sk()
    
    state_key = get_sk()
    state = get_state(state_key)
    
    if 'TGBOXES' not in state:
        click.echo(
            red('You didn\'t connected box yet. Use ')\
            + white('box-connect ') + red('command')
        )
    elif number < 1 or number > len(state['TGBOXES']):
        click.echo(
            red(f'There is no box #{number}. Use ')\
            + white('box-list ') + red('command')
        )
    elif number == state['CURRENT_ACCOUNT']:
        click.echo(
            blue(f'You already use this box. See other with ')\
            + white('box-list ') + blue('command')
        )
    else:
        state['CURRENT_TGBOX'] = number
        write_state(state, state_key)
        click.echo(green(f'You switched to box #{number}'))

    exit_program()

@cli.command()
def box_list():
    """List all connected boxes"""
    check_sk()

    state_key = get_sk()
    state = get_state(state_key)
        
    lost_boxes, count = [], 0
    for box_path, basekey in state['TGBOXES']:
        try:
            dlb = tgbox.sync(tgbox.api.get_local_box(
                tgbox.keys.BaseKey(basekey), box_path)
            )
            name = Path(box_path).name
            
            salt = urlsafe_b64encode(dlb.box_salt)[:20].decode() + '...'
            click.echo(white(f'{count+1}) ') + blue(name) + f' salt#{salt}')

        except FileNotFoundError:
            click.echo(white(f'{count+1}) ') + red('moved, so removed'))
            lost_boxes.append([box_path, basekey])

        count += 1

    for lbox in lost_boxes:
        state['TGBOXES'].remove(lbox)
        
    write_state(state, state_key); exit_program()

@cli.command()
@click.option(
    '--path', '-p', required=True, prompt=True, 
    help='Will upload specified path. If directory, upload all files in it',
    type=click.Path(readable=True, dir_okay=True, path_type=Path)
)
@click.option(
    '--folder', '-f', 
    help='Folder of this file. Will be file\'s if not specified'
)
@click.option(
    '--comment', '-c',
    help='File comment. Python\'s dict ({}) will be converted to CustomAttributes'
)
@click.option(
    '--thumb/--no-thumb', default=True,
    help='Add thumbnail or not, boolean'
)
@click.option(
    '--workers', '-w', default=3, type=click.IntRange(1,10), 
    help='How many files will be uploaded at the same time',
)
def file_upload(path, folder, comment, thumb, workers):
    dlb, drb = _select_box()
    
    def _upload(to_upload: list):
        try:
            tgbox.sync(gather(*to_upload))
            to_upload.clear()
        except tgbox.errors.NotEnoughRights as e:
            click.echo('\n' + red(e))
            manager.stop()
            exit_program()

    if path.is_dir():
        iter_over = path.rglob('*')
    else:
        iter_over = (path,)
    
    manager, to_upload = get_manager(), []
    for file_path in iter_over:
        if file_path.is_dir():
            continue

        current_folder = str(file_path.parent) if not folder else folder
        try:
            comment_ = literal_eval(comment)
            comment = tgbox.tools.CustomAttributes.make(**comment_)
        except (ValueError, TypeError, SyntaxError):
            comment = comment.encode() if comment else b''

        ff = tgbox.sync(dlb.make_file(
            file = open(file_path,'rb'),
            foldername = current_folder.encode(), 
            comment = comment,
            make_preview = thumb
        ))
        if len(to_upload) >= workers:
            _upload(to_upload)

        to_upload.append(drb.push_file(ff, Progress(
            manager, file_path.name).update))

    if to_upload: # If any files left
        _upload(to_upload)
    
    manager.stop()
    exit_program()

@cli.command()
@click.argument('filters',nargs=-1)
@click.option(
    '--force-remote','-r', is_flag=True,
    help='If specified, will fetch files from RemoteBox'
)
def file_list(filters, force_remote):
    dlb, drb = _select_box()
    
    def bfi_gen(search_file_gen):
        for bfi in sync_async_gen(search_file_gen):
            id = bright_red(f'[{str(bfi.id)}]')
            indent = ' ' * (len(str(bfi.id)) + 3)

            name = white(bfi.file_name.decode())
            size = green(format_bytes(bfi.size))

            salt = yellow(urlsafe_b64encode(bfi.file_salt).decode()[:25] + '...')
            
            dur_color = cyan if bfi.duration else bright_black
            duration = dur_color(str(timedelta(seconds=round(bfi.duration,2))))
            duration = duration.split('.')[0]

            time = datetime.fromtimestamp(bfi.upload_time)
            time = magenta(time.strftime('%d/%m/%y, %H:%M:%S'))

            if bfi.comment:
                comment_ = tgbox.tools.CustomAttributes.parse(bfi.comment)
                if comment_:
                    comment = 'Attributes: '
                    for k,v in comment_.items():
                        try:
                            v = v.decode()
                        except UnicodeDecodeError:
                            v = v.hex()
                        try:
                            k = k.decode()
                        except AttributeError:
                            k = k
                        except UnicodeDecodeError:
                            k = k.hex()

                        comment += '\n' + (indent*2)[:-3] + '* '\
                            + cyan(k) + white('=') + green(v) + ' '
                else:
                    comment = 'Comment: ' + magenta(bfi.comment.decode())
            else:
                comment = 'Comment: ' + bright_black('Empty.')
            
            if len(bfi.foldername.decode()) > 32:
                folder = blue('...' + bfi.foldername.decode()[-32:])
            else:
                folder = blue(bfi.foldername.decode())

            text = (
                f'''{id} {name}\n'''
                f'''{indent}| Folder: {folder}\n'''
                f'''{indent}| Upload Time: {time}\n'''
                f'''{indent}| Salt: {salt}\n'''
                f'''{indent}| Size, Duration: {size}, {duration}\n'''
                f'''{indent}| {comment}\n\n'''
            )
            yield text
    
    sf = filters_to_searchfilter(filters)
    box = drb if force_remote else dlb

    click.echo_via_pager(bfi_gen(box.search_file(sf)))
    exit_program()

@cli.command()
@click.argument('filters',nargs=-1)
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
    '--workers', '-w', default=3, type=click.IntRange(1,10), 
    help='How many files will be downloaded at the same time',
)
def file_download(
        filters, preview, hide_name, 
        hide_folder, out, force_remote, workers):
    """
    """
    dlb, drb = _select_box()
    sf = filters_to_searchfilter(filters)

    box = drb if force_remote else dlb
    manager, to_upload = get_manager(), []
    
    to_download = dlb.search_file(sf)
    while True:
        try:
            to_gather_files = []
            for _ in range(workers):
                dlbfi = tgbox.sync(tgbox.tools.anext(to_download))
                preview_bytes = None

                if preview and not force_remote:
                    file_name = dlbfi.file_name.decode()
                    folder = dlbfi.foldername.decode()
                    preview_bytes = tgbox.sync(dlbfi.get_preview())

                elif preview and force_remote:
                    drbfi = tgbox.sync(drb.get_file(dlbfi.id))

                    file_name = drbfi.file_name.decode()
                    folder = drbfi.foldername.decode()

                    preview_bytes = tgbox.sync(drbfi.get_preview())

                if preview_bytes is not None:
                    if not out:
                        outpath = tgbox.constants.DOWNLOAD_PATH\
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
                    if not out:
                        outpath = tgbox.constants.DOWNLOAD_PATH / 'Files'
                        outpath.mkdir(parents=True, exist_ok=True)
                    else:
                        outpath = out
                    
                    p_file_name = 'Filename was hidden' if hide_name\
                        else drbfi.file_name.decode()

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
        
        except StopAsyncIteration:
            break

    if to_gather_files:
        tgbox.sync(gather(*to_gather_files))
        
    manager.stop()
    exit_program()

@cli.command()
def cli_start():
    """Get commands for initializing TGBOX-CLI"""
    if get_sk():
        click.echo(white('You\'re already connected.'))
    else:
        state_key = urlsafe_b64encode(
            tgbox.crypto.get_rnd_bytes(32)
        )
        commands = (
            '''set +o history # Will disable history\n'''
           f'''export TGBOX_SK={state_key.decode()}\n'''
            '''set -o history # Will enable history\n'''
            '''clear # Will clear this shell\n'''
        )
        click.echo(
            yellow('\nWelcome to the TGBOX-CLI!\n\n')\
            + 'Copy & Paste below commands to your shell:\n\n'\
            + white(commands)
        )

if __name__ == '__main__':
    safe_cli()
