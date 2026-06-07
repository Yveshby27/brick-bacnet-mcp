"""Config loader for brick-bacnet-mcp.

Reads YAML config files and validates them against a Pydantic schema. The
config governs BACnet network settings, rule file paths, MCP transport choice,
and log verbosity.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class BACnetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    local_device_instance: int = Field(
        default=555001,
        ge=0,
        le=4194303,
        description="BACnet device instance used by this server when broadcasting",
    )
    broadcast_address: str = Field(
        default="255.255.255.255",
        description="BACnet/IP broadcast target (use subnet broadcast for production)",
    )
    bind_address: str = Field(
        default="0.0.0.0:47808",
        description="Local socket bind for the BACnet/IP stack",
    )
    polling_interval_seconds: int = Field(
        default=30, ge=1, description="Property polling cadence in seconds"
    )
    discovery_timeout_seconds: int = Field(
        default=5, ge=1, description="Wait time after Who-Is broadcast for I-Am replies"
    )


class RulesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brick: str = Field(
        default="src/brick_bacnet_mcp/rules/brick_rules.yaml",
        description="Path to Brick rules YAML",
    )
    haystack: str = Field(
        default="src/brick_bacnet_mcp/rules/haystack_rules.yaml",
        description="Path to Haystack rules YAML",
    )


class MCPConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transport: Literal["stdio", "http"] = Field(default="stdio", description="MCP transport")
    http_port: int = Field(
        default=8080, ge=1, le=65535, description="HTTP port if transport == http"
    )
    http_host: str = Field(
        default="127.0.0.1",
        description="HTTP bind host if transport == http",
    )


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bacnet: BACnetConfig = Field(default_factory=BACnetConfig)
    rules: RulesConfig = Field(default_factory=RulesConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    log_level: str = Field(default="INFO")

    @model_validator(mode="after")
    def _validate_log_level(self) -> Config:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.log_level.upper() not in valid:
            raise ValueError(f"log_level must be one of {sorted(valid)}; got {self.log_level}")
        self.log_level = self.log_level.upper()
        return self


def load_config(path: str | Path) -> Config:
    """Read a YAML config file into a validated Config instance.

    Missing config file = use all defaults (informational; not an error).
    """
    p = Path(path)
    if not p.exists():
        return Config()
    with p.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Config file {p} must be a YAML mapping")
    return Config.model_validate(raw)
