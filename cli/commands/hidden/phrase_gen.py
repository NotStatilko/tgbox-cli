import click

from ..group import cli_group
from ...tools.terminal import echo
from ...config import tgbox


@cli_group.command(hidden=True)
@click.option(
    '--words', '-w', default=6,
    help='Words amount in Phrase'
)
def phrase_gen(words: int):
    """Generate random Phrase"""
    echo(f'[M0b]{tgbox.keys.Phrase.generate(words)}[X]')
