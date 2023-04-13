from setuptools import setup

setup(
    name="tgbox-cli",
    version='1.0',
    packages=['tgbox_cli'],

    package_data = {
        'tgbox_cli': ['tgbox_cli/data'],
    },
    include_package_data = True,

    install_requires=[
        'urllib3',
        'tgbox<2',
        'click==8.1.3',
        'enlighten==1.10.2'
    ],
    extras_require={
        'fast': ['tgbox[fast]<2']
    },
    entry_points='''
        [console_scripts]
        tgbox-cli=tgbox_cli.tgbox_cli:safe_tgbox_cli_startup
    '''
)
