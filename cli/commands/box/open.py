import click

from pathlib import Path

from ..group import cli_group
from ..helpers import ctx_require
from ...tools.terminal import echo
from ...config import tgbox, TGBOX_CLI_SHOW_PASSWORD


@cli_group.command()
@click.option(
    '--box-path', '-b',

    required = True,
    prompt = True,

    type = click.Path(
        exists = True,
        dir_okay = False,
        readable = True,
        path_type = Path
    ),
    help = 'Path to the LocalBox DB file',
)
@click.option(
    '--phrase', '-p', required=True,
    prompt=True, hide_input=(not TGBOX_CLI_SHOW_PASSWORD),
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
@click.option(
    '--no-switch', is_flag=True,
    help='If specified, will not switch to Box you connect'
)
@ctx_require(session=True)
def box_open(ctx, box_path, phrase, s, n, p, r, l, no_switch):
    """Decrypt & connect existing LocalBox"""

    echo('[C0b]Making BaseKey...[X] ', nl=False)

    basekey = tgbox.keys.make_basekey(
        phrase.strip().encode(),
        salt=bytes.fromhex(s),
        n=n, p=p, r=r, dklen=l
    )
    echo('[G0b]Successful![X]')

    box_path = box_path.resolve()

    echo('[C0b]Opening LocalBox...[X] ', nl=False)
    try:
        dlb = tgbox.sync(tgbox.api.get_localbox(basekey, box_path))
    except tgbox.errors.AESError:
        echo('[R0b]Incorrect passphrase![X]')
    else:
        echo('[G0b]Successful![X]')
        echo('[C0b]Updating local data...[X] ', nl=False)

        localbox_path = str(Path(dlb.tgbox_db.db_path).resolve())
        box_data = [localbox_path, basekey.key]

        for other_box_data in ctx.obj.session['BOX_LIST']:
            if other_box_data == box_data:
                echo('[R0b]This Box is already opened[X]')
                break
        else:
            ctx.obj.session['BOX_LIST'].append(box_data)

            if not no_switch:
                ctx.obj.session['CURRENT_BOX'] = len(ctx.obj.session['BOX_LIST']) - 1

            ctx.obj.session.commit()
            echo('[G0b]Successful![X]')

        tgbox.sync(dlb.done())
