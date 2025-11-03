import click

from re import search as re_search
from os.path import getsize
from asyncio import gather
from copy import deepcopy
from pathlib import Path
from os import SEEK_SET
from math import ceil
from io import IOBase

from filetype import guess as filetype_guess

from ...tools.convert import (
    filters_to_searchfilter, parse_str_cattrs,
    format_bytes
)
from ..group import cli_group
from ..helpers import ctx_require
from ...tools.other import sync_async_gen
from ...tools.terminal import echo, ProgressBar
from ...config import tgbox


class LimitedReader:
    """
    This class is designed to provide limited, offset
    read() for the Tgbox .push_file() method. Here
    we can specify start and stop position to read
    from.
    """
    def __init__(
            self, file_path: str, start_pos: int,
            stop_pos: int, actual_size: int):

        self._file_path = file_path
        self._start_pos = start_pos
        self._stop_pos = stop_pos
        self._actual_size = actual_size

        self._flo = open(file_path,'rb')
        self._flo.seek(start_pos, 0)

        self._available = stop_pos - start_pos

    def __del__(self):
        self.close()

    @property
    def size(self) -> int:
        return self._actual_size

    @property
    def name(self) -> str:
        return self._file_path

    def read(self, size: int=-1):
        if self._available <= 0:
            return b''

        if size < 0:
            amount = self._available
            self._available = 0
        else:
            if self._available < size:
                amount = self._available
            else:
                amount = size

        self._available -= amount
        return self._flo.read(amount)

    def seek(self, cookie: int, whence: int=SEEK_SET, /):
        """
        Dead simple File-like object (IOBase) .seek() analogue.
        Please note that here we support only SEEK_SET (0) as
        whence, any other values will throw error. We don't
        need complex .seek() here, as it's only for the tgbox
        push_file() coroutine.
        """
        if whence != SEEK_SET:
            raise ValueError('This dumb seek() supports only SEEK_SET (0)')

        sp_p_cookie = self._start_pos + cookie

        if sp_p_cookie < self._start_pos:
            start_pos = self._start_pos

        elif sp_p_cookie > self._stop_pos:
            start_pos = self._stop_pos
        else:
            start_pos = self._start_pos + cookie

        self._available = self._stop_pos - self._start_pos
        return self._flo.seek(start_pos, whence)

    def close(self):
        self._flo.close()


def _check_filters(filters, current_path: Path):
    """
    This function will check filters against given File
    (under current_path)
    """
    # Will use Regex Search if 're' is included in Filters, "In" otherwise.
    in_func = re_search if filters.in_filters['re'] else lambda p,s: p in s
    INCLUDE, EXCLUDE = 0, 1

    for inex, filter in enumerate((filters.in_filters, filters.ex_filters)):
        try:
            if filter['min_time'] or filter['max_time']:
                cp_st_mtime = current_path.stat().st_mtime # File Modification Time

            if filter['min_size'] or filter['max_size']:
                cp_st_size = current_path.stat().st_size # File Size

            if filter['mime']:
                file_mime = filetype_guess(current_path) # File MIME Type
                file_mime = file_mime.mime if file_mime else ''

            if filter['file_path']:
                abs_path = str(current_path.absolute()) # File absolute Path

        except (FileNotFoundError, PermissionError, OSError) as e:
            echo(f'[R0b]x {e}. Skipping...[X]')
            return

        for filter_file_path in filter['file_path']:
            if in_func(filter_file_path, abs_path): # pylint: disable=E0606
                if inex == EXCLUDE:
                    return
                break
        else:
            if filter['file_path']:
                if inex == INCLUDE:
                    return

        for file_name in filter['file_name']:
            if in_func(file_name, current_path.name):
                if inex == EXCLUDE:
                    return
                break
        else:
            if filter['file_name'] and inex == INCLUDE:
                return

        for mime in filter['mime']:
            if in_func(mime, file_mime):
                if inex == EXCLUDE:
                    return
                break
        else:
            if filter['mime'] and inex == INCLUDE:
                return

        if filter['min_time']:
            if cp_st_mtime < filter['min_time'][-1]: # pylint: disable=E0606
                if inex == INCLUDE:
                    return

            elif cp_st_mtime >= filter['min_time'][-1]:
                if inex == EXCLUDE:
                    return

        if filter['max_time']:
            if cp_st_mtime > filter['max_time'][-1]:
                if inex == INCLUDE:
                    return

            elif cp_st_mtime <= filter['max_time'][-1]:
                if inex == EXCLUDE:
                    return

        if filter['min_size']:
            if cp_st_size < filter['min_size'][-1]: # pylint: disable=E0606
                if inex == INCLUDE:
                    return

            elif cp_st_size >= filter['min_size'][-1]:
                if inex == EXCLUDE:
                    return

        if filter['max_size']:
            if cp_st_size > filter['max_size'][-1]:
                if inex == INCLUDE:
                    return

            elif cp_st_size <= filter['max_size'][-1]:
                if inex == EXCLUDE:
                    return

    return True # File matches against the filters

