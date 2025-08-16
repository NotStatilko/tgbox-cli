import click

from ..group import cli_group
from ..helpers import ctx_require
from ...tools.terminal import echo
from ...config import tgbox


@cli_group.command()
@click.argument('defaults',nargs=-1)
@ctx_require(dlb=True)
def box_default(ctx, defaults):
    """Change the TGBOX default values to your own

    \b
    I.e:\b
        # Change METADATA_MAX to the max allowed size
        tgbox-cli box-default METADATA_MAX=1677721
        \b
        # Change download path from DownloadsTGBOX to Downloads
        tgbox-cli box-default DOWNLOAD_PATH=Downloads
    """
    for default in defaults:
        try:
            key, value = default.split('=',1)
            tgbox.sync(ctx.obj.dlb.defaults.change(key, value))
            echo(f'[G0b]Successfully changed {key} to {value}[X]')
        except AttributeError:
            echo(f'[R0b]Default {key} doesn\'t exist, skipping[X]')
