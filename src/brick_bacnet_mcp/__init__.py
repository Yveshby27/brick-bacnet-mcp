"""brick-bacnet-mcp

Read-only BACnet/IP gateway exposing Brick + Project Haystack tagged building
topology to LLM agents via MCP.

See https://habchy.dev/research/bacnet-msi-semantic-gap for the research note
this implementation came out of.
"""

__version__ = "0.1.0a0"

from brick_bacnet_mcp.models import (
    BACnetDevice,
    BACnetObject,
    TaggedObject,
    Topology,
)
from brick_bacnet_mcp.tagger import Tagger, TaggingRule

__all__ = [
    "BACnetDevice",
    "BACnetObject",
    "TaggedObject",
    "Tagger",
    "TaggingRule",
    "Topology",
    "__version__",
]