async def _get_push_action(
        ctx, file, file_path, cattrs, force_update,
        no_update, no_thumb
    ):
    """Helper-function for the .push_file() coroutine"""

    fingerprint = tgbox.tools.make_file_fingerprint(
        mainkey = ctx.obj.dlb.mainkey,
        file_path = str(file_path)
    )
    dlbf = await ctx.obj.dlb.get_file(fingerprint=fingerprint)

    if isinstance(file, LimitedReader):
        file_size = file.size
    else:
        file_size = getsize(file)

    # Standard file upload if dlbf is not exists (from scratch)
    if not dlbf and not force_update:
        file_action = (ctx.obj.drb.push_file, {})

    # File re-uploading (or updating) if file size differ
    elif force_update or not no_update and dlbf and dlbf.size != file_size:
        if not dlbf: # Wasn't uploaded before
            file_action = (ctx.obj.drb.push_file, {})
        else:
            drbf = await ctx.obj.drb.get_file(dlbf.id)
            file_action = (ctx.obj.drb.update_file, {'rbf': drbf})
    else:
        # Ignore upload if file exists and wasn't changed
        name = file.name if isinstance(file, IOBase) else file
        echo(f'[Y0b]| File {name} is already uploaded. Skipping...[X]')
        return

    if cattrs is None: # CAttrs not specified
        cattrs = cattrs or dlbf.cattrs if dlbf else None

    elif not cattrs: # Can be "", then remove CAttrs
        cattrs = None
    else:
        if dlbf and dlbf.cattrs: # Combine if dlbf has CAttrs
            dlbf.cattrs.update(cattrs)
            cattrs = dlbf.cattrs

    if not isinstance(file, (IOBase, LimitedReader)):
        file = open(file,'rb')
    try:
        pf = await ctx.obj.dlb.prepare_file(
            file = file,
            file_path = file_path,
            file_size = file_size,
            cattrs = cattrs,
            make_preview = (not no_thumb),
            skip_fingerprint_check = True
        )
    except tgbox.errors.LimitExceeded as e:
        echo(f'[Y0b]{file}: {e} Skipping...[X]')
        return

    except PermissionError:
        echo(f'[R0b]{file} is not readable! Skipping...[X]')
        return

    progressbar = ProgressBar(ctx.obj.enlighten_manager, file_path.name)

    file_action[1]['pf'] = pf
    file_action[1]['progress_callback'] = progressbar.update

    return file_action

async def _push_wrapper(
        ctx, file, file_path, cattrs, force_update,
        no_update, no_thumb, use_slow_upload):
    """
    This function selects correct push action (either
    updates file or uploads it) and wraps it.
    """
    file_action = await _get_push_action(
        ctx=ctx, file=file,
        file_path=file_path,
        cattrs=cattrs,
        force_update=force_update,
        no_update=no_update,
        no_thumb=no_thumb
    )
    if file_action is None:
        return

    return await file_action[0](**file_action[1],
        use_slow_upload=use_slow_upload)

