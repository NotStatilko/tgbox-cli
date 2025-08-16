import click
from base64 import urlsafe_b64encode
from pathlib import Path

from ..group import cli_group
from ..helpers import check_ctx
from ...tools.terminal import echo
from ...tools.strings import split_string
from ...tools.other import sync_async_gen
from ...config import tgbox


@cli_group.command()
@click.option(
    '--remote', '-r', is_flag=True,
    help='If specified, will search for Remote Boxes on Account'
)
@click.option(
    '--prefix', '-p', default=tgbox.defaults.REMOTEBOX_PREFIX,
    help='Channels with this prefix will be searched (only if --remote)'
)
@click.pass_context
def box_list(ctx, remote, prefix):
    """List all Boxes (--remote for Remote)"""

    if remote:
        check_ctx(ctx, account=True)
        count = 0

        echo('[Y0b]Searching...[X]')
        for chat in sync_async_gen(ctx.obj.account.iter_dialogs()):
            if prefix in chat.title and chat.is_channel:
                erb = tgbox.api.EncryptedRemoteBox(chat, ctx.obj.account)

                erb_name = tgbox.sync(erb.get_box_name())
                erb_salt = tgbox.sync(erb.get_box_salt())
                erb_salt = urlsafe_b64encode(erb_salt.salt).decode()
                erb_desc = tgbox.sync(erb.get_box_description())

                count_id = str(count+1).zfill(2)
                echo(
                    f'[W0b]{count_id}[X]) [B0b]{erb_name}[X]'
                    f'@[X1b]{erb_salt}[X]'
                )
                if erb_desc:
                    erb_desc = split_string(f'{erb_desc}', 4, '>')
                    echo(f'    Description: [Y0b]{erb_desc}[X]')
                count += 1

        echo('[Y0b]Done.[X]')
    else:
        check_ctx(ctx, session=True)

        if ctx.obj.session['CURRENT_BOX'] is None:
            echo(
                '[R0b]You didn\'t opened any box yet. Use[X] '
                '[W0b]box-open[X] [R0b]command firstly.[X]')
        else:
            echo(
                '\n[W0b]You\'re using Box[X] '
               f'[R0b]#{str(ctx.obj.session["CURRENT_BOX"]+1)}[X]\n'
            )
            lost_boxes, count = [], 0

            for box_path, basekey in ctx.obj.session['BOX_LIST']:
                try:
                    name = Path(box_path).name

                    dlb = tgbox.sync(tgbox.api.get_localbox(
                        tgbox.keys.BaseKey(basekey), box_path)
                    )
                    salt = urlsafe_b64encode(dlb.box_salt.salt).decode()

                    count_id = str(count+1).zfill(2)
                    echo(
                        f'[W0b]{count_id})[X] [B0b]{name}[X]'
                        f'@[X1b]{salt}[X]'
                    )
                    tgbox.sync(dlb.done())
                except FileNotFoundError:
                    count_id = str(count+1).zfill(2)
                    echo(
                       f'[W0b]{count_id})[X] [R0b]{name} LocalBox '
                        'file was moved, so disconnected.[X]'
                    )
                    lost_boxes.append([box_path, basekey])

                count += 1

            for lbox in lost_boxes:
                ctx.obj.session['BOX_LIST'].remove(lbox)

            if lost_boxes:
                if not ctx.obj.session['BOX_LIST']:
                    ctx.obj.session['CURRENT_BOX'] = None
                    echo('No more Boxes, use [W0b]box-open[X].')
                else:
                    ctx.obj.session['CURRENT_BOX'] = 0
                    echo(
                        'Switched to the first Box. Set other '
                        'with [W0b]box-switch[X].'
                    )
            ctx.obj.session.commit()
            echo('')
