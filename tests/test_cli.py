from click.testing import CliRunner

from advocu_manager import __version__
from advocu_manager.cli import cli


def test_version_flag_prints_package_version():
    result = CliRunner().invoke(cli, ["--version"])

    assert result.exit_code == 0
    assert result.output.strip() == f"advocu, version {__version__}"


def test_short_version_flag():
    result = CliRunner().invoke(cli, ["-V"])

    assert result.exit_code == 0
    assert __version__ in result.output


def test_version_is_a_real_version_not_unknown():
    assert __version__ != "unknown"
    assert all(part.isdigit() for part in __version__.split("."))
