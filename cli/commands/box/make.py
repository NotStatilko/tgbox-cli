import click

from pathlib import Path

from ..group import cli_group
from ..helpers import ctx_require
from ...tools.terminal import echo, clear_console
from ...config import tgbox, TGBOX_CLI_SHOW_PASSWORD


@cli_group.command()
@click.option(
    '--box-path', '-p', help='Path to store LocalBox DB file',
    type=click.Path(writable=True, readable=True, path_type=Path)
)
@click.option(
    '--box-name', '-b', prompt=True,
    help='Name of your future Box',
)
@click.option(
    '--box-salt', help='BoxSalt as hexadecimal'
)
@click.option(
    '--phrase', help='Passphrase to your Box. Keep it secret'
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
@ctx_require(account=True)
def box_make(ctx, box_path, box_name, box_salt, phrase, s, n, p, r, l):
    """Create the new Box (Remote & Local)"""

    if not phrase and click.confirm('Generate passphrase for you?'):
        phrase = tgbox.keys.Phrase.generate(6).phrase.decode()
        echo(f'\nYour Phrase is [M0b]{phrase}[X]')

        echo(
            'Please, write it down [W0b]on paper[X] '
            'and press [R0b]Enter[X]'
            ', we will [R0b]clear[X] shell for you'
        )
        input(); clear_console()

    elif not phrase:
        phrase, phrase_repeat = 0, 1
        while phrase != phrase_repeat:
            if phrase != 0: # Init value
                echo('[R0b]Phrase mismatch! Try again[X]\n')

            phrase = click.prompt(
                text = 'Phrase',
                hide_input = (not TGBOX_CLI_SHOW_PASSWORD)
            )
            phrase_repeat = click.prompt(
                text = 'Repeat phrase',
                hide_input = (not TGBOX_CLI_SHOW_PASSWORD)
            )

    echo('[C0b]Making BaseKey...[X] ', nl=False)

    if box_salt:
        box_salt = tgbox.crypto.BoxSalt(bytes.fromhex(box_salt))

    basekey = tgbox.keys.make_basekey(
        phrase.strip().encode(),
        salt=bytes.fromhex(s),
        n=n, p=p, r=r, dklen=l
    )
    echo('[G0b]Successful![X]')

    echo('[C0b]Making RemoteBox...[X] ', nl=False)
    erb = tgbox.sync(tgbox.api.make_remotebox(
        ctx.obj.account, box_name, box_salt=box_salt)
    )
    echo('[G0b]Successful![X]')

    echo('[C0b]Making LocalBox...[X] ', nl=False)
    dlb = tgbox.sync(tgbox.api.make_localbox(
        erb, basekey, box_path=box_path, box_name=box_name))
    echo('[G0b]Successful![X]')

    echo('[C0b]Updating local data...[X] ', nl=False)

    localbox_path = str(Path(dlb.tgbox_db.db_path).resolve())

    ctx.obj.session['BOX_LIST'].append([localbox_path, basekey.key])
    ctx.obj.session['CURRENT_BOX'] = len(ctx.obj.session['BOX_LIST']) - 1

    ctx.obj.session.commit()

    tgbox.sync(erb.done())
    tgbox.sync(dlb.done())

    echo('[G0b]Successful![X]')
