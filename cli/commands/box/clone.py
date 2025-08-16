import click

from pathlib import Path

from ..group import cli_group
from ..helpers import select_remotebox
from ...tools.terminal import echo, ProgressBar
from ...config import tgbox, TGBOX_CLI_SHOW_PASSWORD


@cli_group.command()
@click.option(
    '--box-path', '-p', help='Path to which we will clone',
    type=click.Path(writable=True, readable=True, path_type=Path)
)
@click.option(
    '--box-name', '-b',
    help='Filename to your future cloned LocalBox DB',
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
    '--phrase', required=True,
    hide_input=(not TGBOX_CLI_SHOW_PASSWORD),
    prompt='Phrase to your cloned Box',
    help='To clone Box you need to specify phrase to it'
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
@click.pass_context
def box_clone(
        ctx, box_path, box_name,
        box_number, prefix, key,
        phrase, s, n, p, r, l):
    """
    Clone RemoteBox to LocalBox by your passphrase
    """
    erb = select_remotebox(box_number, prefix)

    try:
        key = tgbox.keys.Key.decode(key)
    except tgbox.errors.IncorrectKey:
        pass

    echo('\n[C0b]Making BaseKey...[X] ', nl=False)

    basekey = tgbox.keys.make_basekey(
        phrase.strip().encode(),
        salt=bytes.fromhex(s),
        n=n, p=p, r=r, dklen=l
    )
    echo('[G0b]Successful![X]')

    if key is None:
        key = basekey
    else:
        key = tgbox.keys.make_importkey(
            key=basekey, sharekey=key,
            salt=tgbox.sync(erb.get_box_salt())
        )
    drb = tgbox.sync(erb.decrypt(key=key))

    dlb = tgbox.sync(tgbox.api.local.clone_remotebox(
        drb = drb,
        basekey = basekey,
        box_name = box_name,
        box_path = box_path,
        progress_callback = ProgressBar(
            ctx.obj.enlighten_manager, 'Cloning...').update_2
        )
    )
    echo('\n[C0b]Updating local data...[X] ', nl=False)

    localbox_path = str(Path(dlb.tgbox_db.db_path).resolve())
    box_data = [localbox_path, basekey.key]

    for other_box_data in ctx.obj.session['BOX_LIST']:
        if other_box_data == box_data:
            echo('[R0b]This Box is already opened[X]')
            break
    else:
        ctx.obj.session['BOX_LIST'].append(box_data)
        ctx.obj.session['CURRENT_BOX'] = len(ctx.obj.session['BOX_LIST']) - 1

        ctx.obj.session.commit()
        echo('[G0b]Successful![X]')

    tgbox.sync(dlb.done())
    tgbox.sync(drb.done())

