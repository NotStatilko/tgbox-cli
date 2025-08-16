import click

from base64 import urlsafe_b64encode

from ..group import cli_group
from ...tools.terminal import echo
from ...config import tgbox


@cli_group.command(hidden=True)
@click.option(
    '--size', '-s', default=32,
    help='SessionKey bytesize'
)
def sk_gen(size: int):
    """Generate random urlsafe b64encoded SessionKey"""
    echo(urlsafe_b64encode(tgbox.crypto.get_rnd_bytes(size)).decode())
