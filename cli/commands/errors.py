"""Module with Exception classes"""

import click

class CheckCTXFailed(click.exceptions.ClickException):
    """Will be raised if check_ctx found unsupported requirement"""
