import ipaddress
import os
import socket
from pathlib import Path
from typing import Any

import pytest


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail any test that tries to reach a non-loopback address."""
    real_connect = socket.socket.connect

    def guarded_connect(self: socket.socket, address: Any) -> None:
        host = address[0] if isinstance(address, tuple) else None
        if isinstance(host, str) and not _is_loopback(host):
            raise RuntimeError(f"network access blocked in tests: {host}")
        real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    # Models must already be in the local cache; never check the Hub for updates.
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep tests independent from the developer's fonti.toml, .env and FONTI_* variables."""
    for name in list(os.environ):
        if name.startswith("FONTI_"):
            monkeypatch.delenv(name)
    # Never load the real reranker in fast tests; tests that rerank inject a fake one.
    monkeypatch.setenv("FONTI_RERANK__ENABLED", "false")
    monkeypatch.chdir(tmp_path)
