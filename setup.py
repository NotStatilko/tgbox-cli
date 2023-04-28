from setuptools import setup
from ast import literal_eval

with open('tgbox_cli/version.py', encoding='utf-8') as f:
    version = literal_eval(f.read().split('=',1)[1].strip())

setup(
    name             = "tgbox-cli",
    version          = version,
    packages         = ['tgbox_cli'],
    license          = 'MIT',
    description      = 'A Command Line Interface to the TGBOX',
    author           = 'NotStatilko',
    author_email     = 'thenonproton@pm.me',
    url              = 'https://github.com/NotStatilko/tgbox-cli',
    download_url     = f'https://github.com/NotStatilko/tgbox-cli/archive/refs/tags/v{version}.tar.gz',

    install_requires=[
        'urllib3',
        'tgbox<1',
        'click==8.1.3',
        'enlighten==1.10.2'
    ],
    extras_require={
        'fast': ['tgbox[fast]<1']
    },
    keywords = [
        'Telegram', 'Cloud-Storage',
        'Cloud', 'Non-official'
    ],
    classifiers = [
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: End Users/Desktop',
        'Topic :: Security :: Cryptography',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
    entry_points='''
        [console_scripts]
        tgbox-cli=tgbox_cli.tgbox_cli:safe_tgbox_cli_startup
    '''
)
