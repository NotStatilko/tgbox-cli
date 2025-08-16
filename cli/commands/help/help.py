import click

from ..group import cli_group
from ...tools.terminal import echo, colorize
from ...config import PACKAGE, TGBOX_CLI_NOCOLOR


@cli_group.command(name='help')
@click.option(
    '--non-interactive', '-n', is_flag=True,
    help='If specified, will echo to shell instead of pager'
)
def help_(non_interactive):
    """Write this command for extended Help!"""

    help_text = open(PACKAGE / 'data' / 'help.txt').read()
    if non_interactive:
        echo(help_text)
    else:
        colored = False if TGBOX_CLI_NOCOLOR else None
        click.echo_via_pager(colorize(help_text), color=colored)
