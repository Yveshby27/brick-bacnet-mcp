# brick-bacnet-mcp

A read-only BACnet/IP gateway that exposes building automation point databases to LLM agents via MCP, with Brick + Project Haystack semantic tagging at ingest time.

## Why this exists

The research note this implementation came out of is at https://habchy.dev/research/bacnet-msi-semantic-gap. A version of the same article is also published at AutomatedBuildings.com (link will be added when the AB.com edition goes live).

Short version: vendor agentic platforms (JCI OpenBlue, Honeywell Forge, Siemens Building X, Tridium Niagara 5) keep their semantic AI layer inside their own controls portfolios. Independent MSIs running mixed-vendor 5-50 building portfolios have BACnet point databases but no clean way to expose them in semantic-tagged form to external LLM agents. This gateway is one answer to that gap.

[ezhuk/bacnet-mcp](https://github.com/ezhuk/bacnet-mcp) does read and write at the BACnet protocol layer with no semantic normalization. This project sits beside it: it adds the Brick + Haystack tagging step at ingest and restricts the v0.1 surface to read-only for a tighter compliance footprint.

## What it does (v0.1)

- Discovers BACnet/IP devices on the local broadcast domain (Who-Is, I-Am)
- Enumerates objects per device (AI, AO, AV, BI, BO, BV, MSI, MSO, MSV, Schedule, Calendar)
- Reads present-value, units, and description per object
- Tags each object with a Brick class and a Haystack tag set using rule-based mapping (rules are extensible via YAML)
- Exposes the tagged topology to any MCP host via four tools: `list_devices`, `list_objects`, `get_object_value`, `get_tagged_topology`

## What it isn't (v0.1)

- Not a write path. WriteProperty is intentionally out of v0.1 for the compliance-surface reasons noted in the research article.
- Not a Niagara station integration. Fox protocol / Niagara module wrapping is a separate design.
- Not an FDD or analytics platform. The tagged topology is meant to be consumed by downstream FDD or LLM-agent workflows. This gateway is the ingest layer only.
- Not a UI. Output is MCP only. Pair it with Claude Desktop, Cursor, or any other MCP host.
- Not BACnet/SC. v0.1 is BACnet/IP only. Secure Connect is a v0.2 consideration.
- Not 223P full schema parity. v0.1 uses the simplified Brick + Haystack mapping. Full 223P entity model is a v0.2 candidate.
- Not multi-site federated. v0.1 handles one broadcast domain at a time.
- Not authenticated. v0.1 runs in a trusted local network environment.

## Install

```bash
pip install brick-bacnet-mcp
```

Or from source:

```bash
git clone https://github.com/Yveshby27/brick-bacnet-mcp
cd brick-bacnet-mcp
pip install -e .
```

Python 3.11 or later required.

## Quick start

Create a config file `config.yaml`:

```yaml
bacnet:
  local_device_instance: 555001
  broadcast_address: 192.168.1.255
  polling_interval_seconds: 30
rules:
  brick: src/brick_bacnet_mcp/rules/brick_rules.yaml
  haystack: src/brick_bacnet_mcp/rules/haystack_rules.yaml
mcp:
  transport: stdio  # or "http" for a hosted MCP host
  http_port: 8080   # only if transport == http
log_level: INFO
```

Run the MCP server:

```bash
brick-bacnet-mcp --config config.yaml
```

Or wire it into Claude Desktop:

```json
{
  "mcpServers": {
    "brick-bacnet": {
      "command": "brick-bacnet-mcp",
      "args": ["--config", "/path/to/config.yaml"]
    }
  }
}
```

## Example interaction

With the server running and the simulator active (or a real BACnet/IP network reachable), an MCP-capable LLM can run:

> User: List all the air-handling units across the building.
>
> Agent (via MCP tool): calls `get_tagged_topology(filter="brick:AHU")`
>
> Agent response: Found 3 AHUs. AHU-1 has 5 child points (discharge_air_temp, return_air_temp, supply_fan_status, mixed_air_damper_position, outside_air_temp). AHU-2 ... AHU-3 ...

See [examples/](examples/) for full runnable scripts.

## Checking coverage on your building

The starter rule library targets common US-style object-name conventions (OAT, DAT, ZNT, CHWS, AHU-1, etc.). Real-world mixed-vendor portfolios use wildly different naming. Before assuming the tool is broken or working, run:

```bash
brick-bacnet-mcp --coverage-report --config config.yaml
```

This does one discover + enumerate + tag cycle against your network and prints:

- Total objects discovered
- Brick / Haystack match percentages
- Top 20 most-common object names that no rule matched (use `--top-unmatched N` for a different count)
- Top 10 hottest rules

Use the unmatched list to extend the YAML rule files for your naming convention. A first-run match rate of 30-50% is normal for a portfolio that hasn't been calibrated yet; 70%+ is what you'd want before relying on the tagged topology for LLM queries.

## How tagging works

The tagger applies YAML-defined rules to map BACnet object names and units to Brick classes and Haystack tag sets. The default rule set covers about 50 common HVAC, lighting, and metering object-name patterns. Users override or extend by editing `src/brick_bacnet_mcp/rules/brick_rules.yaml` and `haystack_rules.yaml` locally.

Example rule (Brick):

```yaml
- pattern: '(?i)^(oat|outside_air_temp|outsideair)$'
  units: ['degF', 'degC', '°F', '°C']
  brick_class: 'Outside_Air_Temperature_Sensor'
```

See [docs/RULES.md](docs/RULES.md) for the rule grammar and override conventions.

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Short version:

- `discovery.py` runs Who-Is broadcast, captures I-Am responses, caches device metadata
- `reader.py` enumerates the object list per device and polls present-value at the configured interval
- `tagger.py` applies Brick + Haystack rules to each enumerated object
- `topology.py` assembles the tagged objects into a queryable graph
- `server.py` exposes four MCP tools over stdio or streamable HTTP

## Roadmap

v0.1 is a research instrument. The roadmap below is what the research article flagged as worth doing next IF v0.1 gets enough sustained-use signal to justify extending. None of it is committed pre-signal.

- v0.2: COV subscription support, BACnet/SC, 223P full schema parity, SkySpark / FIN Haystack-store passthrough
- v0.3+: Optional write path behind explicit opt-in, multi-site federation, authentication layer for non-local deployment

## Acknowledgments

- [ezhuk/bacnet-mcp](https://github.com/ezhuk/bacnet-mcp) for the prior-art MCP + BACnet integration that this project builds beside
- [bacpypes3](https://github.com/JoelBender/bacpypes3) for the BACnet protocol library
- [Project Haystack](https://project-haystack.org/) for the Haystack tagging vocabulary and community
- [Brick consortium](https://brickschema.org/) for the Brick schema
- The named MSI voices whose published positioning this research builds on: Brian Turner (Adaptive Buildings), Marc Petock (Lynxspring), Tom Shircliff and Rob Murchison (Intelligent Buildings LLC), Jim Meacham (Altura Associates), Therese Sullivan (BuildingContext), Alper Üzmezler (BASSG)

## License

MIT. See [LICENSE](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). PRs welcome for rule library extensions, documentation, examples, and test coverage. Larger changes (write path, non-BACnet protocol support, UI, FDD logic) are out of v0.1 scope. Open an issue first to discuss before submitting a PR.
