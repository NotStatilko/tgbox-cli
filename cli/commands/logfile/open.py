import click

from ..group import cli_group
from ...config import LOGFILE
from ...tools.terminal import echo


@cli_group.command()
@click.option(
    '--locate', '-l', is_flag=True,
    help='If specified, will open file path in file manager'
)
def logfile_open(locate):
    """Open logfile with default app"""
    if LOGFILE:
        click.launch(str(LOGFILE), locate=locate)
    else:
        echo('[R0b]Can not open Logfile[X]')
