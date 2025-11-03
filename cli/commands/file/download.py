import click

from time import sleep
from pathlib import Path
from asyncio import get_event_loop, gather

from ..group import cli_group
from ..helpers import check_ctx
from ...tools.other import sync_async_gen
from ...tools.terminal import echo, ProgressBar
from ...tools.convert import filters_to_searchfilter
from ...config import tgbox


def _launch(path: str, locate: bool, size: int) -> None:
    """
    This function will call click.launch() after 5% of the
    target file (path) is downloaded
    """
    while (Path(path).stat().st_size+1) / size * 100 < 5:
        sleep(1)
    click.launch(path, locate=locate)

def _download_preview(
        dxbf, file_name, outfile, show,
        locate, downloads, force_remote
    ):
    """This function will save preview to outfile (if exists)"""

    if dxbf.preview == b'':
        # Drop the '.jpg' preview suffix string
        file_name = '.'.join(file_name.split('.')[:-1])

        if force_remote:
            echo(f'[Y0b]{file_name} doesn\'t have preview. Skipping.[X]')
        else:
            echo(
               f'[Y0b]{file_name} doesn\'t have '
                'preview. Try -r flag. Skipping.[X]')
        return

    with open(outfile,'wb') as f:
        f.write(dxbf.preview)

    if show or locate:
        click.launch(str(outfile), locate)
    echo(
        f'[W0b]{file_name}[X] preview downloaded '
        f'to [W0b]{str(downloads)}[X]')

