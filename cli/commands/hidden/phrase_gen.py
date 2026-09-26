import click
import phrasegen

from ..group import cli_group
from ...tools.terminal import echo


@cli_group.command(hidden=True)
@click.option(
    '--words', '-w', default=6,
    help='Words amount in Phrase'
)
@click.option(
    '--language', '-l', default='en',
    help='Language code to select Words list'
)
def phrase_gen(words, language):
    """Generate random Phrase"""

    g = phrasegen.Generator()
    l = language.strip().lower()

    if l not in g.supported_languages:
        echo(
            f'[R0b]x Invalid lang code. We support '
            f'only {g.supported_languages}[X]')
    else:
        echo(f'[M0b]{getattr(g,l).generate(words)}[X]')
