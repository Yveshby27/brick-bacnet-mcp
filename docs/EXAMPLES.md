# Examples

Three worked examples ship in `examples/`. Each is copy-paste runnable. None
hand-wave a step.

## 01: Discover and list

[examples/01_discover_and_list.py](../examples/01_discover_and_list.py)

Runs the full discovery + enumeration + tagging cycle once and prints a
topology summary, the device list, and the first 10 tagged objects. Good first
sanity check after installing the package.

```bash
python examples/01_discover_and_list.py --config examples/config_example.yaml
```

Expected output shape:

```
=== Topology summary ===
Devices:          5
Tagged objects:   20
Brick classes:    AHU, Outside_Air_Temperature_Sensor, Supply_Air_Temperature_Sensor, ...
Haystack tag set: ahu, air, chilled, equip, outside, point, sensor, supply, temp, ...

=== Devices ===
  Device 200001 @ 192.168.1.10:47808
  Device 200002 @ 192.168.1.11:47808
  ...

=== Sample tagged objects (first 10) ===
  analog-input:1@200001                 name=OAT brick=Outside_Air_Temperature_Sensor haystack=[point,sensor,outside,air,temp]
  ...
```

## 02: Tag one AHU

[examples/02_tag_one_ahu.py](../examples/02_tag_one_ahu.py)

Filters the topology to the first AHU and walks every tagged object on that
device. Surfaces untagged objects as a rule-library-gap signal.

```bash
python examples/02_tag_one_ahu.py --config examples/config_example.yaml
```

Expected output shape:

```
=== AHU equipment object found on device 200001 ===
  Name: AHU_1

=== All tagged objects on device 200001 (7 total) ===
                   OAT =     72.5 degF       brick=Outside_Air_Temperature_Sensor   hs=[point,sensor,outside,air,temp]
                   DAT =     55.0 degF       brick=Supply_Air_Temperature_Sensor    hs=[point,sensor,discharge,air,temp]
                   ...
```

If any objects show `brick=(untagged)`, the script prints them at the bottom
as candidates for new rule entries.

## 03: Query via Claude Desktop

[examples/03_query_via_claude_desktop.md](../examples/03_query_via_claude_desktop.md)

Walks through wiring the server into Claude Desktop's MCP config and running
real natural-language queries against your network. Includes troubleshooting
patterns for common setup issues.

## Running the simulator

When you do not have a real BACnet network reachable, use the bundled
simulator:

```bash
pip install bacpypes3
python scripts/run_simulator.py --fixtures tests/fixtures/simulator_devices.yaml
```

The simulator spins up five virtual devices (AHU, two VAV boxes, central
plant, meter) and listens for Who-Is broadcasts. Run any of the examples
above in another terminal pointing the same config at `127.0.0.1` and you get
a deterministic test surface.
