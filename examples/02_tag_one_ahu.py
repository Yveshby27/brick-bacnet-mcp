"""Example 02: filter the topology to one AHU and walk its tagged objects.

Demonstrates the `filter_by_brick` operator on Topology. After discovery, this
script extracts the first AHU it finds plus its child sensor / actuator
objects, prints the Brick class and Haystack tag set per object, and surfaces
which objects matched a rule vs which fell through as untagged.

Run against the bacpypes3 simulator:

    python scripts/run_simulator.py --fixtures tests/fixtures/simulator_devices.yaml &
    python examples/02_tag_one_ahu.py --config examples/config_example.yaml
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

        # Find an AHU device by Brick equipment tag
        ahu_objects = [
            t for t in topology.tagged_objects if t.brick_class == "AHU"
        ]
        if not ahu_objects:
            print("No object tagged as Brick:AHU was found in the topology.")
            print("Check your rule files or the discovered device names.")
            return

        ahu_device_id = ahu_objects[0].object.device_instance
        print(f"\n=== AHU equipment object found on device {ahu_device_id} ===")
        print(f"  Name: {ahu_objects[0].object.object_name}")

        # Get all tagged objects on that device
        same_device = [
            t for t in topology.tagged_objects if t.object.device_instance == ahu_device_id
        ]
        print(f"\n=== All tagged objects on device {ahu_device_id} ({len(same_device)} total) ===")
        for t in same_device:
            o = t.object
            brick = t.brick_class or "(untagged)"
            hs_tags = ",".join(t.haystack_tags) if t.haystack_tags else "(untagged)"
            value = o.present_value if o.present_value is not None else "-"
            unit = o.units or "-"
            print(
                f"  {o.object_name!s:>22} = {value!s:>8} {unit:<10} "
                f"brick={brick:<40} hs=[{hs_tags}]"
            )

        # Highlight untagged objects (rule-library gap signal)
        untagged = [t for t in same_device if t.brick_class is None]
        if untagged:
            print(f"\n=== {len(untagged)} untagged objects on this device ===")
            print("Consider adding rules for these patterns to brick_rules.yaml / haystack_rules.yaml")
            for t in untagged:
                print(f"  name={t.object.object_name} type={t.object.object_type} units={t.object.units}")
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
