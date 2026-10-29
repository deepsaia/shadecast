"""Settings resolve once, from the constant, the environment, then the flags, and reach uvicorn."""

import socket
from pathlib import Path

import pytest
from typer.testing import CliRunner

from shadecast import serve_cli
from shadecast.cli import app
from shadecast.server.settings import ServerSettings

runner = CliRunner()


def test_settings_come_from_the_environment_when_set(monkeypatch):
    monkeypatch.delenv("SDC_HOST", raising=False)
    monkeypatch.setenv("SDC_PORT", "9999")
    monkeypatch.setenv("SDC_DATA", "/elsewhere/data")
    settings = ServerSettings.from_environment()
    assert settings.host == "127.0.0.1" and settings.port == 9999
    assert settings.data_root == Path("/elsewhere/data")
    assert settings.environment() == {
        "SDC_HOST": "127.0.0.1",
        "SDC_PORT": "9999",
        "SDC_DATA": "/elsewhere/data",
    }
    assert settings.tiles_root == Path("/elsewhere/data/tiles")


def test_flags_override_the_environment(monkeypatch):
    monkeypatch.setenv("SDC_PORT", "9999")
    settings = serve_cli.resolve(None, 7000, Path("d"), True)
    assert settings.port == 7000 and settings.data_root == Path("d") and settings.reload is True


def test_serve_exports_the_settings_and_runs_the_factory(monkeypatch):
    seen: dict = {}
    monkeypatch.delenv("SDC_HOST", raising=False)
    monkeypatch.delenv("SDC_PORT", raising=False)
    monkeypatch.delenv("SDC_DATA", raising=False)
    monkeypatch.setattr(serve_cli.uvicorn, "run", lambda target, **kwargs: seen.update(target=target, **kwargs))
    result = runner.invoke(app, ["serve", "--port", "9000", "--no-open"])
    assert result.exit_code == 0, result.output
    assert seen["target"] == "shadecast.server.app:create_app" and seen["factory"] is True
    assert seen["port"] == 9000 and seen["host"] == "127.0.0.1" and seen["reload"] is False
    assert serve_cli.os.environ.get("SDC_PORT") == "9000"
    assert "http://127.0.0.1:9000/" in result.stdout


def test_a_port_already_in_use_is_named_before_anything_starts(monkeypatch):
    holder = socket.socket()
    holder.bind(("127.0.0.1", 0))
    holder.listen(1)
    port = holder.getsockname()[1]
    try:
        monkeypatch.setattr(serve_cli.uvicorn, "run", lambda *args, **kwargs: pytest.fail("uvicorn ran"))
        result = runner.invoke(app, ["serve", "--port", str(port), "--no-open"])
    finally:
        holder.close()
    assert result.exit_code == 1
    assert f"port {port} is already in use" in result.output and "--port" in result.output