@cli_group.command()
@click.argument(
    'target', nargs=-1, required=False, default=None,
    type=click.Path(readable=None, dir_okay=True, path_type=Path)
)
@click.option(
    '--file-path', '-f', type=Path,
    help='Change file path of target in Box. System\'s if not specified'
)
@click.option(
    '--flat-path', is_flag=True,
    help = (
        'If specified alongside with --file-path, will ignore all TARGET '
        'sub-directories, uploading all files directly under --file-path'
    )
)
@click.option(
    '--cattrs', '-c',
    help='File\'s CustomAttributes. Format: "key: value | key: value"'
)
@click.option(
    '--no-update', is_flag=True,
    help='If specified, will NOT re-upload file if it was changed (in size)'
)
@click.option(
    '--force-update', is_flag=True,
    help='If specified, will force to re-upload every target file'
)
@click.option(
    '--use-slow-upload', is_flag=True,
    help='If specified, will use slow, non-parallel upload'
)
@click.option(
    '--no-thumb', is_flag=True,
    help='If specified, will not add thumbnail'
)
@click.option(
    '--calculate', is_flag=True,
    help = (
        'If specified, will calculate and show a total '
        'bytesize of targets (without uploading)')
)
@click.option(
    '--max-workers', default=5, type=click.IntRange(1,50),
    help='Max amount of files we will upload at the same time, default=10',
)
@click.option(
    '--max-bytes', default=200000000,
    type=click.IntRange(1000000, 1000000000),
    help='Max amount of bytes we will upload at the same time, default=200000000',
)
@click.option(
    '--multi-file-size',
    type = click.IntRange(
        32_000_000, # V 32MB here is reserved for possible Metadata
        tgbox.defaults.UploadLimits.PREMIUM - 32_000_000
    ),
    help = (
        'Max amount of bytes that we can upload as single file. If file size is > '
        '--multi-file-size, will split one file by {--multi-file-size} parts and '
        'upload them separately')
)
@ctx_require(dlb=True, drb=True)
def file_upload(
        ctx, target, file_path, flat_path, cattrs,
        no_update, force_update, use_slow_upload,
        no_thumb, calculate, max_workers, max_bytes,
        multi_file_size):
    """
    Upload TARGET by specified filters to the Box

    \b
    TARGET can be a path to File or a Directory.
    If TARGET is a Directory, -- this command
    will upload to Box all files from dir.
    \b
    If file was already uploaded but changed (in size)
    and --no-update is NOT specified, -- will re-upload.
    \b
    Available filters:\b
        file_path str: File path
        file_name str: File name
        mime str: File MIME type
        \b
        min_size integer/str: File Size should be > min_size
        max_size integer/str: File Size should be < max_size
        +
        min_size & max_size can be also specified as string,
            i.e "1GB" (one gigabyte), "122.45KB" or "700B"
        \b
        min_time integer/float/str: Modification Time should be > min_time
        max_time integer/float/str: Modification Time should be < max_time
        +
        min_time & max_time can be also specified as string,
            i.e "22/02/22, 22:22:22" or "22/02/22"
        \b
        re bool: Regex search for every str filter
    \b
    Please note that Filters should be placed after TARGET!
    \b
    You can also use special flags to specify
    that filters is for include or exclude search:
    \b
    Example:\b
        # An ordinary upload process (upload Music & Documents folders)
        tgbox-cli file-upload /home/user/Music /home/user/Documents
        \b
        # Include flag (upload only .DOC from Documents, ignore unmatched)
        tgbox-cli file-upload /home/non/Documents +i file_name='.doc'
        \b
        # Exclude flag (ignore .DOC, upload every single file from Documents)
        tgbox-cli file-upload /home/non/Documents +e file_name='.doc'
        \b
        You can use both, the ++include and ++exclude (+i, +e)
        in one command, but make sure to place them after TARGET!
    """
    if not target:
        target = click.prompt('Please enter target to upload')
        target = (Path(target),)
    else:
        target = tuple((str(p) for p in target))

    if '+i' in target:
        filters_pos_i = target.index('+i')

    elif '++include' in target:
        filters_pos_i = target.index('++include')
    else:
        filters_pos_i = None

    if '+e' in target:
        filters_pos_e = target.index('+e')

    elif '++exclude' in target:
        filters_pos_e = target.index('++exclude')
    else:
        filters_pos_e = None

    if all((filters_pos_i, filters_pos_e)):
        filters_pos = min(filters_pos_i, filters_pos_e)
    else:
        filters_pos = (filters_pos_i or filters_pos_e)

    if filters_pos:
        filters = filters_to_searchfilter(target[filters_pos:])
        target = target[:filters_pos]
    else:
        filters = None

    # Remove all duplicates present in Target (if any)
    target = tuple(set(Path(p).resolve() for p in target))

    current_workers = max_workers
    current_bytes = max_bytes

    if cattrs is not None and not cattrs:
        parsed_cattrs = {}

    elif cattrs is not None:
        parsed_cattrs = parse_str_cattrs(cattrs)
    else:
        parsed_cattrs = None

                               # We can omit request to drb if --calculate
    if multi_file_size is None and not calculate:
        has_premium = tgbox.sync(ctx.obj.drb.tc.get_me()).premium
        if has_premium:
            multi_file_size = tgbox.defaults.UploadLimits.PREMIUM
        else:
            multi_file_size = tgbox.defaults.UploadLimits.DEFAULT

        multi_file_size -= 32_000_000 # Subtract 32MB to leave space
                                      # for possible Metadata

    for path in target:
        if not path.exists():
            echo(f'[R0b]@ Target "{path}" doesn\'t exists! Skipping...[X]')
            continue

        if path.is_dir():
            try:
                next(path.iterdir())
            except (FileNotFoundError, PermissionError, OSError):
                echo(f'[R0b]@ Target "{path}" is not readable! Skipping...[X]')
                continue

        if path.is_dir():
            iter_over = path.rglob('*')
        else:
            iter_over = (path,)

        echo(f'[C0b]@ Working on[X] [W0b]{str(path.absolute())}[X] ...')

        # Will be used if --calculate specified
        target_files, target_files_bs = 0, 0

        to_upload = []
        for current_path in iter_over:
            try:
                if current_path.is_dir():
                    echo(f'[C0b]@ Working on[X] [W0b]{str(current_path)}[X] ...')
                    continue
                else:
                    open(current_path,'rb') # check if we can read file
            except (FileNotFoundError, PermissionError, OSError) as e:
                if current_path.is_dir():
                    echo(f'[R0b]x Not Working on. {e}. Skipping...[X]')
                else:
                    echo(f'[R0b]x {current_path} is not readable. Skipping...[X]')
                continue

            # --calculate ------------------------------------------------- #
            if calculate:
                if not current_path.exists():
                    echo(
                       f'[R0b]x Target "{current_path}" doesn\'t '
                        'exists! Skipping...[X]')
                    continue

                cp_st_size = current_path.stat().st_size

                target_files += 1; target_files_bs += cp_st_size
                target_files_bs_f = format_bytes(target_files_bs)

                echo_text = (
                    f'@ Total [W0b]targets found [X]([Y0b]{target_files}[X]) '
                    f'size is [B0b]{target_files_bs_f}[X]({target_files_bs})   \r'
                )
                echo(echo_text, nl=False)
                echo(' ' * 60 + '\r', nl=False)
                continue

            if filters and not _check_filters(filters, current_path):
                echo(
                    f'[Y0b]x Target "{current_path}" is '
                    'ignored by filters! Skipping...[X]'
                )
                continue
            # ------------------------------------------------------------- #

            if not file_path:
                remote_path = current_path.resolve()
            else:
                if flat_path:
                    remote_path = Path(file_path) / current_path.name
                else:
                    r = str(current_path.resolve().parent)
                    r = r.removeprefix(str(path)).lstrip('/\\')
                    remote_path = file_path / r / current_path.name

            current_path_size = getsize(current_path)
            current_bytes -= current_path_size
            current_workers -= 1

            if not all((current_workers > 0, current_bytes > 0)):
                try:
                    tgbox.sync(gather(*to_upload))
                    to_upload.clear()
                except tgbox.errors.NotEnoughRights as e:
                    echo(f'\n[R0b]{e}[X]')
                    return

                current_workers = max_workers - 1
                current_bytes = max_bytes - current_path_size

            # --- Multi upload --------------------------------- #
            actual_file_size = current_path_size
            parts = ceil(current_path_size / multi_file_size)
            multipart_total_b = tgbox.tools.int_to_bytes(parts)

            multipart_offset = 0
            previous_part_id = b'genesis'

            if current_path_size > multi_file_size:
                for p in range(parts):
                    # will be True if part is already uploaded
                    skip_upload = False

                    part_path = remote_path.parent / f'{remote_path.name}-{p}'

                    if not force_update:

                        dlbf_sf = tgbox.tools.SearchFilter(
                            file_name=part_path.name,
                            scope=str(part_path.parent)
                        )
                        dlbf = ctx.obj.dlb.search_file(dlbf_sf)
                        try:
                            dlbf = next(sync_async_gen(dlbf))
                        except StopIteration:
                            pass # Proceed with upload
                        else:
                            p_bytes = tgbox.tools.int_to_bytes(p)
                            if dlbf.cattrs and dlbf.cattrs['__mp_part'] == p_bytes:
                                echo(f'[Y0b]| Part {p} of file {remote_path.name} '
                                    'is already uploaded. Skipping...[X]')

                                previous_part_id = tgbox.tools.int_to_bytes(dlbf.id)
                                skip_upload = True
                            else:
                                echo(
                                    f'[R0b]x File "{part_path}" is already exists in '
                                    'your LocalBox, so upload of Multipart file is '
                                    'impossible! Please rename your file or verify '
                                    'that your LocalBox is not broken (if you see '
                                    'this error after broken multipart upload)![X]')
                                break # will jump to continue

                    if actual_file_size >= multi_file_size:
                        actual_size = multi_file_size
                    else:
                        actual_size = actual_file_size

                    actual_file_size -= multi_file_size

                    if not skip_upload:
                        cattrs = {} if not parsed_cattrs else deepcopy(parsed_cattrs)

                        cattrs['__mp_previous'] = previous_part_id
                        cattrs['__mp_part'] = tgbox.tools.int_to_bytes(p)
                        cattrs['__mp_total'] = multipart_total_b

                        file = LimitedReader(
                            file_path=current_path,
                            start_pos=multipart_offset,
                            stop_pos=(multipart_offset + multi_file_size),
                            actual_size = actual_size
                        )
                        pw = _push_wrapper(
                            ctx = ctx,
                            file = file,
                            file_path = part_path,
                            cattrs = cattrs,
                            force_update = force_update,
                            no_update = no_update,
                            no_thumb = no_thumb,
                            use_slow_upload = use_slow_upload
                        )
                        drbf = tgbox.sync(pw)
                        previous_part_id = tgbox.tools.int_to_bytes(drbf.id)
                        file.close()

                    multipart_offset += multi_file_size

                continue
            # -------------------------------------------------- #

            pw = _push_wrapper(
                ctx = ctx,
                file = current_path,
                file_path = remote_path,
                cattrs = parsed_cattrs,
                force_update = force_update,
                no_update = no_update,
                no_thumb = no_thumb,
                use_slow_upload = use_slow_upload
            )
            to_upload.append(pw)

        if to_upload: # If any files left
            try:
                tgbox.sync(gather(*to_upload))
                to_upload.clear()
            except tgbox.errors.NotEnoughRights as e:
                echo(f'\n[R0b]{e}[X]')

        if calculate and target_files:
            echo(' ' * 60 + '\r', nl=True)
            echo(echo_text + '\n')
