from ..group import cli_group
from ...tools.terminal import echo
from ...config import LOGFILE


@cli_group.command()
def logfile_wipe():
    """Clear all logfile entries"""
    if not LOGFILE:
        echo('[R0b]Can not clean Logfile[X]')
        return
    open(LOGFILE,'w').close()
    echo('[G0b]Done.[X]')
