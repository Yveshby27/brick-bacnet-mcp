"""Loopback end-to-end demo for Windows.

Mirrors tests/test_integration.py: uses a unicast Who-Is against the
simulator on 127.0.0.1:47808 because Windows blocks broadcast on the
loopback adapter. Drives the same Discovery + Reader + Tagger +
TopologyAssembler classes the production server uses.

Run AFTER starting scripts/run_simulator.py in another terminal:

    python scripts/loopback_demo.py
"""

from __future__ import annotations

import asyncio
import logging
from argparse import Namespace

from brick_bacnet_mcp.config import BACnetConfig, RulesConfig
from brick_bacnet_mcp.discovery import Discovery
from brick_bacnet_mcp.models import BACnetDevice
from brick_bacnet_mcp.reader import Reader
from brick_bacnet_mcp.tagger import Tagger, compute_coverage
from brick_bacnet_mcp.topology import TopologyAssembler


SIM_ADDR = "127.0.0.1:47808"
# 47810, not 47809. The Claude Desktop MCP server uses 47809 by default
# (per the example config.yaml). Using a different port here lets the
# demo runbook run the MCP server and this loopback script side by side
# without the OS rejecting the second bind.
GATEWAY_PORT = 47810
GATEWAY_INSTANCE = 555002


async def unicast_discover(discovery: Discovery) -> list[BACnetDevice]:
    """Replace GlobalBroadcast() with a unicast Who-Is to the simulator address."""
    from bacpypes3.pdu import Address

    i_ams = await discovery._app.who_is(
        address=Address(SIM_ADDR),
        timeout=5,
    )
    devices: list[BACnetDevice] = []
    for i_am in i_ams:
        device_instance = i_am.iAmDeviceIdentifier[1]
        device = BACnetDevice(
            device_instance=device_instance,
            address=str(i_am.pduSource),
            vendor_id=getattr(i_am, "vendorID", None),
        )
        discovery.cache.upsert(device)
        devices.append(device)
    return devices


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    bacnet_cfg = BACnetConfig(
        local_device_instance=GATEWAY_INSTANCE,
        broadcast_address="127.0.0.1",
        bind_address=f"0.0.0.0:{GATEWAY_PORT}",
        polling_interval_seconds=30,
        discovery_timeout_seconds=5,
    )
    rules_cfg = RulesConfig(
        brick="src/brick_bacnet_mcp/rules/brick_rules.yaml",
        haystack="src/brick_bacnet_mcp/rules/haystack_rules.yaml",
    )

    tagger = Tagger(brick_rules_path=rules_cfg.brick, haystack_rules_path=rules_cfg.haystack)
    discovery = Discovery(bacnet_cfg)
    reader = Reader(bacnet_cfg)
    assembler = TopologyAssembler(tagger)

    await discovery.start()
    reader.attach(discovery._app)
    try:
        print("\n>>> STEP 1: unicast Who-Is to simulator at", SIM_ADDR)
        devices = await unicast_discover(discovery)
        print(f"    discovered {len(devices)} device(s)")
        for d in devices:
            print(f"      device {d.device_instance} @ {d.address} vendor_id={d.vendor_id}")

        print("\n>>> STEP 2: enumerate objects per device + ReadProperty")
        objects_by_device: dict[int, list] = {}
        for d in devices:
            objs = await reader.enumerate_objects(d)
            objects_by_device[d.device_instance] = objs
            print(f"    device {d.device_instance}: {len(objs)} objects")

        print("\n>>> STEP 3: assemble + tag")
        topology = assembler.assemble(devices, objects_by_device)

        summary = topology.to_summary()
        print("\n=== Topology summary ===")
        print(f"  Devices:          {summary['device_count']}")
        print(f"  Tagged objects:   {summary['object_count']}")
        print(f"  Brick classes:    {', '.join(summary['brick_classes']) or '(none)'}")
        print(f"  Haystack tag set: {', '.join(sorted(summary['haystack_tag_set'])) or '(none)'}")

        print("\n=== All tagged objects ===")
        for t in topology.tagged_objects:
            o = t.object
            brick = t.brick_class or "(untagged)"
            tags = ",".join(t.haystack_tags) if t.haystack_tags else "(untagged)"
            val = o.present_value if o.present_value is not None else "-"
            unit = o.units or "-"
            print(
                f"  {o.object_name!s:>32} = {val!s:>8} {unit:<10} "
                f"brick={brick:<42} hs=[{tags}]"
            )

        print("\n=== Coverage report ===")
        report = compute_coverage(topology.tagged_objects, top_n=10)
        print(report.render_text())

        print("\n=== Filter demo: brick=AHU ===")
        ahu_topo = topology.filter_by_brick("AHU")
        print(f"  matched {len(ahu_topo.tagged_objects)} objects")
        for t in ahu_topo.tagged_objects[:5]:
            print(f"    {t.object.object_name}  brick={t.brick_class}")

        print("\n=== Filter demo: haystack=['temp', 'sensor'] ===")
        temp_topo = topology.filter_by_haystack("temp", "sensor")
        print(f"  matched {len(temp_topo.tagged_objects)} objects")
        for t in temp_topo.tagged_objects[:5]:
            print(f"    {t.object.object_name}  hs={t.haystack_tags}")
    finally:
        await discovery.stop()


if __name__ == "__main__":
    asyncio.run(main())
