import click

from pathlib import Path

from .close import box_close
from ..group import cli_group
from ..helpers import ctx_require
from ...tools.terminal import echo
from ...config import tgbox


@cli_group.command()
@ctx_require(dlb=True, drb=True)
def box_delete(ctx):
    """Completely remove your Box with all files in it"""

    dlb_box_name = Path(ctx.obj.dlb.tgbox_db.db_path).name
    drb_box_name = tgbox.sync(ctx.obj.drb.get_box_name())

    files_total = tgbox.sync(ctx.obj.drb.get_files_total())

    warning_message = (
        '    [R0b]WARNING! You are trying to COMPLETELY REMOVE your\n'
       f'    CURRENT SELECTED Box with {files_total} FILES IN IT. After this\n'
        '    operation, you WILL NOT BE ABLE to recover or download\n'
        '    your files IN ANY WAY. If you wish to remove (for some\n'
       f'    strange case) only LocalBox then remove the "{dlb_box_name}"\n'
        '    file on your Computer. This command will remove the Local &\n'
        '    Remote BOTH. Proceed only if you TOTALLY understand this![X]'
    )
    echo('\n' + warning_message)

    echo(
       f'\n@ Please enter [Y0b]{drb_box_name}[X] to '
        '[R0b]DESTROY[X] your Box or press [B0b]CTRL+C[X] to abort'
    )
    user_input = click.prompt('\nBox name')

    if user_input == drb_box_name:
        echo('You typed Box name [R0b]correctly[X].\n')

        if click.confirm('The last question: are you sure?'):
            echo('\n[C0b]Closing you LocalBox...[X] ', nl=False)
            ctx.invoke(box_close, number=ctx.obj.session['CURRENT_BOX']+1)

            echo('[C0b]Completely removing your LocalBox...[X] ', nl=False)
            tgbox.sync(ctx.obj.dlb.delete())
            echo('[G0b]Successful![X]')

            echo('[C0b]Completely removing your RemoteBox...[X] ', nl=False)
            tgbox.sync(ctx.obj.drb.delete())
            echo('[G0b]Successful![X]')
        else:
            echo('\nYou [R0b]didn\'t agreed[X]. [Y0b]Aborting[X].')

    else:
        echo(f'\nYou typed [W0b]{user_input}[X], which is incorrect. [Y0b]Aborting.[X]')

