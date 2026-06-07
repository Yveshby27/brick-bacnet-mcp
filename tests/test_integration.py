"""End-to-end integration test: bacpypes3 simulator + Discovery + Reader +
Tagger + TopologyAssembler.

This test is gated on the environment variable `BACNET_LIVE_TESTS=1` because
it spins up two bacpypes3 Application instances on local UDP sockets, which
some CI environments cannot do. To run locally:

    BACNET_LIVE_TESTS=1 pytest tests/test_integration.py -v

On Windows, bacpypes3 broadcast on the loopback adapter is environmentally
blocked (the IPv4 stack lacks a broadcast address for 127.0.0.1). The test
therefore uses a unicast Who-Is to the known simulator address. This validates
the same Discovery + Reader + Tagger code paths a real network would.
"""

from __future__ import annotations

import asyncio
import logging
from argparse import Namespace
from pathlib import Path
from typing import Any

import pytest

from brick_bacnet_mcp.config import BACnetConfig
from brick_bacnet_mcp.discovery import Discovery
from brick_bacnet_mcp.models import BACnetDevice
from brick_bacnet_mcp.reader import Reader
from brick_bacnet_mcp.tagger import Tagger
from brick_bacnet_mcp.topology import TopologyAssembler

pytestmark = pytest.mark.asyncio


SIM_PORT = 47808
DISC_PORT = 47809
SIM_INSTANCE = 200000
DISC_INSTANCE = 555001


def _sim_args() -> Namespace:
    return Namespace(
        name="sim",
        instance=SIM_INSTANCE,
        network=0,
        address=f"127.0.0.1:{SIM_PORT}",
        vendoridentifier=999,
        foreign=None,
        ttl=30,
        bbmd=None,
        route_aware=None,
        debug=None,
        color=None,
        loggers=False,
    )


async def _build_simulator() -> Any:
    """Spin up a bacpypes3 Application with a few representative objects."""
    from bacpypes3.app import Application
    from bacpypes3.local.analog import AnalogInputObject
    from bacpypes3.local.binary import BinaryInputObject

    app = Application.from_args(_sim_args())
    app.add_object(
        AnalogInputObject(
            objectIdentifier=("analog-input", 1),
            objectName="OAT",
            presentValue=72.5,
            units="degreesFahrenheit",
            description="Outside air temperature",
        )
    )
    app.add_object(
        AnalogInputObject(
            objectIdentifier=("analog-input", 2),
            objectName="zone_temp_3",
            presentValue=70.0,
            units="degreesFahrenheit",
            description="Zone 3 air temperature",
        )
    )
    app.add_object(
        BinaryInputObject(
            objectIdentifier=("binary-input", 6),
            objectName="SF_status",
            presentValue=True,
            description="Supply fan status",
        )
    )
    app.add_object(
        AnalogInputObject(
            objectIdentifier=("analog-input", 8),
            objectName="kWh_meter",
            presentValue=123456.7,
            units="kilowattHours",
            description="Building electric kWh",
        )
    )
    return app


def _close_app(app: Any) -> None:
    """bacpypes3 close() may be sync or async depending on version. Be safe."""
    try:
        result = app.close()
        if asyncio.iscoroutine(result):
            asyncio.run_coroutine_threadsafe(result, asyncio.get_event_loop())
    except BaseException as e:
        if isinstance(e, (KeyboardInterrupt, SystemExit)):
            raise
        logging.debug("close() raised %s; ignoring", e)


@pytest.fixture
async def live_simulator(skip_unless_live: None) -> Any:
    """Yields a running bacpypes3 simulator Application bound to 127.0.0.1.

    Auto-skips unless BACNET_LIVE_TESTS=1.
    """
    app = await _build_simulator()
    try:
        yield app
    finally:
        _close_app(app)


async def test_unicast_discovery_finds_simulator(live_simulator: Any) -> None:
    """Discovery + unicast Who-Is to the known simulator address yields one I-Am."""
    from bacpypes3.pdu import Address

    config = BACnetConfig(
        local_device_instance=DISC_INSTANCE,
        broadcast_address="127.0.0.1",
        bind_address=f"127.0.0.1:{DISC_PORT}",
        discovery_timeout_seconds=3,
    )
    discovery = Discovery(config)
    await discovery.start()
    try:
        target = Address(f"127.0.0.1:{SIM_PORT}")
        i_ams = await discovery._app.who_is(address=target, timeout=3.0)
        assert len(i_ams) == 1, f"Expected 1 I-Am from simulator, got {len(i_ams)}"
        assert i_ams[0].iAmDeviceIdentifier[1] == SIM_INSTANCE
    finally:
        await discovery.stop()


