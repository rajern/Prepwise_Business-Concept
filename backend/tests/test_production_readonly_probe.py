import importlib.util
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def probe() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts" / "verify_production_readonly.py"
    spec = importlib.util.spec_from_file_location("production_readonly_probe", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_missing_cli_is_safe(
    probe: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(probe.shutil, "which", lambda name: None)
    assert probe.main() == 1
    assert json.loads(capsys.readouterr().out) == {"error_type": "AzureCliUnavailable"}


def test_cli_exception_text_is_never_printed(
    probe: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(probe.shutil, "which", lambda name: "az")
    monkeypatch.setattr(probe.subprocess, "run", Mock(side_effect=RuntimeError("PRIVATE_SENTINEL")))
    assert probe.main() == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"error_type": "RuntimeError"}
    assert "PRIVATE_SENTINEL" not in captured.out + captured.err


def test_denied_cli_does_not_print_captured_credentials_or_connect(
    probe: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(probe.shutil, "which", lambda name: "az")
    monkeypatch.setattr(
        probe.subprocess,
        "run",
        Mock(return_value=SimpleNamespace(returncode=1, stdout="PRIVATE_SENTINEL")),
    )
    connect = Mock()
    monkeypatch.setattr(probe, "create_engine", connect)
    assert probe.main() == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"error_type": "RuntimeCredentialReadDenied"}
    assert "PRIVATE_SENTINEL" not in captured.out + captured.err
    connect.assert_not_called()
