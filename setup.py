from setuptools import setup

setup(
    name="tgbox-cli",
    version='0.1',
    py_modules=['tgbox_cli','tools'],
    install_requires=[
        'click', 'tgbox'
    ],
    entry_points='''
        [console_scripts]
        tgbox-cli=tgbox_cli:safe_cli
    ''',
)
