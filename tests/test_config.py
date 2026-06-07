"""Tests for the config loader."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from brick_bacnet_mcp.config import Config, load_config


def test_load_defaults_when_missing(tmp_path: Path) -> None:
    config = load_config(tmp_path / "does_not_exist.yaml")
    assert isinstance(config, Config)
    assert config.bacnet.local_device_instance == 555001
    assert config.mcp.transport == "stdio"
    assert config.log_level == "INFO"


def test_load_minimal(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        """
bacnet:
  local_device_instance: 12345
  polling_interval_seconds: 60
mcp:
  transport: http
  http_port: 9000
log_level: DEBUG
""",
        encoding="utf-8",
    )
    config = load_config(path)
    assert config.bacnet.local_device_instance == 12345
    assert config.bacnet.polling_interval_seconds == 60
    assert config.mcp.transport == "http"
    assert config.mcp.http_port == 9000
    assert config.log_level == "DEBUG"


def test_invalid_log_level_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("log_level: NOPE\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_config(path)


def test_invalid_transport_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("mcp:\n  transport: tcp\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_config(path)


def test_extra_keys_rejected(tmp_path: Path) -> None:
    """Config schema is strict; typos should fail loudly."""
    path = tmp_path / "config.yaml"
    path.write_text(
        """
bacnet:
  local_device_instance: 1
  bogus_field: should_fail
""",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_config(path)
