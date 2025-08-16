import click

from os import getenv
from platform import platform
from sys import version as sys_version
from subprocess import CalledProcessError, run as subprocess_run

from ...config import (
    tgbox, TGBOX_CLI_NOCOLOR, CRYPTOGRAPHY_VERSION,
    CRYPTG_VERSION, LOGFILE, LOGLEVEL, VERSION
)
from ..group import cli_group
from ...tools.terminal import echo


@cli_group.command()
def cli_info():
    """Get information about the TGBOX-CLI build"""

    ver = VERSION.split('_')
    try:
        sp_result = subprocess_run(
            args=[tgbox.defaults.FFMPEG, '-version'],
            capture_output=True, stderr=None, check=True
        )
        ffmpeg_version = sp_result.stdout.split(b' ',3)[2].decode()
        ffmpeg_version = f"[G0b]YES[X]([C0b]v{ffmpeg_version}[X])"
    except CalledProcessError:
        ffmpeg_version = '[R0b]UNKNOWN[X]'
    except:
        ffmpeg_version = '[R0b]NOT FOUND[X]'

    if tgbox.crypto.FAST_ENCRYPTION:
        fast_encryption = f'[G0b]YES[X]([C0b]v{CRYPTOGRAPHY_VERSION}[X])'
    else:
        fast_encryption = '[R0b]NO[X]'

    if tgbox.crypto.FAST_TELETHON:
        fast_telethon = f'[G0b]YES[X]([C0b]v{CRYPTG_VERSION}[X])'
    else:
        fast_telethon = '[R0b]NO[X]'

    sys_ver = sys_version.split('[', 1)[0].strip()
    logfile_name = 'STDOUT' if not LOGFILE else LOGFILE.name

    echo(
        '\n# Copyright [W0b](c) Non [github.com/NotStatilko][X], the MIT License\n'
        '# Author Email: [W0b]thenonproton@protonmail.com[X]\n\n'

        f'TGBOX-CLI Version: [Y0b]{ver[0]}[X]\n'
        f'TGBOX Version: [M0b]{ver[1]}[X]\n\n'

        f'PYTHON: [C0b]{sys_ver}[X]\n'
        f'SYSTEM: [C0b]{platform()}[X]\n\n'

        f'FFMPEG: {ffmpeg_version}\n'
        f'FAST_ENCRYPTION: {fast_encryption}\n'
        f'FAST_TELETHON: {fast_telethon}\n\n'

        f'LOGGING: [Y0b]{LOGLEVEL}[X]([W0b]{logfile_name}[X])\n'
    )
    if getenv('BLACK_SABBATH'):
        from time import sleep

        bs_ana = (
            '\nI am the world that hides the universal secret of all time\n'
            'Destruction of the empty spaces is my one and only crime\n'
            'I\'ve lived a thousand times, I found out what it means to be believed\n'
            'The thoughts and images, the unborn child that never was conceived\n'
        )
        for L in bs_ana:
            if TGBOX_CLI_NOCOLOR:
                echo(L, nl=False)
            else:
                click.secho(
                    L, fg='white', bg='bright_red',
                    bold=True, italic=True, nl=False
                )
            if L == '\n':
                sleep(0.999)
            elif L == ',':
                sleep(0.666)
            else:
                sleep(0.0666)

        echo('\n') # HAHA!!!
