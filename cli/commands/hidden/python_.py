import logging
import click

from pathlib import Path
from code import interact as interactive_console

from ..group import cli_group
from ...tools.terminal import echo, colorize


@cli_group.command(hidden=True)
@click.option(
    '--enable-logging', is_flag=True,
    help='Will enable logging for Python session'
)
@click.option(
    '--execute', help='Path to Python script to execute',
    type=click.Path(readable=True, path_type=Path)
)
@click.option(
    '--non-interactive', is_flag=True,
    help='Will disable interactive console'
)
@click.option(
    '--i-understand-risk', is_flag=True,
    help='Will disable warning prompt'
)
@click.pass_context
def python(ctx, enable_logging, execute, non_interactive, i_understand_risk):
    """Launch interactive Python console"""

    global Objects
    Objects = ctx.obj

    if not enable_logging:
        logging.disable()

    global EXEC_SCRIPT

    if execute:
        # Users are notified about all risks of exec(), so we don't need Warning.
        EXEC_SCRIPT = lambda: exec(open(execute).read()) # pylint: disable=exec-used
    else:
        EXEC_SCRIPT = lambda: None

    if execute and not i_understand_risk:
        echo(
            '\n    [R0b]You are specified some Python script with the --execute option.\n'
            '    Third-party scripts can be useful for some actions that out of\n'
            '    TGBOX-CLI abilities, however, they can do MANY BAD THINGS to your\n'
            '    Telegram account [i.e STEAL IT] (or even to your System [i.e \n'
            '    REMOVE ALL FILES]) if written by ATTACKER. NEVER execute scripts\n'
            '    you DON\'T UNDERSTAND or DON\'T TRUST. NEVER! NEVER! NEVER![X]\n'
        )
        confirm = None
        while confirm != 'YES':
            prompt = (
                'Type [G0b]YES[X] [or [R0b]NO[X]'
                '] if you understand this and want to proceed'
            )
            confirm = click.prompt(colorize(prompt))
            if confirm in ('NO', 'no', 'n'):
                return

    if non_interactive:
        EXEC_SCRIPT()
    else:
        interactive_console(local=globals())
