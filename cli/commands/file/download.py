import click

from time import sleep
from pathlib import Path
from asyncio import get_event_loop, gather

from ..group import cli_group
from ..helpers import check_ctx
from ...tools.terminal import echo, ProgressBar
from ...tools.convert import filters_to_searchfilter
from ...config import tgbox


@cli_group.command()
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
    help='Download path. ./DownloadsTGBOX by default',
    type=click.Path(writable=True, path_type=Path)
)
@click.option(
    '--ignore-file-path', is_flag=True,
    help='If specified, will NOT make folders from file path on download'
)
@click.option(
    '--force-remote','-r', is_flag=True,
    help='If specified, will fetch file data from RemoteBox'
)
@click.option(
    '--redownload', is_flag=True,
    help='If specified, will redownload already cached files'
)
@click.option(
    '--use-slow-download', is_flag=True,
    help='If specified, will use slow, non-parallel download'
)
@click.option(
    '--offset', default=0,
    help='Download decrypted file from specified offset'
)
@click.option(
    '--omit-hmac-check', is_flag=True,
    help='If specified, will omit HMAC check on download'
)
@click.option(
    '--max-workers', default=10, type=click.IntRange(1,50),
    help='Max amount of files downloaded at the same time, default=10',
)
@click.option(
    '--max-bytes', default=200000000,
    type=click.IntRange(1000000, 1000000000),
    help='Max amount of bytes downloaded at the same time, default=200000000',
)
@click.pass_context
def file_download(
        ctx, filters, preview, show, locate,
        hide_name, hide_folder, out, ignore_file_path,
        force_remote, redownload, use_slow_download,
        offset, omit_hmac_check, max_workers, max_bytes):
    """Download files by selected filters

    \b
    Available filters:\b
        scope: Define a path as search scope
               -----------------------------
               The *scope* is an absolute directory in which
               we will search your file by other filters. By
               default, the tgbox.api.utils.search_generator
               will search over the entire LocalBox. This can
               be slow if you're have too many files.
               \b
               Example: let's imagine that You're a Linux user which
               share it's Box with the Windows user. In this case,
               Your LocalBox will contain a path parts on the
               '/' (Linux) and 'C:\\' (Windows) roots. If You
               know that some file was uploaded by Your friend,
               then You can specify a scope='C:\\' to ignore
               all files uploaded from the Linux machine. This
               will significantly fasten the search process,
               because almost all filters require to select
               row from the LocalBox DB, decrypt Metadata and
               compare its values with ones from SearchFilter.
               \b
               !: The scope will be ignored on RemoteBox search.
               !: The min_id & max_id will be ignored if scope used.
        \b
        id integer: File’s ID
        mime str: File MIME type
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
        min_size integer/str: File Size should be > min_size
        max_size integer/str: File Size should be < max_size
        +
        min_size & max_size can be also specified as string,
            i.e "1GB" (one gigabyte), "122.45KB" or "700B"
        \b
        min_time integer/float/str: Upload Time should be > min_time
        max_time integer/float/str: Upload Time should be < max_time
        +
        min_time & max_time can be also specified as string,
            i.e "22/02/22, 22:22:22" or "22/02/22"
               ("%d/%m/%y, %H:%M:%S" or "%d/%m/%y")
        \b
        minor_version int: File minor version
        imported bool: Yield only imported files
        re       bool: Regex search for every str filter
        \b
        non_recursive_scope bool: Ignore scope subdirectories
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
        check_ctx(ctx, dlb=True)
    else:
        check_ctx(ctx, dlb=True, drb=True)
    try:
        sf = filters_to_searchfilter(filters)
    except IndexError: # Incorrect filters format
        echo('[R0b]Incorrect filters! Make sure to use format filter=value[X]')
    except KeyError as e: # Unknown filters
        echo(f'[R0b]Filter "{e.args[0]}" doesn\'t exists[X]')
    else:
        current_workers = max_workers
        current_bytes = max_bytes

        box = ctx.obj.drb if force_remote else ctx.obj.dlb
        to_download = box.search_file(sf)

        while True:
            try:
                to_gather_files = []
                while all((current_workers > 0, current_bytes > 0)):
                    dxbf = tgbox.sync(tgbox.tools.anext(to_download))

                    if hide_name:
                        file_name = tgbox.tools.prbg(16).hex()
                        file_name += Path(dxbf.file_name).suffix
                    else:
                        file_name = dxbf.file_name

                    file_name = file_name.lstrip('/')
                    file_name = file_name.lstrip('\\')

                    file_name = file_name if not preview else file_name + '.jpg'

                    if not out:
                        downloads = Path(dxbf.defaults.DOWNLOAD_PATH)
                        downloads = downloads / ('Previews' if preview else 'Files')
                    else:
                        downloads = out

                    downloads.mkdir(parents=True, exist_ok=True)

                    if ignore_file_path:
                        outfile = downloads / file_name
                    else:
                        if hide_folder:
                            file_path = tgbox.tools.make_safe_file_path(tgbox.defaults.DEF_UNK_FOLDER)
                        else:
                            file_path = tgbox.tools.make_safe_file_path(dxbf.file_path)

                        outfile = downloads / file_path / file_name

                    outfile.parent.mkdir(exist_ok=True, parents=True)

                    preview_bytes = dxbf.preview if preview else None

                    if preview_bytes is not None:
                        if preview_bytes == b'':
                            # Drop the '.jpg' preview suffix string
                            file_name = '.'.join(file_name.split('.')[:-1])

                            if force_remote:
                                echo(f'[Y0b]{file_name} doesn\'t have preview. Skipping.[X]')
                            else:
                                echo(
                                    f'[Y0b]{file_name} doesn\'t have preview. Try '
                                     '-r flag. Skipping.[X]'
                                )
                            continue

                        with open(outfile,'wb') as f:
                            f.write(preview_bytes)

                        if show or locate:
                            click.launch(str(outfile), locate)

                        echo(
                            f'[W0b]{file_name}[X] preview downloaded '
                            f'to [W0b]{str(downloads)}[X]')
                    else:
                        if not force_remote: # box is DecryptedLocalBox
                            drbf = tgbox.sync(ctx.obj.drb.get_file(dxbf.id))

                            if not drbf:
                                echo(
                                    f'[Y0b]There is no file with ID={dxbf.id} in '
                                     'RemoteBox. Skipping.[X]'
                                )
                                continue
                            dxbf = drbf

                        write_mode = 'wb'
                        outfile_size = outfile.stat().st_size if outfile.exists() else 0

                        if not redownload and outfile.exists():
                            if outfile_size == dxbf.size:
                                echo(f'[G0b]{str(outfile)} downloaded. Skipping...[X]')
                                continue
                            else:
                                if offset:
                                    echo(
                                       f'[Y0b]{str(outfile)} is partially downloaded and '
                                        'you specified offset. This will corrupt file. Drop the '
                                        'offset or remove file from your computer. Skipping...[X]'
                                    )
                                    continue

                                if outfile_size % 524288: # Remove partially downloaded block
                                    with open(outfile, 'ab') as f:
                                        f.truncate(outfile_size - (outfile_size % 524288))

                                # File is partially downloaded, so we need to fetch left bytes
                                offset, write_mode = outfile.stat().st_size, 'ab+'

                        if offset % 4096 or offset % 524288:
                            echo('[R0b]Offset must be divisible by 4096 and by 524288.[X]')
                            continue

                        current_workers -= 1
                        current_bytes -= dxbf.file_size

                        outpath = open(outfile, write_mode)

                        p_file_name = '<Filename hidden>' if hide_name\
                            else dxbf.file_name

                        blocks_downloaded = 0 if not offset else offset // 524288

                        download_coroutine = dxbf.download(
                            outfile = outpath,
                            progress_callback = ProgressBar(
                                ctx.obj.enlighten_manager,
                                p_file_name, blocks_downloaded).update,

                            offset = offset,
                            use_slow_download = use_slow_download,
                            omit_hmac_check = omit_hmac_check
                        )
                        to_gather_files.append(download_coroutine)

                        if write_mode == 'ab+': # Partially downloaded write
                            offset = 0 # Reset offset for the next files

                        if show or locate:
                            def _launch(path: str, locate: bool, size: int) -> None:
                                while (Path(path).stat().st_size+1) / size * 100 < 5:
                                    sleep(1)
                                click.launch(path, locate=locate)

                            loop = get_event_loop()

                            to_gather_files.append(loop.run_in_executor(
                                None, lambda: _launch(outpath.name, locate, dxbf.size))
                            )
                if to_gather_files:
                    tgbox.sync(gather(*to_gather_files))

                current_workers = max_workers
                current_bytes = max_bytes

            except StopAsyncIteration:
                break

        if to_gather_files: # If any files left
            tgbox.sync(gather(*to_gather_files))
