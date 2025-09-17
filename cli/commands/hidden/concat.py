import click
from pathlib import Path

from ..group import cli_group
from ...tools.terminal import echo


@cli_group.command(hidden=True)
@click.argument('parts', nargs=-1)
@click.option(
    '--remove', '-r', is_flag=True,
    help='If specified, will remove parts after concatenation'
)
def concat(parts, remove):
    """Concatenate multiple files on your Machine into one

    \b
    You can use this command to concat Multipart file parts
    into one file if Download as one is impossible (if some
    parts are missing, for example).
    \b
    Example:\b
        # Assuming we're in directory where parts are located
        tgbox-cli concat Video.mp4 Video.mp4-0 Video.mp4-1
    \b
    Here, first argument of command is "concated file" name,
    in our case it's "Video.mp4", we have two parts that
    are named "Video.mp4-0" and "Video.mp4-1", we want
    to insert part 1 at the end of part 0, thus, correct
    order here is from lowest part (0) to highest (1).
    """
    parts = list(parts)

    if not parts:
        echo('[R0b]x Incorrect usage. See --help.[X]')
        return

    if len(parts) == 1:
        echo('[R0b]x You should specify parts. See --help.[X]')
        return

    concatedp = Path(parts[0])
    if concatedp.exists():
        echo(f'[R0b]x File "{concatedp.absolute()}" already exists.[X]')
        return

    for i, part in enumerate(parts[1:]):
        parts[i+1] = Path(part)

        if not parts[i+1].exists():
            echo(f'[R0b]x File "{parts[i+1].absolute()}" does not exist.[X]')
            return

    with open(concatedp,'wb') as concatedf:
        for part in parts[1:]:
            with open(part,'rb') as partf:
                while (chunk := partf.read(128_000_000)):
                    echo(
                        f'[Y1]Write {len(chunk)} bytes from {part.name} '
                        f'to {concatedp.name}[X]')
                    concatedf.write(chunk)
    if remove:
        for part in parts[1:]:
            part.unlink()

    echo('[G0b]Done.[X]')
