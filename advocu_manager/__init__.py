from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("advocu-manager")
except PackageNotFoundError:
    __version__ = "unknown"