async def test_reader_enumerates_simulator_objects(live_simulator: Any) -> None:
    """Reader.enumerate_objects returns the 4 simulator-defined BACnet objects."""
    from bacpypes3.pdu import Address

    config = BACnetConfig(
        local_device_instance=DISC_INSTANCE,
        broadcast_address="127.0.0.1",
        bind_address=f"127.0.0.1:{DISC_PORT}",
        discovery_timeout_seconds=3,
    )
    discovery = Discovery(config)
    await discovery.start()
    try:
        target = Address(f"127.0.0.1:{SIM_PORT}")
        i_ams = await discovery._app.who_is(address=target, timeout=3.0)
        device = BACnetDevice(
            device_instance=i_ams[0].iAmDeviceIdentifier[1],
            address=str(i_ams[0].pduSource),
            vendor_id=getattr(i_ams[0], "vendorID", None),
        )

        reader = Reader(config)
        reader.attach(discovery._app)
        objects = await reader.enumerate_objects(device)
        assert len(objects) == 4
        names = {obj.object_name for obj in objects}
        assert {"OAT", "zone_temp_3", "SF_status", "kWh_meter"} == names

        oat = next(o for o in objects if o.object_name == "OAT")
        assert oat.present_value == pytest.approx(72.5)
        assert oat.units is not None and "fahrenheit" in oat.units.lower()
    finally:
        await discovery.stop()


async def test_end_to_end_tagged_topology(
    live_simulator: Any,
    brick_rules_path: Path,
    haystack_rules_path: Path,
) -> None:
    """Discovery -> Reader -> Tagger -> Topology produces correct Brick + Haystack tags."""
    from bacpypes3.pdu import Address

    config = BACnetConfig(
        local_device_instance=DISC_INSTANCE,
        broadcast_address="127.0.0.1",
        bind_address=f"127.0.0.1:{DISC_PORT}",
        discovery_timeout_seconds=3,
    )
    discovery = Discovery(config)
    await discovery.start()
    try:
        target = Address(f"127.0.0.1:{SIM_PORT}")
        i_ams = await discovery._app.who_is(address=target, timeout=3.0)
        device = BACnetDevice(
            device_instance=i_ams[0].iAmDeviceIdentifier[1],
            address=str(i_ams[0].pduSource),
            vendor_id=getattr(i_ams[0], "vendorID", None),
        )
        reader = Reader(config)
        reader.attach(discovery._app)
        objects = await reader.enumerate_objects(device)

        tagger = Tagger(brick_rules_path, haystack_rules_path)
        topology = TopologyAssembler(tagger).assemble([device], {device.device_instance: objects})

        assert len(topology.devices) == 1
        assert len(topology.tagged_objects) == 4

        by_name = {t.object.object_name: t for t in topology.tagged_objects}

        assert by_name["OAT"].brick_class == "Outside_Air_Temperature_Sensor"
        assert set(by_name["OAT"].haystack_tags) == {"point", "sensor", "outside", "air", "temp"}

        assert by_name["zone_temp_3"].brick_class == "Zone_Air_Temperature_Sensor"
        assert "zone" in by_name["zone_temp_3"].haystack_tags

        assert by_name["SF_status"].brick_class == "Supply_Fan"
        assert "fan" in by_name["SF_status"].haystack_tags

        assert by_name["kWh_meter"].brick_class == "Electrical_Power_Sensor"
        assert "energy" in by_name["kWh_meter"].haystack_tags
    finally:
        await discovery.stop()


async def test_filter_by_brick(
    live_simulator: Any,
    brick_rules_path: Path,
    haystack_rules_path: Path,
) -> None:
    """Topology.filter_by_brick returns only matching objects."""
    from bacpypes3.pdu import Address

    config = BACnetConfig(
        local_device_instance=DISC_INSTANCE,
        broadcast_address="127.0.0.1",
        bind_address=f"127.0.0.1:{DISC_PORT}",
        discovery_timeout_seconds=3,
    )
    discovery = Discovery(config)
    await discovery.start()
    try:
        target = Address(f"127.0.0.1:{SIM_PORT}")
        i_ams = await discovery._app.who_is(address=target, timeout=3.0)
        device = BACnetDevice(
            device_instance=i_ams[0].iAmDeviceIdentifier[1],
            address=str(i_ams[0].pduSource),
            vendor_id=getattr(i_ams[0], "vendorID", None),
        )
        reader = Reader(config)
        reader.attach(discovery._app)
        objects = await reader.enumerate_objects(device)

        tagger = Tagger(brick_rules_path, haystack_rules_path)
        topology = TopologyAssembler(tagger).assemble([device], {device.device_instance: objects})

        oat_only = topology.filter_by_brick("Outside_Air_Temperature_Sensor")
        assert len(oat_only.tagged_objects) == 1
        assert oat_only.tagged_objects[0].object.object_name == "OAT"
    finally:
        await discovery.stop()
