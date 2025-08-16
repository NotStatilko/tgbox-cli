import click

from os import getenv
from platform import system

from ..group import cli_group
from ...tools.terminal import echo


@cli_group.command()
@click.option(
    '--bash', '-b', is_flag=True,
    help='If specified, will give commands for Bash'
)
@click.option(
    '--fish', '-f', is_flag=True,
    help='If specified, will give commands for Fish'
)
@click.option(
    '--zsh', '-z', is_flag=True,
    help='If specified, will give commands for Zsh'
)
@click.option(
    '--win-cmd', '-w', is_flag=True,
    help='If specified, will give commands for Zsh'
)
@click.pass_context
def cli_init(ctx, bash, fish, zsh, win_cmd):
    """Get commands for initializing TGBOX-CLI"""

    if ctx.obj.session:
        echo('[W0b]CLI is already initialized.[X]')
    else:
        if win_cmd or system() == 'Windows' and not any((bash, fish, zsh)):
            init_commands = (
                '(for /f %i in (\'tgbox-cli sk-gen\') '
                'do set "TGBOX_CLI_SK=%i") > NUL\n'
                'chcp 65001 || # Change the default CMD encoding to UTF-8'
            )
        else:
            current_shell = getenv('SHELL')

            autocompletions = {
                'bash': '\neval "$(_TGBOX_CLI_COMPLETE=bash_source tgbox-cli)"',
                'zsh': '\neval "$(_TGBOX_CLI_COMPLETE=zsh_source tgbox-cli)"',
                'fish' : '\neval (env _TGBOX_CLI_COMPLETE=fish_source tgbox-cli)'
            }
            if bash: autocomplete, cmd = autocompletions['bash'], 'bash'
            elif fish: autocomplete, cmd = autocompletions['fish'], 'fish'
            elif zsh: autocomplete, cmd = autocompletions['zsh'], 'zsh'
            else:
                if current_shell and 'bash' in current_shell:
                    autocomplete, cmd = autocompletions['bash'], 'bash'

                elif current_shell and 'fish' in current_shell:
                    autocomplete, cmd = autocompletions['fish'], 'fish'

                elif current_shell and 'zsh' in current_shell:
                    autocomplete, cmd = autocompletions['zsh'], 'zsh'
                else:
                    autocomplete, cmd = '', ''

            if cmd == 'fish':
                eval_commands = (
                    f'export TGBOX_CLI_SK=(tgbox-cli sk-gen)\n'
                    f'{autocomplete}')

            if cmd != 'fish':
                echo('\n# [B0b](Execute commands below if eval doesn\'t work)[X]\n')
                eval_commands = (
                    f'export TGBOX_CLI_SK="$(tgbox-cli sk-gen)"'
                    f'{autocomplete}'
                )
                echo(eval_commands)

                init_commands = 'eval "$(!!)" || true && clear'
            else:
                init_commands = (
                    f'export TGBOX_CLI_SK=(tgbox-cli sk-gen)'
                    f'{autocomplete}'
                )
        echo(
            '\n[Y0b]Welcome to the TGBOX-CLI![X]\n\n'
            'Copy & Paste commands below to your shell:\n\n'
           f'[W0b]{init_commands}[X]\n'
        )
