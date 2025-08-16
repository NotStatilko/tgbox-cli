import click

from datetime import datetime

from ..group import cli_group
from ..helpers import ctx_require
from ...tools.terminal import echo, colorize
from ...tools.convert import format_bytes
from ...tools.strings import break_string
from ...tools.other import sync_async_gen
from ...config import tgbox


@cli_group.command()
@click.option(
    '--bytesize-total', is_flag=True,
    help='Will compute a total size of all uploaded to Box files'
)
@ctx_require(dlb=True, drb=True)
def box_info(ctx, bytesize_total):
    """Show information about current Box"""

    if bytesize_total:
        total_bytes, current_file_count = 0, 0
        total_files = tgbox.sync(ctx.obj.dlb.get_files_total())

        echo('')
        for dlbf in sync_async_gen(ctx.obj.dlb.files()):
            total_bytes += dlbf.size
            current_file_count += 1

            total_formatted = f'[B0b]{format_bytes(total_bytes)}[X]'

            if current_file_count == total_files:
                current_file = f'[G0b]{current_file_count}[X]'
            else:
                current_file = f'[Y0b]{current_file_count}[X]'

            echo_text = (
                f'@ Total [W0b]Box[X] size is {total_formatted}'
                f'({total_bytes}) [{current_file}/[G0b]{total_files}[X]]   \r'
            )
            echo(echo_text, nl=False)

        echo('\n')
    else:
        box_name = tgbox.sync(ctx.obj.drb.get_box_name())
        box_name = f'[W0b]{box_name}[X]'

        box_id = f'[W0b]id{ctx.obj.drb.box_channel_id}[X]'

        total_local = tgbox.sync(ctx.obj.dlb.get_files_total())
        total_remote = tgbox.sync(ctx.obj.drb.get_files_total())

        if total_local != total_remote:
            status = f'[R0b]Out of sync! ({total_local}L/{total_remote}R)[X]'
        else:
            status = '[G0b]Seems synchronized[X]'

        total_local = f'[W0b]{total_local}[X]'
        total_remote = f'[W0b]{total_remote}[X]'

        if ctx.obj.drb.box_channel.username:
            public_link = f'[W0b]@{ctx.obj.drb.box_channel.username}[X]'
        else:
            public_link = '[R0b]<Not presented>[X]'

        if ctx.obj.drb.box_channel.restricted:
            restricted = f'[R0b]yes: {ctx.obj.drb.box_channel.restriction_reason}[X]'
        else:
            restricted = '[W0b]no[X]'

        box_path = f'[W0b]{ctx.obj.dlb.tgbox_db.db_path.name}[X]'

        local_box_date = datetime.fromtimestamp(ctx.obj.dlb.box_cr_time).strftime('%d/%m/%Y')
        local_date_created = f'[W0b]{local_box_date}[X]'

        remote_box_date = tgbox.sync(ctx.obj.drb.tc.get_messages(
            ctx.obj.drb.box_channel, ids=1)
        )
        remote_box_date = remote_box_date.date.strftime('%d/%m/%Y')
        remote_date_created = f'[W0b]{remote_box_date}[X]'

        box_description = tgbox.sync(ctx.obj.drb.get_box_description())
        if box_description:
            box_description = break_string(box_description, 15)
            box_description = colorize(f'[Y0b]{box_description}[X]')
        else:
            box_description = colorize('[R0b]<Not presented>[X]')

        rights_interested = {
            'post_messages' : 'Upload files',
            'delete_messages' : 'Remove files',
            'edit_messages' : 'Edit files',
            'invite_users' : 'Invite users',
            'add_admins': 'Add admins'
        }
        if ctx.obj.drb.box_channel.admin_rights:
            rights = ' (+) [G0b]Fast sync files[X]\n'
        else:
            rights = ' (-) [R0b]Fast sync files[X]\n'

        rights += ' (+) [G0b]Download files[X]\n'

        for k,v in rights_interested.items():
            if ctx.obj.drb.box_channel.admin_rights and\
                getattr(ctx.obj.drb.box_channel.admin_rights, k):
                    right_status = '(+)' # User has such right
                    right = f'[G0b]{v}[X]'
            else:
                right_status = '(-)' # User hasn't such right
                right = f'[R0b]{v}[X]'

            rights += f' {right_status} {right}\n'

        echo(
            '\n ====== Current Box (remote) ======\n\n'

            f'| Box name: {box_name}\n'
            f'| Description: [Y0b]{box_description}[X]\n'
            f'| Public link: {public_link}\n'
            f'| ID: {box_id}\no\n'
            f'| Date created: {remote_date_created}\n'
            f'| Files total: {total_remote}\n'
            f'| Is restricted: {restricted}\no\n'
            f'| Your rights: \n{rights}\n'

            ' ====== Current Box (local) =======\n\n'

            f'| Box DB: {box_path}\n'
            f'| Date created: {local_date_created}\n'
            f'| Files total: {total_local}\n'

            '\n :::::::::::::::::::::::::::::::::\n\n'

            f'| Status: {status}\n'

            '\n =================================\n'
        )
