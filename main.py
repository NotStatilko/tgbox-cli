#!/usr/bin/env python3

import click
import cli

if not cli.config.TGBOX_CLI_COMPLETE:
    import logging
    import warnings

    from traceback import format_exception
    try:
        # This will enable navigation in input
        import readline # pylint: disable=unused-import
    except (ImportError, ModuleNotFoundError):
        pass

    logger = logging.getLogger(__name__)

    # Disable annoying (in CLI) UserWarning/RuntimeWarning
    warnings.simplefilter('ignore', category=UserWarning)
    warnings.simplefilter('ignore', category=RuntimeWarning)


def safe_tgbox_cli_startup():
    try:
        cli.commands.group.cli_group(standalone_mode=False)
    except click.exceptions.NoArgsIsHelpError as e:
        # Normal behaviour, tells us just to show commands list
        cli.tools.terminal.echo(e.format_message())
    except Exception as e:
        if isinstance(e, (click.Abort, cli.commands.errors.CheckCTXFailed)):
            exit(0)

        traceback = ''.join(format_exception(
            e,
            value = e,
            tb = e.__traceback__
        ))
        # This will ignore some click exceptions that we really
        # don't need to log like click.exceptions.UsageError
        if not issubclass(type(e), click.exceptions.ClickException):
            logger.error(traceback)

        if cli.config.DEBUG_MODE:
            cli.tools.terminal.echo(f'[R0b]{traceback}[X]')

        elif e.args: # Will echo only if error have message
            cli.tools.terminal.echo(f'[R0b]{e}[X]')

        cli.tools.terminal.echo('')
        exit(1)

if __name__ == '__main__':
    safe_tgbox_cli_startup()
