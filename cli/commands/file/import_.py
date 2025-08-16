import click

from asyncio import gather
from pathlib import Path

from ..group import cli_group
from ..helpers import ctx_require
from ...tools.terminal import echo
from ...tools.other import format_dxbf, sync_async_gen
from ...config import tgbox


@cli_group.command()
@click.option(
    '--key', '-k', required=True,
    help='File\'s ShareKey/ImportKey/FileKey'
)
@click.option(
    '--id', required=True, type=int,
    help='ID of file to import'
)
@click.option(
    '--propagate', '-p', is_flag=True,
    help='If specified, will import all files up to first error'
)
@click.option(
    '--file-path', '-f', type=Path,
    help='Imported file\'s path.'
)
@ctx_require(dlb=True, drb=True)
def file_import(ctx, key, id, propagate, file_path):
    """Import RemoteBox file to your LocalBox

    Use --propagate option to auto import a
    bunch of files (if you have a ShareKey of
    a DirectoryKey).
    """
    erbf = tgbox.sync(ctx.obj.drb.get_file(
        id, return_imported_as_erbf=True))

    if not erbf:
        echo(f'[R0b]There is no file in RemoteBox by ID {id}[X]')

    elif isinstance(erbf, tgbox.api.remote.DecryptedRemoteBoxFile):
        echo(f'[R0b]File ID{id} is already decrypted. Did you mistyped ID?[X]')
    else:
        try:
            key = tgbox.keys.Key.decode(key)
        except tgbox.errors.IncorrectKey:
            echo('[R0b]Specified Key is invalid[X]')
            return

        if isinstance(key, tgbox.keys.ShareKey):
            key = tgbox.keys.make_importkey(
                key=ctx.obj.dlb._mainkey,
                sharekey=key,
                salt=erbf.file_salt
            )

        async def _import_wrap(erbf):
            try:
                drbf = await erbf.decrypt(key)
            except tgbox.errors.AESError:
                return # Probably not a file of Directory

            await ctx.obj.dlb.import_file(drbf, file_path)
            echo(format_dxbf(drbf), nl=False); return drbf

        echo('\n[Y0b]Searching for files to import[X]...')

        # Import first found EncryptedRemoteBoxFile
        if not tgbox.sync(_import_wrap(erbf)):
            echo('[R0b]Can not decrypt. Specified Key is invalid[X]')
            return

        if propagate:
            IMPORT_STACK, IMPORT_WHEN = [], 100

            iter_over = ctx.obj.drb.files(
                offset_id=erbf.id, reverse=True,
                return_imported_as_erbf=True
            )
            for erbf in sync_async_gen(iter_over):
                if len(IMPORT_STACK) == IMPORT_WHEN:
                    tgbox.sync(gather(*IMPORT_STACK))
                    IMPORT_STACK.clear()

                if type(erbf) is tgbox.api.DecryptedRemoteBoxFile:
                    break # All files from shared Dir was imported

                IMPORT_STACK.append(_import_wrap(erbf))

            if IMPORT_STACK: # If any files left
                tgbox.sync(gather(*IMPORT_STACK))
            echo('')
