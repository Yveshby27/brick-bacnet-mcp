"""Shared pytest fixtures for brick-bacnet-mcp.

Most v0.1 tests are pure-Python (tagger, topology assembler, config). Integration
tests against a live bacpypes3 simulator are skipped unless `BACNET_LIVE_TESTS=1`
is set and a simulator is reachable on the local network.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
RULES_DIR = PROJECT_ROOT / "src" / "brick_bacnet_mcp" / "rules"
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def rules_dir() -> Path:
    return RULES_DIR


@pytest.fixture(scope="session")
def brick_rules_path(rules_dir: Path) -> Path:
    return rules_dir / "brick_rules.yaml"


@pytest.fixture(scope="session")
def haystack_rules_path(rules_dir: Path) -> Path:
    return rules_dir / "haystack_rules.yaml"


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture(scope="session")
def simulator_devices_path(fixtures_dir: Path) -> Path:
    return fixtures_dir / "simulator_devices.yaml"


@pytest.fixture(scope="session")
def live_tests_enabled() -> bool:
    return os.environ.get("BACNET_LIVE_TESTS", "0") == "1"


@pytest.fixture
def skip_unless_live(live_tests_enabled: bool) -> None:
    if not live_tests_enabled:
        pytest.skip("Skipping live BACnet test: set BACNET_LIVE_TESTS=1 to enable.")
