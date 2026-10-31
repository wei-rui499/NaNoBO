"""Run before PyInstaller's Qt hooks in the shared Python 3.10 executable.

PySide 6.8 adds a typing.Self backport which Python 3.10's Union rejects.
Initialize the supported typing_extensions backport before Qt touches typing.
"""
import typing_extensions  # noqa: F401