def process_regular_download(
        ctx, offset: int, redownload: bool, max_workers: int,
        max_bytes: int, hide_name: bool, use_slow_download: bool,
        omit_hmac_check: bool, show: bool, locate: bool):
    """
    This generator processes regular (not Multipart) downloads.
    We push files into it via .send() method.
    """
    def _gather_helper(list_: list):
        r = tgbox.sync(gather(*list_, return_exceptions=True))

        exception = False
        for flo in r:
            if not flo:
                continue

            if isinstance(flo, Exception): # If download returned Exception
                error = f'{type(flo).__name__}: {flo}'
                echo(f'[R0b]x Can not download ID{drbf.id} due to "{error}"[X]')
                exception = True
            else:
                # We need to close each File-like Object to
                # ensure that all writes are final.
                flo.close()

        if exception:
            return
        list_.clear()

    loop = get_event_loop()
    current_workers = max_workers
    current_bytes = max_bytes

    to_gather_files = []
    try:
        while True:
            drbf, file_name, outfile = yield

            write_mode = 'wb'
            outfile_size = outfile.stat().st_size if outfile.exists() else 0

            if not redownload and outfile.exists():
                if outfile_size == drbf.size:
                    echo(f'[G0b]{str(outfile)} downloaded. Skipping...[X]')
                    continue

                if offset:
                    echo(
                       f'[Y0b]{str(outfile)} is partially downloaded and '
                        'you specified offset. This will corrupt file. Drop the '
                        'offset or remove file from your computer. Skipping...[X]')
                    continue

                if outfile_size % 524288: # Remove partially downloaded block
                    with open(outfile, 'ab') as f:
                        f.truncate(outfile_size - (outfile_size % 524288))

                # File is partially downloaded, so we need to fetch leftover bytes
                offset, write_mode = outfile.stat().st_size, 'ab+'

            if offset % 4096 or offset % 524288:
                echo('[R0b]Offset must be divisible by 4096 and by 524288.[X]')
                continue

            current_workers -= 1
            current_bytes -= drbf.file_size

            outpath = open(outfile, write_mode)

            p_file_name = '<Filename hidden>' if hide_name\
                else file_name

            blocks_downloaded = 0 if not offset else offset // 524288

            download_coroutine = drbf.download(
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
                to_gather_files.append(loop.run_in_executor(
                    None, lambda: _launch(outpath.name, locate, drbf.size))
                )

            check = (current_workers <= 0, current_bytes <= 0)
            if any(check) and to_gather_files:
                _gather_helper(to_gather_files)
                current_workers = max_workers
                current_bytes = max_bytes
    except GeneratorExit:
        if to_gather_files:
            _gather_helper(to_gather_files)


def process_multipart_download(
        ctx, multipart_offset: int, redownload: bool,
        hide_name: bool, use_slow_download: bool,
        omit_hmac_check: bool, show: bool, locate: bool):
    """
    This generator processes Multipart downloads.
    We push files into it via .send() method.
    """
    # We will construct (format) dxbf only for first
    # multipart file part and skip its parts. Here
    # we will cache ids to omit
    multipart_ignore = set()
    loop = get_event_loop()

    while True:
        drbf, file_name, outfile = yield

        if drbf.id in multipart_ignore:
            multipart_ignore.remove(drbf.id)
            continue

        sf = tgbox.tools.SearchFilter(file_name=file_name,
            scope=str(drbf.file_path), cattrs={
                '__mp_part': b'',
                '__mp_previous': b'',
                '__mp_total': b''
            }
        )
        parts = []
        for i, dlbf in enumerate(sync_async_gen(ctx.obj.dlb.search_file(sf))):
            if i > 0: # skip first id as we process it now
                multipart_ignore.add(dlbf.id)
            parts.append(dlbf)

        parts.sort(key=lambda d: d.cattrs['__mp_part'])

        total = tgbox.tools.bytes_to_int(parts[0].cattrs['__mp_total'])
        if len(parts) != total:
            for dlbf in parts:
                if dlbf.id in multipart_ignore:
                    multipart_ignore.remove(dlbf.id)
            echo(
                f'[R0b]x Multipart file "{file_name}" (ID{drbf.id}) has '
                f'incorrect amount of parts! Expected {total}, got {len(parts)}. '
                 'Download is impossible! You can download each part '
                 'separately with --split-multipart flag.[X]')
            continue

        if multipart_offset and multipart_offset+1 > len(parts):
            echo(
               f'[R0b]{len(parts)} parts available on ID{parts[0].id}, '
               f'but your offset is {multipart_offset}.[X]')
            continue

        total_size = 0
        for dlbf in parts:
            total_size += dlbf.size

        outfile_size = outfile.stat().st_size if outfile.exists() else 0

        if not redownload and outfile.exists():
            if outfile_size == total_size:
                echo(f'[G0b]{str(outfile)} downloaded. Skipping...[X]')
                continue

            if multipart_offset:
                echo(
                   f'[Y0b]{str(outfile)} is partially downloaded and '
                    'you specified offset. This will corrupt file. Drop the '
                    'offset or remove file from your computer. Skipping...[X]')
                continue

            csize = 0
            for multipart_offset, dlbf in enumerate(parts):
                if (csize + dlbf.size) == outfile_size:
                    multipart_offset += 1
                    break

                if (csize + dlbf.size) > outfile_size:
                    with open(outfile, 'ab') as f:
                        f.truncate(csize)
                    break

                csize += dlbf.size

        outpath = open(outfile, 'ab+')

        if show or locate:
            launch_coro = loop.run_in_executor(None,
                lambda: _launch(outpath.name, locate, total_size)
            )
            loop.create_task(launch_coro)

        for dlbf in parts[multipart_offset:]:
            # File name that will be displayed on Progressbar
            p_file_name = '<Filename hidden>' if hide_name else dlbf.file_name
            drbf = tgbox.sync(ctx.obj.drb.get_file(dlbf.id))

            download_coroutine = drbf.download(
                outfile = outpath,
                progress_callback = ProgressBar(
                    ctx.obj.enlighten_manager,
                    p_file_name, 0).update,

                use_slow_download = use_slow_download,
                omit_hmac_check = omit_hmac_check
            )
            tgbox.sync(download_coroutine)

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
    help=(
        'Download decrypted file from specified offset. This '
        'offset does NOT work for Multipart files.'
    )
)
@click.option(
    '--multipart-offset', type=int,
    help=(
        'Download decrypted Multipart file from specified offset. Please note '
        'that offset here is number of part that you want to download, NOT '
        'actual byte offset. For example, if you have Multipart file of 5 '
        'parts, by specifying --multipart-offset=2 you will download from '
        'THIRD part to FIVE part, skipping First (0) and Second (1).'
    )
)
@click.option(
    '--split-multipart', '-m', is_flag=True,
    help='If specified, will download all Multipart file parts separately',
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
        offset, multipart_offset, split_multipart,
        omit_hmac_check, max_workers, max_bytes):
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
        return
    except KeyError as e: # Unknown filters
        echo(f'[R0b]Filter "{e.args[0]}" doesn\'t exists[X]')
        return

    box = ctx.obj.drb if force_remote else ctx.obj.dlb
    to_download = box.search_file(sf)

    process_r_download = process_regular_download(
        ctx, offset, redownload, max_workers, max_bytes, hide_name,
        use_slow_download, omit_hmac_check, show, locate
    )
    process_m_download = process_multipart_download(
        ctx, multipart_offset, redownload, hide_name,
        use_slow_download, omit_hmac_check, show, locate
    )
    next(process_r_download) # Init Generator
    next(process_m_download) # Init Generator

    for dxbf in sync_async_gen(to_download):
        if not split_multipart and (dxbf.cattrs and '__mp_part' in dxbf.cattrs):
            multipart_file = True
        else:
            multipart_file = False

        if hide_name:
            file_name = tgbox.tools.prbg(16).hex()
            file_name += Path(dxbf.file_name).suffix
        else:
            if multipart_file:
                file_name = '-'.join(dxbf.file_name.split('-')[:-1])
            else:
                file_name = dxbf.file_name

        file_name = file_name.lstrip('/\\')
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
                file_path = tgbox.tools.make_safe_file_path(
                    tgbox.defaults.DEF_UNK_FOLDER)
            else:
                file_path = tgbox.tools.make_safe_file_path(dxbf.file_path)

            outfile = downloads / file_path / file_name

        outfile.parent.mkdir(exist_ok=True, parents=True)

        if preview:
            _download_preview(
                dxbf, file_name, outfile, show,
                locate, downloads, force_remote)
            continue

        if not force_remote: # box is DecryptedLocalBox
            drbf = tgbox.sync(ctx.obj.drb.get_file(dxbf.id))

            if not drbf:
                echo(
                    f'[Y0b]There is no file with ID={dxbf.id} in '
                     'RemoteBox. Skipping.[X]')
                continue
            dxbf = drbf

        if multipart_file and not split_multipart:
            process_m_download.send((dxbf, file_name, outfile))
        else:
            process_r_download.send((dxbf, file_name, outfile))

    process_r_download.close()
    process_m_download.close()
