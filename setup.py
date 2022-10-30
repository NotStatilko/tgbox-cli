from setuptools import setup

setup(
    name="tgbox-cli",
    version='1.0',
    py_modules=['tgbox_cli','tools'],

    install_requires=[
        'tgbox', 'click==8.1.3',
        'enlighten==1.10.2'
    ],
    entry_points='''
        [console_scripts]
        tgbox-cli=tgbox_cli:safe_cli
    ''',
)
