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


class _FailingClient:
    """Stands in for AdvocuClient; every call fails with the given exception."""

    exc: Exception = RuntimeError("unset")

    def __init__(self, token=None, **kwargs):
        pass

    def list_all_activities(self):
        raise self.exc


def _run_failing(monkeypatch, exc, args=("list",)):
    import advocu_manager.cli as cli_module

    monkeypatch.setattr(cli_module, "AdvocuClient", type("C", (_FailingClient,), {"exc": exc}))
    return CliRunner().invoke(cli, ["--token", "t", *args])


def test_api_error_shows_one_line_not_a_traceback(monkeypatch):
    import requests

    result = _run_failing(monkeypatch, requests.HTTPError("HTTP 401: bad token (check your token)"))

    assert result.exit_code == 1
    assert "Error: HTTP 401: bad token" in result.output
    assert "Traceback" not in result.output


def test_network_error_shows_one_line_not_a_traceback(monkeypatch):
    from advocu_manager.api import AdvocuNetworkError

    result = _run_failing(monkeypatch, AdvocuNetworkError("Could not connect to Advocu"))

    assert result.exit_code == 1
    assert "Error: Could not connect to Advocu" in result.output
    assert "Traceback" not in result.output


def test_api_text_with_brackets_is_shown_verbatim(monkeypatch):
    # rich would swallow "[durationHours]" as a markup tag; click must not.
    import requests

    result = _run_failing(
        monkeypatch, requests.HTTPError("HTTP 400: [#: extraneous key [durationHours] is not permitted]")
    )

    assert "[durationHours]" in result.output


def test_error_is_handled_for_other_commands_too(monkeypatch):
    import requests

    result = _run_failing(monkeypatch, requests.HTTPError("HTTP 500: boom"), args=("stats",))

    assert result.exit_code == 1
    assert "Error: HTTP 500: boom" in result.output
