"""MCP server exposing tagged BACnet topology to LLM agents.

Four tools:
  - list_devices()                        full device list with metadata
  - list_objects(device_instance)         tagged objects for one device
  - get_object_value(device_instance, object_type, object_instance) read present-value
  - get_tagged_topology(filter)           full or filtered topology graph

Transport: stdio for local MCP hosts (Claude Desktop, Cursor) or streamable HTTP
for hosted MCP hosts. Configured via Config.mcp.

v0.1 assumes a single broadcast domain. The server holds a single Discovery +
Reader + TopologyAssembler triad; refresh cadence is the polling interval from
config.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from brick_bacnet_mcp.config import Config
from brick_bacnet_mcp.discovery import Discovery
from brick_bacnet_mcp.models import Topology
from brick_bacnet_mcp.reader import Reader
from brick_bacnet_mcp.tagger import CoverageReport, Tagger, compute_coverage
from brick_bacnet_mcp.topology import TopologyAssembler

logger = logging.getLogger(__name__)


class BrickBACnetServer:
    """Stateful container wiring Discovery, Reader, Tagger, and TopologyAssembler.

    The MCP transport is wrapped in `run()`. Tools delegate to the assembled
    topology snapshot, which is refreshed on each tool call (v0.1) or via a
    background polling task (v0.2 candidate).
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self.tagger = Tagger(
            brick_rules_path=config.rules.brick,
            haystack_rules_path=config.rules.haystack,
        )
        self.discovery = Discovery(config.bacnet)
        self.reader = Reader(config.bacnet)
        self.assembler = TopologyAssembler(self.tagger)
        self._topology: Topology | None = None

    async def start(self) -> None:
        await self.discovery.start()
        # Attach the same bacpypes Application to the reader for socket sharing
        self.reader.attach(self.discovery._app)

    async def stop(self) -> None:
        await self.discovery.stop()

    async def refresh(self) -> Topology:
        """One full discover + enumerate + tag cycle.

        v0.1: synchronous on tool call. v0.2 may run this in a background task
        on `polling_interval_seconds` and have tools serve cached state.
        """
        devices = await self.discovery.discover_once()
        objects_by_device: dict[int, list] = {}
        for dev in devices:
            objects_by_device[dev.device_instance] = await self.reader.enumerate_objects(dev)
        self._topology = self.assembler.assemble(devices, objects_by_device)
        return self._topology

    async def _ensure_topology(self) -> Topology:
        # v0.1: refresh on every tool call. Caching would freeze present_value
        # reads and miss devices that come online after the first call. v0.2
        # candidate: TTL cache that invalidates after polling_interval_seconds.
        return await self.refresh()

    # ---- MCP tool implementations ----

    async def list_devices(self) -> list[dict[str, Any]]:
        topo = await self._ensure_topology()
        return [d.model_dump() for d in topo.devices]

    async def list_objects(self, device_instance: int) -> list[dict[str, Any]]:
        topo = await self._ensure_topology()
        matches = [
            t.model_dump()
            for t in topo.tagged_objects
            if t.object.device_instance == device_instance
        ]
        return matches

    async def get_object_value(
        self, device_instance: int, object_type: str, object_instance: int
    ) -> dict[str, Any] | None:
        topo = await self._ensure_topology()
        for t in topo.tagged_objects:
            o = t.object
            if (
                o.device_instance == device_instance
                and o.object_type == object_type
                and o.object_instance == object_instance
            ):
                return {
                    "present_value": o.present_value,
                    "units": o.units,
                    "object_name": o.object_name,
                    "description": o.description,
                    "brick_class": t.brick_class,
                    "haystack_tags": t.haystack_tags,
                    "haystack_kind": t.haystack_kind,
                    "haystack_unit": t.haystack_unit,
                }
        return None

    async def get_tagged_topology(
        self, filter_brick: str | None = None, filter_haystack: list[str] | None = None
    ) -> dict[str, Any]:
        topo = await self._ensure_topology()
        if filter_brick:
            topo = topo.filter_by_brick(filter_brick)
        if filter_haystack:
            topo = topo.filter_by_haystack(*filter_haystack)
        return {
            "summary": topo.to_summary(),
            "devices": [d.model_dump() for d in topo.devices],
            "tagged_objects": [t.model_dump() for t in topo.tagged_objects],
        }


def build_mcp(server: BrickBACnetServer) -> Any:
    """Wire BrickBACnetServer tools into a FastMCP server instance.

    Deferred-import of fastmcp so test code without it installed can still import
    this module.
    """
    try:
        from fastmcp import FastMCP
    except ImportError as e:
        raise RuntimeError(
            "fastmcp is required to run the MCP server. Install via `pip install fastmcp`."
        ) from e

    mcp = FastMCP("brick-bacnet-mcp")

    @mcp.tool()
    async def list_devices() -> list[dict[str, Any]]:
        """List all BACnet devices discovered on the local broadcast domain."""
        return await server.list_devices()

    @mcp.tool()
    async def list_objects(device_instance: int) -> list[dict[str, Any]]:
        """List all tagged objects for a given BACnet device."""
        return await server.list_objects(device_instance)

    @mcp.tool()
    async def get_object_value(
        device_instance: int, object_type: str, object_instance: int
    ) -> dict[str, Any] | None:
        """Read the current present-value and tags of a single BACnet object."""
        return await server.get_object_value(device_instance, object_type, object_instance)

    @mcp.tool()
    async def get_tagged_topology(
        filter_brick: str | None = None,
        filter_haystack: list[str] | None = None,
    ) -> dict[str, Any]:
        """Return the full or filtered tagged-topology graph.

        filter_brick: keep only objects matching this Brick class fragment
        filter_haystack: keep only objects whose Haystack tags include all of these
        """
        return await server.get_tagged_topology(
            filter_brick=filter_brick, filter_haystack=filter_haystack
        )

    return mcp


async def serve(config: Config) -> None:
    """Top-level entry: build the BrickBACnetServer, attach MCP, run."""
    server = BrickBACnetServer(config)
    await server.start()
    try:
        mcp = build_mcp(server)
        if config.mcp.transport == "stdio":
            await mcp.run_stdio_async()
        else:
            await mcp.run_streamable_http_async(
                host=config.mcp.http_host, port=config.mcp.http_port
            )
    finally:
        await server.stop()


def run_blocking(config: Config) -> None:
    asyncio.run(serve(config))


async def generate_coverage_report(config: Config, top_n: int = 20) -> CoverageReport:
    """One-shot discover + enumerate + tag, then compute coverage. No MCP server."""
    server = BrickBACnetServer(config)
    await server.start()
    try:
        topology = await server.refresh()
        return compute_coverage(topology.tagged_objects, top_n=top_n)
    finally:
        await server.stop()


def run_coverage_report_blocking(config: Config, top_n: int = 20) -> CoverageReport:
    return asyncio.run(generate_coverage_report(config, top_n=top_n))
