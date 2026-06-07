# Example 03: Querying brick-bacnet-mcp via Claude Desktop

This worked example walks through wiring the server into Claude Desktop and
running a real natural-language query against your BACnet network (real or
simulated).

## Prerequisites

- Claude Desktop installed: https://claude.ai/download
- brick-bacnet-mcp installed: `pip install brick-bacnet-mcp`
- A reachable BACnet network OR the bundled simulator running:
  ```bash
  python scripts/run_simulator.py --fixtures tests/fixtures/simulator_devices.yaml
  ```

## Step 1: create your config

Copy `examples/config_example.yaml` somewhere stable and edit it for your network:

```yaml
bacnet:
  local_device_instance: 555001
  broadcast_address: 192.168.1.255   # adjust to your subnet
  bind_address: 0.0.0.0:47808
  polling_interval_seconds: 30
  discovery_timeout_seconds: 5
rules:
  brick: src/brick_bacnet_mcp/rules/brick_rules.yaml
  haystack: src/brick_bacnet_mcp/rules/haystack_rules.yaml
mcp:
  transport: stdio
log_level: INFO
```

Save as `~/.config/brick-bacnet-mcp/config.yaml` (Linux / macOS) or
`%APPDATA%\brick-bacnet-mcp\config.yaml` (Windows).

## Step 2: register the server with Claude Desktop

Open Claude Desktop's MCP servers config:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Add (or merge into the existing `mcpServers` block):

```json
{
  "mcpServers": {
    "brick-bacnet": {
      "command": "brick-bacnet-mcp",
      "args": ["--config", "/absolute/path/to/your/config.yaml"]
    }
  }
}
```

Restart Claude Desktop. The server's tools should appear in the tool list.

## Step 3: run a few queries

Open a chat and try:

> List all the air-handling units across the building.

Claude will call `get_tagged_topology(filter_brick="AHU")` and respond with the
matching equipment.

> Which zones are currently above their setpoint?

Claude will call `get_tagged_topology(filter_haystack=["zone", "temp"])` and
`get_tagged_topology(filter_haystack=["zone", "sp"])` and reason about the
delta per zone.

> What is the present value of OAT?

Claude will call `list_devices`, then `list_objects` per device, locate the
object with Brick class `Outside_Air_Temperature_Sensor`, and return the
current present-value plus its units.

## Troubleshooting

**No devices discovered**

- Confirm `broadcast_address` is reachable (try `ping` from the host running
  the server)
- Increase `discovery_timeout_seconds` for slow networks
- Run `python examples/01_discover_and_list.py` from the same host as a
  diagnostic
- If using the simulator, confirm `scripts/run_simulator.py` is still running

**Tool calls error out**

- Check the server's log at the level set in `config.yaml log_level`
- Confirm the rule file paths in `config.yaml` resolve from the working
  directory Claude Desktop launches the server in (use absolute paths if in
  doubt)

**Objects show up but are untagged**

- The default rule library covers about 50 common patterns. Sites with vendor-
  specific naming conventions will have unmatched objects.
- Copy `src/brick_bacnet_mcp/rules/brick_rules.yaml` and
  `haystack_rules.yaml` to local copies, point your config at the local copies,
  and add rules for your site's patterns.
- See [docs/RULES.md](../docs/RULES.md) for the rule grammar.
