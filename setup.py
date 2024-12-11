from setuptools import setup
from ast import literal_eval

with open('tgbox_cli/version.py', encoding='utf-8') as f:
    version = literal_eval(f.read().split('=')[1].strip())

setup(
    name             = "tgbox-cli",
    version          = version,
    packages         = ['tgbox_cli'],
    license          = 'MIT',
    description      = 'A Command Line Interface to the TGBOX',
    long_description = open('README.md', encoding='utf-8').read(),
    author           = 'NotStatilko',
    author_email     = 'thenonproton@pm.me',
    url              = 'https://github.com/NotStatilko/tgbox-cli',
    download_url     = f'https://github.com/NotStatilko/tgbox-cli/archive/refs/tags/v{version}.tar.gz',

    long_description_content_type='text/markdown',

    package_data = {
        'tgbox_cli': ['tgbox_cli/data'],
    },
    include_package_data = True,

    install_requires=[
        'urllib3',
        'tgbox<2',
        'click==8.1.3',
        'enlighten==1.12.0'
    ],
    extras_require={
        'fast': ['tgbox[fast]<2']
    },
    keywords = [
        'Telegram', 'Cloud-Storage',
        'Cloud', 'Non-official'
    ],
    classifiers = [
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: End Users/Desktop',
        'Topic :: Security :: Cryptography',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12'
    ],
    entry_points='''
        [console_scripts]
        tgbox-cli=tgbox_cli.tgbox_cli:safe_tgbox_cli_startup
    '''
)
