"""Topology assembler: combines device discovery + object enumeration + tagging
into a single queryable Topology graph.
"""

from __future__ import annotations

import logging

from brick_bacnet_mcp.models import BACnetDevice, BACnetObject, TaggedObject, Topology
from brick_bacnet_mcp.tagger import Tagger

logger = logging.getLogger(__name__)


class TopologyAssembler:
    """Assemble a Topology from cached devices and reader output.

    Stateless; safe to construct per request. v0.1 just maps + tags; v0.2 may
    add caching and incremental updates.
    """

    def __init__(self, tagger: Tagger) -> None:
        self.tagger = tagger

    def assemble(
        self,
        devices: list[BACnetDevice],
        objects_by_device: dict[int, list[BACnetObject]],
    ) -> Topology:
        """Build a Topology from devices + per-device object lists.

        Tags every object via the configured Tagger. Devices with empty object
        lists are still included (they show up in `list_devices`).
        """
        tagged: list[TaggedObject] = []
        for device in devices:
            objs = objects_by_device.get(device.device_instance, [])
            tagged.extend(self.tagger.tag_many(objs))
        topology = Topology(devices=list(devices), tagged_objects=tagged)
        logger.info(
            "Topology assembled: %d devices, %d tagged objects (%d Brick / %d Haystack matched)",
            len(topology.devices),
            len(topology.tagged_objects),
            sum(1 for t in topology.tagged_objects if t.brick_class),
            sum(1 for t in topology.tagged_objects if t.haystack_tags),
        )
        return topology
