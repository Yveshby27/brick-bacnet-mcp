# v0.1.0a0

First public alpha. A read-only BACnet/IP gateway that exposes building automation point databases to LLM agents via the Model Context Protocol, with Brick + Project Haystack semantic tagging applied at ingest.

## Why this exists

Vendor agentic platforms (JCI OpenBlue, Honeywell Forge, Siemens Building X, Tridium Niagara 5) ship a semantic-AI layer that only works inside their own controls portfolios. Independent master systems integrators (MSIs) running mixed-vendor 5-50 building portfolios have BACnet point databases but no clean way to expose them in semantic-tagged form to external LLM agents.

This gateway is one answer to that gap. It sits beside [ezhuk/bacnet-mcp](https://github.com/ezhuk/bacnet-mcp), which does raw protocol-layer BACnet read/write with no semantic normalization. This project adds the Brick + Haystack tagging step at ingest and restricts the v0.1 surface to read-only for a tighter compliance footprint.

Full research note: https://habchy.dev/research/bacnet-msi-semantic-gap

## What you get in v0.1

- BACnet/IP discovery on the local broadcast domain
- Object enumeration across AI, AO, AV, BI, BO, BV, MSI, MSO, MSV, Schedule, Calendar
- Present-value + units + description reading
- Brick class + Haystack tag assignment via extensible YAML rules
- Four MCP tools exposed over stdio (Claude Desktop, Cursor) or streamable HTTP (hosted MCP hosts):
  - `list_devices` returns the discovered BACnet devices with metadata
  - `list_objects` returns tagged objects for a specific device
  - `get_object_value` returns the current present-value and tags for one object
  - `get_tagged_topology` returns the full or filtered tagged-topology graph
- Coverage diagnostic CLI to inspect rule-library match rate against your network
- BACnet simulator for offline integration testing

## Install

```bash
pip install brick-bacnet-mcp
```

Python 3.11 or later required.

## Quick start

Create `config.yaml`:

```yaml
bacnet:
  local_device_instance: 555001
  broadcast_address: 192.168.1.255
  polling_interval_seconds: 30
rules:
  brick: src/brick_bacnet_mcp/rules/brick_rules.yaml
  haystack: src/brick_bacnet_mcp/rules/haystack_rules.yaml
mcp:
  transport: stdio
log_level: INFO
```

Run the MCP server:

```bash
brick-bacnet-mcp --config config.yaml
```

Or wire into Claude Desktop:

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

## Before you decide it's broken: run the coverage report

The starter rule library targets common US-style BACnet object-name conventions (OAT, DAT, ZNT, CHWS, AHU-1, etc.). Real-world mixed-vendor portfolios use wildly different naming. Before assuming the tool is broken or working, run:

```bash
brick-bacnet-mcp --coverage-report --config config.yaml
```

This does one discover + enumerate + tag cycle against your network and prints:

- Total objects discovered
- Brick / Haystack match percentages
- Top 20 most-common object names that no rule matched
- Top 10 hottest rules

Use the unmatched list to extend the YAML rule files for your naming convention. A first-run match rate of 30-50% is normal for an uncalibrated portfolio; 70%+ is what you'd want before relying on the tagged topology for LLM queries. The rule files are plain YAML, regex-driven, first-match-wins; see [docs/RULES.md](../docs/RULES.md) for the grammar.

## Deliberate v0.1 scope (what this is NOT)

- Not a write path. WriteProperty is intentionally out of v0.1 for compliance-surface reasons.
- Not a Niagara station integration. Fox protocol / Niagara module wrapping is a separate design.
- Not an FDD or analytics platform. The tagged topology is meant to be consumed by downstream FDD or LLM-agent workflows. This gateway is the ingest layer only.
- Not a UI. Output is MCP only.
- Not BACnet/SC. v0.1 is BACnet/IP only.
- Not 223P full schema parity. v0.1 uses simplified Brick + Haystack mapping.
- Not multi-site federated. v0.1 handles one broadcast domain at a time.
- Not authenticated. v0.1 runs in a trusted local-network environment.

The v0.2 roadmap (COV subscription, BACnet/SC, 223P, SkySpark passthrough, equipment-hierarchy linkage) is conditional on sustained-use signal from v0.1. None of it is committed pre-signal.

## Tested against

- Python 3.13.9 (also targets 3.11, 3.12)
- bacpypes3 0.0.106
- fastmcp 2.x
- 39 unit tests + 4 integration tests against the included simulator

## How to extend the rule library

Most useful PRs in this period are rule library additions for naming conventions the starter set misses. Run `--coverage-report` against your building, copy the most-common unmatched names, draft a YAML rule, run the test suite, open a PR. The grammar is documented in [docs/RULES.md](../docs/RULES.md).

## Known structural gaps to be honest about

- TaggedObject has no `parent_equipment` field. Real Niagara JACE deployments host many AHUs under one device_instance; grouping by device_instance alone conflates them. Equipment-prefix detection is a v0.2 candidate.
- The rule library is starter-shaped, not vendor-comprehensive. JCI Metasys, Tridium Niagara, Siemens Apogee, Honeywell BMS, and Distech each have characteristic naming conventions that warrant overlay rule files. None ship in v0.1; contributions welcome.

## Acknowledgments

- [ezhuk/bacnet-mcp](https://github.com/ezhuk/bacnet-mcp) for the prior-art MCP + BACnet integration this project builds beside
- [bacpypes3](https://github.com/JoelBender/bacpypes3) for the BACnet protocol library
- [Project Haystack](https://project-haystack.org/) for the Haystack tagging vocabulary
- [Brick consortium](https://brickschema.org/) for the Brick schema
- MSI voices whose published positioning the research builds on: Brian Turner (Adaptive Buildings), Marc Petock (Lynxspring), Tom Shircliff and Rob Murchison (Intelligent Buildings LLC), Jim Meacham (Altura Associates), Therese Sullivan (BuildingContext), Alper Üzmezler (BASSG)

## License

MIT.

## Feedback

This is a v0.1 alpha published as a research instrument. The kill-gate test window is 14-21 days from publish. Issues, PRs, design-partner inquiries, and "I tried it on my building and X% of points tagged" reports are all genuinely useful. Open an issue or email yves.habchy@gmail.com.
