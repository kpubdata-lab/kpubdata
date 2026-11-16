"""The all-extras gate must fail rather than skip when dependencies are absent."""

from __future__ import annotations

import subprocess
import sys
import venv
from pathlib import Path

from scripts import smoke_installed_extras


def test_missing_optional_dependencies_make_the_smoke_command_fail(tmp_path: Path) -> None:
    environment = tmp_path / "minimal"
    venv.EnvBuilder(with_pip=False).create(environment)
    python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    script = Path(__file__).resolve().parents[3] / "scripts/smoke_installed_extras.py"
    result = subprocess.run(
        [str(python), "-I", str(script)], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 1
    assert "Installed extras smoke failed" in result.stderr
    assert "certifi" in result.stderr
    assert result.stdout == ""


def test_provider_credentials_and_network_are_unavailable_during_smoke(monkeypatch, capsys) -> None:
    import os
    import socket

    monkeypatch.setenv("KRX_ID", "synthetic-review-user")
    monkeypatch.setenv("KRX_PW", "synthetic-review-password")

    def attempted_network():
        assert os.environ["KRX_ID"] == os.environ["KRX_PW"] == ""
        with socket.socket() as connection:
            connection.connect(("127.0.0.1", 9))

    monkeypatch.setattr(smoke_installed_extras, "run_smoke", attempted_network)
    assert smoke_installed_extras.main() == 1
    captured = capsys.readouterr()
    assert "Network disabled" in captured.err
    assert captured.out == ""
    assert os.environ["KRX_ID"] == "synthetic-review-user"
    assert os.environ["KRX_PW"] == "synthetic-review-password"
