# Architecture

This is the v0.1 architecture overview. For the why behind it, see the research
note at https://habchy.dev/research/bacnet-msi-semantic-gap.

## Module map

```
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│   discovery.py   │   │     reader.py    │   │     tagger.py    │
│  Who-Is / I-Am   │   │  ReadProperty    │   │  rule-based      │
│  DeviceCache     │   │  + enumerate     │   │  Brick + Haystack│
└────────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘
         │                      │                      │
         │                      │                      │
         └──────────────┬───────┴──────────────┬───────┘
                        │                      │
                ┌───────▼──────────────────────▼─────────┐
                │              topology.py               │
                │  TopologyAssembler => Topology graph   │
                └────────────────────┬───────────────────┘
                                     │
                              ┌──────▼──────┐
                              │  server.py  │
                              │ FastMCP +   │
                              │ four tools  │
                              └─────────────┘
```

## Data flow

1. **Discovery** broadcasts a Who-Is request via bacpypes3, harvests I-Am
   responses into a `DeviceCache`. One round per `refresh()`.
2. **Reader** takes the cached devices and runs `ReadProperty` calls per
   device: object-list, then per-object name + description + units +
   present-value.
3. **Tagger** applies YAML-defined Brick + Haystack rules against each
   `BACnetObject`, producing `TaggedObject` instances.
4. **TopologyAssembler** stitches devices + tagged objects into a `Topology`.
5. **Server** wires the four MCP tools to topology accessors and serves over
   stdio or streamable HTTP via FastMCP.

## Why this layering

The four modules below `server.py` have one job each. Discovery owns the
broadcast, Reader owns the property polling, Tagger owns the semantic mapping,
Topology owns the assembly. Each is testable in isolation (Tagger and Topology
have no BACnet dependency at all; Discovery and Reader use bacpypes3 but
delegate to a real or simulated network).

The Server module is the only one that knows about FastMCP. Swapping in a
different agent-protocol wrapper later (HTTP REST, gRPC, plain JSON over a
socket) only changes server.py.

## Rule engine semantics

For each object, the tagger evaluates rules in file order. First match wins.
A rule matches when:

1. The regex `pattern` matches the object's name (regex `re.search`, so
   anchor with `\b` or `^/$` if you need full-name match)
2. If the rule has `units`, at least one entry is a substring (case-
   insensitive) of the object's units field
3. If the rule has `object_types`, the object's BACnet object type is in the list

Rules without `units` or `object_types` constraints match any object whose name
matches the pattern. The first-match-wins ordering means more specific rules
should appear before more general ones in the YAML file. The starter rule
library follows this convention; the generic temperature catch-all at the
bottom matches anything left over.

## v0.1 trade-offs

- **Polling, not COV.** Simpler protocol surface; COV is v0.2.
- **One broadcast domain.** Multi-site federation is v0.3.
- **No write path.** Compliance footprint stays tight at v0.1.
- **Single bacpypes3 Application shared by Discovery and Reader.** Reduces
  socket churn but tightly couples the two modules. v0.2 will likely hoist
  the Application to a shared resource managed by the BrickBACnetServer.
- **Topology refresh on tool call.** Acceptable for v0.1 latency; v0.2 will
  run a background polling task and serve cached topology to MCP tools.

## Testing surface

- `tests/test_tagger.py`: pure-Python, no bacpypes3 dependency
- `tests/test_topology.py`: pure-Python, no bacpypes3 dependency
- `tests/test_config.py`: pure-Python, no bacpypes3 dependency
- `tests/test_integration.py` (planned v0.1 follow-on): end-to-end against
  the bacpypes3 simulator at `scripts/run_simulator.py`. Gated by
  `BACNET_LIVE_TESTS=1` environment variable so CI without a BACnet stack
  installed still passes the unit suite.

## Adding new object types

The set of supported BACnet object types is centralized in
`reader.SUPPORTED_OBJECT_TYPES`. To add a new type (Loop, Accumulator,
Trend Log, etc.):

1. Add the canonical type string to `SUPPORTED_OBJECT_TYPES`
2. Add type-specific present-value coercion in `_coerce_present_value` if
   the object's value is not a primitive
3. Add starter rules in `brick_rules.yaml` and `haystack_rules.yaml` if
   the type carries semantic information worth surfacing
4. Add a unit test in `tests/test_tagger.py` validating the new rules

## Adding a new MCP tool

1. Add an `async def` method to `BrickBACnetServer` returning a serializable
   dict or list
2. Wire it into `build_mcp(server)` with a `@mcp.tool()` decorator
3. Document the tool's input/output schema in the README and in this file

Avoid tools that bypass the Topology layer; they will not benefit from caching
and may diverge in semantics from the canonical state.
