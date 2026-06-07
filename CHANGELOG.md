# Changelog

All notable changes to brick-bacnet-mcp are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

(no changes yet since v0.1.0a0)

## [0.1.0a0] - 2026-06-06

First public alpha. Read-only BACnet/IP gateway exposing Brick + Project Haystack tagged building topology to LLM agents via MCP.

### Added
- Rule-based Brick + Haystack semantic tagger with extensible YAML rule files
- Starter rule library: 30+ Brick rules, 25+ Haystack rules covering common HVAC, lighting, metering, and equipment patterns
- Pydantic data models for BACnetDevice, BACnetObject, TaggedObject, Topology
- BACnet/IP discovery (Who-Is / I-Am) via bacpypes3, with DeviceCache
- Property reader: object enumeration + present-value + units + description
- Topology assembler stitching devices + tagged objects into a queryable graph
- FastMCP server exposing four MCP tools: list_devices, list_objects, get_object_value, get_tagged_topology
- Coverage diagnostic CLI: `brick-bacnet-mcp --coverage-report --config config.yaml` prints match-rate by format, top unmatched object names, and top rule hits (use `--top-unmatched N` to change list length)
- BACnet simulator for integration testing (scripts/run_simulator.py)
- 39 unit tests + 4 integration tests (integration suite gated by BACNET_LIVE_TESTS=1 env var)
- Documentation: README, ARCHITECTURE, RULES, EXAMPLES, CONTRIBUTING

### Compatibility
- Python 3.11+
- bacpypes3 0.0.100+ (tested on 0.0.106)
- fastmcp 2.0+

### Known limitations (v0.1 by design)
- Read-only. No WriteProperty path.
- Single broadcast domain. No multi-site federation.
- No COV subscription support. Polling only.
- No BACnet/SC. BACnet/IP only.
- Flat topology grouped by device_instance. No equipment-hierarchy linkage (relevant for Niagara JACE deployments where one device_instance hosts many AHUs).
- No authentication layer. Designed for trusted local-network deployment.
- Starter rule library targets US-style English object-name conventions; non-Anglo or vendor-specific naming will need rule extensions.

### Notes
- Honest first-run coverage expectation for an uncalibrated mixed-vendor MSI portfolio: 30-50%. Use `--coverage-report` to see what's unmatched, then extend `src/brick_bacnet_mcp/rules/*.yaml` for your naming convention.
- Research note this implementation came out of: https://habchy.dev/research/bacnet-msi-semantic-gap
