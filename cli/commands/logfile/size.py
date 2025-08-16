from ..group import cli_group
from ...tools.convert import format_bytes
from ...tools.terminal import echo
from ...config import LOGFILE


@cli_group.command()
def logfile_size():
    """Get bytesize of logfile"""
    if not LOGFILE:
        echo('[R0b]We can not calculate the size of Logfile[X]')
        return

    size = format_bytes(LOGFILE.stat().st_size)
    echo(f'[W0b]{str(LOGFILE)}[X]: {size}')
