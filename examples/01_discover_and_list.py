"""Example 01: discover + enumerate + tag, print a topology summary.

Run against the bacpypes3 simulator (or a real BACnet/IP network):

    python examples/01_discover_and_list.py --config examples/config_example.yaml

Requires bacpypes3 installed. If you do not have a live BACnet network, start
the simulator first:

    python scripts/run_simulator.py --fixtures tests/fixtures/simulator_devices.yaml
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from brick_bacnet_mcp.config import load_config
from brick_bacnet_mcp.server import BrickBACnetServer


async def main_async(config_path: Path) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    config = load_config(config_path)
    server = BrickBACnetServer(config)
    await server.start()
    try:
        topology = await server.refresh()
        print("\n=== Topology summary ===")
        summary = topology.to_summary()
        print(f"Devices:          {summary['device_count']}")
        print(f"Tagged objects:   {summary['object_count']}")
        print(f"Brick classes:    {', '.join(summary['brick_classes']) or '(none)'}")
        print(f"Haystack tag set: {', '.join(sorted(summary['haystack_tag_set'])) or '(none)'}")

        print("\n=== Devices ===")
        for device in topology.devices:
            print(f"  Device {device.device_instance} @ {device.address}")

        print("\n=== Sample tagged objects (first 10) ===")
        for tobj in topology.tagged_objects[:10]:
            o = tobj.object
            tags = ",".join(tobj.haystack_tags) if tobj.haystack_tags else "-"
            brick = tobj.brick_class or "-"
            print(
                f"  {o.object_type}:{o.object_instance}@{o.device_instance:>6} "
                f"name={o.object_name!s:>20} brick={brick} haystack=[{tags}]"
            )
    finally:
        await server.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("examples/config_example.yaml"),
        help="Path to config YAML",
    )
    args = parser.parse_args()
    asyncio.run(main_async(args.config))


if __name__ == "__main__":
    main()
