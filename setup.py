from setuptools import setup, find_packages
from ast import literal_eval

with open('cli/version.py', encoding='utf-8') as f:
    version = literal_eval(f.read().split('=')[1].strip())

setup(
    name             = 'tgbox-cli',
    version          = version,
    packages         = find_packages(),
    py_modules       = ['main'],
    license          = 'MIT',
    description      = 'A Command Line Interface to the TGBOX',
    long_description = open('README.md', encoding='utf-8').read(),
    author           = 'NotStatilko',
    author_email     = 'thenonproton@pm.me',
    url              = 'https://github.com/NotStatilko/tgbox-cli',
    download_url     = f'https://github.com/NotStatilko/tgbox-cli/archive/refs/tags/v{version}.tar.gz',

    long_description_content_type='text/markdown',

    package_data = {
        'tgbox_cli': ['cli/data'],
    },
    include_package_data = True,

    install_requires=[
        'tgbox<2',
        'click==8.3.0',
        'enlighten==1.14.1'
    ],
    extras_require={
        'fast': ['tgbox[fast]<2']
    },
    keywords = [
        'Telegram', 'Cloud-Storage',
        'Cloud', 'Non-official'
    ],
    entry_points='''
        [console_scripts]
        tgbox-cli=main:safe_tgbox_cli_startup
    '''
)
