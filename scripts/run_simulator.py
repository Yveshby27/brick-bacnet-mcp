"""Spin up a bacpypes3-based virtual BACnet building from a fixtures YAML.

The simulator reads the synthetic-building YAML at tests/fixtures/simulator_devices.yaml
(or any path passed via --fixtures), creates a virtual BACnet device per entry,
exposes the listed objects, and responds to Who-Is + ReadProperty requests.

This is the test surface for the discovery + reader + server modules when real
BACnet hardware is not available.

Usage:

    pip install bacpypes3
    python scripts/run_simulator.py --fixtures tests/fixtures/simulator_devices.yaml --port 47808

Notes:

- v0.1 simulator handles a single broadcast domain.
- The simulator runs until interrupted (Ctrl-C).
- It binds to 0.0.0.0:47808 by default. If you already have a BACnet stack on
  that port (e.g. the production gateway), pass --port to choose another.
- bacpypes3 evolves quickly. If the import paths in this script no longer match
  the installed version, check the upstream README and adjust the imports below;
  the simulator pattern itself (one Application per device, register objects,
  serve) is stable.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("simulator")


# Map fixture YAML object-type strings to bacpypes3 type identifiers. Kept here
# so the fixture file format is decoupled from bacpypes3 internals.
OBJECT_TYPE_MAP = {
    "analog-input": "analogInput",
    "analog-output": "analogOutput",
    "analog-value": "analogValue",
    "binary-input": "binaryInput",
    "binary-output": "binaryOutput",
    "binary-value": "binaryValue",
    "multi-state-input": "multiStateInput",
    "multi-state-output": "multiStateOutput",
    "multi-state-value": "multiStateValue",
}


def _load_fixtures(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict) or "devices" not in raw:
        raise ValueError(f"{path} must be a YAML mapping with a 'devices' key")
    devices = raw["devices"]
    if not isinstance(devices, list):
        raise ValueError(f"{path}.devices must be a list")
    return devices


# Map colloquial unit strings used in the fixture YAML to bacpypes3-canonical
# EngineeringUnit enum names. bacpypes3 strictly validates the units field on
# Analog objects; the colloquial forms (degF, %) fail validation, so we
# normalize at simulator build time.
_UNIT_MAP = {
    "degF": "degreesFahrenheit",
    "°F": "degreesFahrenheit",
    "degC": "degreesCelsius",
    "°C": "degreesCelsius",
    "%": "percent",
    "percent": "percent",
    "ppm": "partsPerMillion",
    "cfm": "cubicFeetPerMinute",
    "kWh": "kilowattHours",
    "Wh": "wattHours",
    "kW": "kilowatts",
    "gallons": "usGallons",
    "liters": "liters",
    "m3": "cubicMeters",
    "therms": "therms",
    "inWC": "inchesOfWater",
}


def _normalize_units(raw: str | None) -> str | None:
    if raw is None or raw == "":
        return None
    return _UNIT_MAP.get(raw, raw)


async def _start_one_device(device_fixture: dict[str, Any], port: int) -> Any:
    """Construct one bacpypes3 Application for a single fixture device.

    Uses `Application.from_args(Namespace(...))` per bacpypes3 0.0.10x canonical
    factory. The Application's device object is built from the Namespace; we
    then add child objects via `app.add_object(obj)`.
    """
    try:
        from argparse import Namespace

        from bacpypes3.app import Application
        from bacpypes3.local.analog import (
            AnalogInputObject,
            AnalogOutputObject,
            AnalogValueObject,
        )
        from bacpypes3.local.binary import (
            BinaryInputObject,
            BinaryOutputObject,
            BinaryValueObject,
        )
        from bacpypes3.local.multistate import (
            MultiStateInputObject,
            MultiStateOutputObject,
            MultiStateValueObject,
        )
    except ImportError as e:
        raise RuntimeError(
            "bacpypes3 is required to run the simulator. Install via "
            "`pip install bacpypes3`. See the script docstring for notes."
        ) from e

    args = Namespace(
        name=device_fixture.get(
            "device_name", f"Sim-{device_fixture['device_instance']}"
        ),
        instance=device_fixture["device_instance"],
        network=0,
        address=f"0.0.0.0:{port}",
        vendoridentifier=device_fixture.get("vendor_id", 999),
        foreign=None,
        ttl=30,
        bbmd=None,
        route_aware=None,
        debug=None,
        color=None,
        loggers=False,
    )
    app = Application.from_args(args)

    type_to_class = {
        "analog-input": AnalogInputObject,
        "analog-output": AnalogOutputObject,
        "analog-value": AnalogValueObject,
        "binary-input": BinaryInputObject,
        "binary-output": BinaryOutputObject,
        "binary-value": BinaryValueObject,
        "multi-state-input": MultiStateInputObject,
        "multi-state-output": MultiStateOutputObject,
        "multi-state-value": MultiStateValueObject,
    }

    for obj_fixture in device_fixture.get("objects", []):
        otype = obj_fixture["type"]
        cls = type_to_class.get(otype)
        if cls is None:
            logger.warning("Skipping unsupported object type in fixture: %s", otype)
            continue
        kwargs: dict[str, Any] = {
            "objectIdentifier": (otype, obj_fixture["instance"]),
            "objectName": obj_fixture.get("name", f"{otype}-{obj_fixture['instance']}"),
            "presentValue": obj_fixture.get("present_value"),
        }
        if "description" in obj_fixture:
            kwargs["description"] = obj_fixture["description"]
        if otype.startswith("analog-"):
            units = _normalize_units(obj_fixture.get("units"))
            if units:
                kwargs["units"] = units
        obj = cls(**kwargs)
        app.add_object(obj)

    logger.info(
        "Started device instance %d (%s) on port %d with %d objects",
        device_fixture["device_instance"],
        args.name,
        port,
        len(device_fixture.get("objects", [])),
    )
    return app


def _collapse_fixture_objects(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten all fixture devices' objects into a single list, prefixing object
    instances per-device to avoid collisions.

    v0.1 design choice: BACnet/IP routing across multiple devices on Windows is
    fragile from a single broadcast port. The simulator collapses the fixture
    into ONE virtual device exposing all 19 objects so the discovery + reader +
    tagger paths can be exercised cleanly. Multi-device routing is a real
    BACnet/IP behavior but it isn't load-bearing for v0.1 code-path validation.
    """
    collapsed: list[dict[str, Any]] = []
    for dev_idx, dev in enumerate(devices):
        prefix = (dev_idx + 1) * 100  # device 0 → 100s, device 1 → 200s, etc.
        dev_name_short = dev.get("device_name", f"dev{dev_idx}")
        for obj in dev.get("objects", []):
            new_obj = dict(obj)
            new_obj["instance"] = prefix + obj["instance"]
            # Prefix the object name with the originating device for context
            new_obj["name"] = f"{dev_name_short}_{obj['name']}"
            collapsed.append(new_obj)
    return collapsed


async def run_simulator(fixtures_path: Path, port: int) -> None:
    devices = _load_fixtures(fixtures_path)
    logger.info("Loading %d device fixtures from %s", len(devices), fixtures_path)
    flattened_objects = _collapse_fixture_objects(devices)
    logger.info(
        "Collapsed %d fixture devices into 1 virtual device with %d objects",
        len(devices),
        len(flattened_objects),
    )

    collapsed_device = {
        "device_instance": 200000,
        "device_name": "brick-bacnet-mcp-sim",
        "vendor_id": 999,
        "vendor_name": "Simulator",
        "model_name": "SIM",
        "objects": flattened_objects,
    }
    app = await _start_one_device(collapsed_device, port)

    logger.info("Simulator running on port %d. Press Ctrl-C to stop.", port)
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Shutting down simulator...")
        try:
            result = app.close()
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.debug("Error closing app: %s", e)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=Path("tests/fixtures/simulator_devices.yaml"),
        help="Path to fixtures YAML",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=47808,
        help="Base BACnet/IP port (each fixture device gets port+N)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    asyncio.run(run_simulator(args.fixtures, args.port))


if __name__ == "__main__":
    main()
