"""The server's schema is printed offline, so the client's types come from the one contract."""

import json

from shadecast.server import openapi


def test_the_schema_prints_without_a_running_server_or_data(capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert openapi.main() == 0
    schema = json.loads(capsys.readouterr().out)
    assert "/api/v1/cities/{city}/tiles/{tile}/report" in schema["paths"]
    assert "TileReport" in schema["components"]["schemas"]
