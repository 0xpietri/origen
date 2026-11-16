"""origen: the real sky, computed with serious tools."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("origen")
except PackageNotFoundError:  # running from a source tree without installing
    __version__ = "0.0.0"
