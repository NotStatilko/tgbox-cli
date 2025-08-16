import click

from re import search as re_search
from os.path import getsize
from asyncio import gather
from pathlib import Path

from filetype import guess as filetype_guess

from ...tools.convert import (
    filters_to_searchfilter, parse_str_cattrs,
    format_bytes
)
from ..group import cli_group
from ..helpers import ctx_require
from ...tools.terminal import echo, ProgressBar
from ...config import tgbox


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
    '--cattrs', '-c', help='File\'s CustomAttributes. Format: "key: value | key: value"'
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
    help='If specified, will calculate and show a total bytesize of targets'
)
@click.option(
    '--max-workers', default=10, type=click.IntRange(1,50),
    help='Max amount of files uploaded at the same time, default=10',
)
@click.option(
    '--max-bytes', default=200000000,
    type=click.IntRange(1000000, 1000000000),
    help='Max amount of bytes uploaded at the same time, default=200000000',
)
@ctx_require(dlb=True, drb=True)
def file_upload(
        ctx, target, file_path, cattrs, no_update,
        force_update, use_slow_upload, no_thumb,
        calculate, max_workers, max_bytes):
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
        # Exclude flag (ingore .DOC, upload every single file from Documents)
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
    target = tuple(set(Path(p) for p in target))

    current_workers = max_workers
    current_bytes = max_bytes

    if cattrs is not None and not cattrs:
        parsed_cattrs = {}

    elif cattrs is not None:
        parsed_cattrs = parse_str_cattrs(cattrs)
    else:
        parsed_cattrs = None

    def _upload(to_upload: list):
        tgbox.sync(gather(*to_upload))
        to_upload.clear()

    async def _push_wrapper(file, file_path, cattrs):
        fingerprint = tgbox.tools.make_file_fingerprint(
            mainkey = ctx.obj.dlb.mainkey,
            file_path = str(file_path)
        )
        # Standard file upload if dlbf is not exists (from scratch)
        if not (dlbf := await ctx.obj.dlb.get_file(fingerprint=fingerprint)) and not force_update:
            file_action = (ctx.obj.drb.push_file, {})

        # File re-uploading (or updating) if file size differ
        elif force_update or not no_update and dlbf and dlbf.size != getsize(file):
            if not dlbf: # Wasn't uploaded before
                file_action = (ctx.obj.drb.push_file, {})
            else:
                drbf = await ctx.obj.drb.get_file(dlbf.id)
                file_action = (ctx.obj.drb.update_file, {'rbf': drbf})
        else:
            # Ignore upload if file exists and wasn't changed
            echo(f'[Y0b]| File {file} is already uploaded. Skipping...[X]')
            return

        if cattrs is None: # CAttrs not specified
            cattrs = cattrs or dlbf.cattrs if dlbf else None

        elif not cattrs: # Can be "", then remove CAttrs
            cattrs = None
        else:
            if dlbf and dlbf.cattrs: # Combine if dlbf has CAttrs
                dlbf.cattrs.update(cattrs)
                cattrs = dlbf.cattrs
        try:
            pf = await ctx.obj.dlb.prepare_file(
                file = open(file,'rb'),
                file_path = file_path,
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

        progressbar = ProgressBar(ctx.obj.enlighten_manager, file.name)

        file_action[1]['pf'] = pf
        file_action[1]['progress_callback'] = progressbar.update
        file_action[1]['use_slow_upload'] = use_slow_upload

        await file_action[0](**file_action[1])

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
            except (FileNotFoundError, PermissionError, OSError) as e:
                echo(f'[R0b]x Not Working on. {e}. Skipping...[X]')
                continue

            if filters:
                # Flags. First is for 'Include', the second
                # is for 'Exclude. Both must be 'True' to
                # start uploading process.
                yield_result = [True, True]

                # Will use Regex Search if 're' is included in Filters, "In" otherwise.
                in_func = re_search if filters.in_filters['re'] else lambda p,s: p in s

                for indx, filter in enumerate((filters.in_filters, filters.ex_filters)):
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
                        yield_result[0] = False; break

                    for filter_file_path in filter['file_path']:
                        if in_func(filter_file_path, abs_path): # pylint: disable=E0606
                            if indx == 1:
                                yield_result[indx] = False
                            break
                    else:
                        if filter['file_path']:
                            if indx == 0:
                                yield_result[indx] = False
                                break

                    for file_name in filter['file_name']:
                        if in_func(file_name, current_path.name):
                            if indx == 1:
                                yield_result[indx] = False
                            break
                    else:
                        if filter['file_name']:
                            if indx == 0:
                                yield_result[indx] = False
                                break

                    for mime in filter['mime']:
                        if in_func(mime, file_mime):
                            if indx == 1:
                                yield_result[indx] = False
                            break
                    else:
                        if filter['mime']:
                            if indx == 0:
                                yield_result[indx] = False
                                break

                    if filter['min_time']:
                        if cp_st_mtime < filter['min_time'][-1]: # pylint: disable=E0606
                            if indx == 0:
                                yield_result[indx] = False
                                break

                        elif cp_st_mtime >= filter['min_time'][-1]:
                            if indx == 1:
                                yield_result[indx] = False
                                break

                    if filter['max_time']:
                        if cp_st_mtime > filter['max_time'][-1]:
                            if indx == 0:
                                yield_result[indx] = False
                                break

                        elif cp_st_mtime <= filter['max_time'][-1]:
                            if indx == 1:
                                yield_result[indx] = False
                                break

                    if filter['min_size']:
                        if cp_st_size < filter['min_size'][-1]: # pylint: disable=E0606
                            if indx == 0:
                                yield_result[indx] = False
                                break

                        elif cp_st_size >= filter['min_size'][-1]:
                            if indx == 1:
                                yield_result[indx] = False
                                break

                    if filter['max_size']:
                        if cp_st_size > filter['max_size'][-1]:
                            if indx == 0:
                                yield_result[indx] = False
                                break

                        elif cp_st_size <= filter['max_size'][-1]:
                            if indx == 1:
                                yield_result[indx] = False
                                break

                if not all(yield_result):
                    echo(
                        f'[Y0b]x Target "{current_path}" is '
                        'ignored by filters! Skipping...[X]'
                    )
                    continue

            if calculate:
                if not current_path.exists():
                    echo(
                       f'[R0b]@ Target "{current_path}" doesn\'t '
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
            else:
                if not file_path:
                    remote_path = current_path.resolve()
                else:
                    remote_path = Path(file_path) / current_path.name

                current_bytes -= getsize(current_path)
                current_workers -= 1

                if not all((current_workers > 0, current_bytes > 0)):
                    try:
                        _upload(to_upload)
                    except tgbox.errors.NotEnoughRights as e:
                        echo(f'\n[R0b]{e}[X]')
                        return

                    current_workers = max_workers - 1
                    current_bytes = max_bytes - getsize(current_path)

                pw = _push_wrapper(
                    file = current_path,
                    file_path = remote_path,
                    cattrs = parsed_cattrs
                )
                to_upload.append(pw)

        if to_upload: # If any files left
            try:
                _upload(to_upload)
            except tgbox.errors.NotEnoughRights as e:
                echo(f'\n[R0b]{e}[X]')

        if calculate and target_files:
            echo(' ' * 60 + '\r', nl=True)
            echo(echo_text + '\n')
