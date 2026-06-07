"""Pydantic data models for devices, objects, tagged objects, and topology.

These are the schema-validated types that flow between discovery, reader,
tagger, topology, and server modules. Use them as the canonical interfaces;
prefer model instantiation over loose dicts everywhere.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BACnetDevice(BaseModel):
    """A BACnet device discovered on the network via Who-Is / I-Am."""

    model_config = ConfigDict(frozen=False, extra="forbid")

    device_instance: int = Field(..., description="BACnet device instance number (0..4194303)")
    address: str = Field(..., description="BACnet/IP address (e.g. '192.168.1.42:47808')")
    vendor_id: int | None = Field(default=None, description="BACnet vendor identifier")
    vendor_name: str | None = Field(
        default=None, description="Vendor name (may require ReadProperty to resolve)"
    )
    model_name: str | None = Field(default=None, description="Device model name")
    firmware_revision: str | None = Field(default=None, description="Firmware revision string")
    object_count: int | None = Field(default=None, description="Length of the device's object list")


class BACnetObject(BaseModel):
    """A single object enumerated from a BACnet device."""

    model_config = ConfigDict(frozen=False, extra="forbid")

    device_instance: int = Field(..., description="Owning device instance")
    object_type: str = Field(
        ...,
        description=(
            "BACnet object type as canonical string "
            "(e.g. 'analog-input', 'binary-output', 'multi-state-value')"
        ),
    )
    object_instance: int = Field(..., description="Object instance number")
    object_name: str | None = Field(default=None, description="Object name property")
    description: str | None = Field(default=None, description="Object description")
    present_value: float | int | bool | str | None = Field(
        default=None, description="Current present-value (type varies by object type)"
    )
    units: str | None = Field(
        default=None, description="Engineering units string (only meaningful for analog)"
    )

    @property
    def object_id(self) -> str:
        """Stable string identifier for the object across queries."""
        return f"{self.object_type}:{self.object_instance}@{self.device_instance}"


class TaggedObject(BaseModel):
    """A BACnet object with Brick + Haystack semantic tags attached."""

    model_config = ConfigDict(frozen=False, extra="forbid")

    object: BACnetObject = Field(..., description="The underlying BACnet object")
    brick_class: str | None = Field(
        default=None,
        description=(
            "Brick class IRI fragment (e.g. 'Outside_Air_Temperature_Sensor'). "
            "None when no rule matched."
        ),
    )
    haystack_tags: list[str] = Field(
        default_factory=list,
        description=(
            "Haystack tag marker set "
            "(e.g. ['point', 'sensor', 'outside', 'air', 'temp']). "
            "Empty list when no rule matched."
        ),
    )
    haystack_kind: str | None = Field(
        default=None,
        description="Haystack 'kind' tag value (Number, Bool, Str, Marker)",
    )
    haystack_unit: str | None = Field(
        default=None,
        description="Haystack unit string normalized (e.g. '°F', 'kWh', '%')",
    )
    rule_matched: str | None = Field(
        default=None,
        description="Identifier of the matched rule (for debugging / extension)",
    )


class Topology(BaseModel):
    """Full or filtered tagged-topology graph for LLM agent consumption."""

    model_config = ConfigDict(frozen=False, extra="forbid")

    devices: list[BACnetDevice] = Field(default_factory=list)
    tagged_objects: list[TaggedObject] = Field(default_factory=list)

    def filter_by_brick(self, brick_class: str) -> Topology:
        """Return a new Topology containing only objects matching a Brick class."""
        filtered = [tobj for tobj in self.tagged_objects if tobj.brick_class == brick_class]
        device_ids = {tobj.object.device_instance for tobj in filtered}
        devices = [dev for dev in self.devices if dev.device_instance in device_ids]
        return Topology(devices=devices, tagged_objects=filtered)

    def filter_by_haystack(self, *required_tags: str) -> Topology:
        """Return a new Topology containing only objects with all required Haystack tags."""
        required = set(required_tags)
        filtered = [
            tobj for tobj in self.tagged_objects if required.issubset(set(tobj.haystack_tags))
        ]
        device_ids = {tobj.object.device_instance for tobj in filtered}
        devices = [dev for dev in self.devices if dev.device_instance in device_ids]
        return Topology(devices=devices, tagged_objects=filtered)

    def to_summary(self) -> dict[str, Any]:
        """Compact summary for LLM agent rendering."""
        return {
            "device_count": len(self.devices),
            "object_count": len(self.tagged_objects),
            "brick_classes": sorted({t.brick_class for t in self.tagged_objects if t.brick_class}),
            "haystack_tag_set": sorted(
                {tag for t in self.tagged_objects for tag in t.haystack_tags}
            ),
        }
