"""BACnet ReadProperty: object enumeration and present-value polling.

For v0.1: read-only. Enumerates the object list per device, then polls
present-value, units, description, and object-name per object at the
configured polling interval.

No COV in v0.1 (defer to v0.2). No WriteProperty in v0.1 (intentional;
compliance-surface tight).
"""

from __future__ import annotations

import logging
from typing import Any

from brick_bacnet_mcp.config import BACnetConfig
from brick_bacnet_mcp.models import BACnetDevice, BACnetObject

logger = logging.getLogger(__name__)


# Object types we enumerate in v0.1. Schedule, Calendar, Notification Class are
# read but parsed as opaque records (full structure decoding deferred to v0.2).
SUPPORTED_OBJECT_TYPES = {
    "analog-input",
    "analog-output",
    "analog-value",
    "binary-input",
    "binary-output",
    "binary-value",
    "multi-state-input",
    "multi-state-output",
    "multi-state-value",
    "schedule",
    "calendar",
    "notification-class",
}


class Reader:
    """Enumerates BACnet objects per device and reads present-value properties.

    For v0.1: polling-based, no COV. The reader takes the active bacpypes3
    Application from a Discovery instance; both share a single network stack
    to avoid socket churn.
    """

    def __init__(self, config: BACnetConfig, app: Any = None) -> None:
        self.config = config
        self._app = app  # bacpypes3 Application; supplied externally for now

    def attach(self, app: Any) -> None:
        """Wire up the shared bacpypes3 Application (constructed by Discovery)."""
        self._app = app

    async def enumerate_objects(self, device: BACnetDevice) -> list[BACnetObject]:
        """Read the device's object list and produce a BACnetObject per entry.

        Each entry triggers ReadProperty calls for object-name, description,
        units (analog types), and present-value. Errors on individual properties
        are logged and the object is included with the failed property left as None.

        bacpypes3 0.0.10x expects property names as kebab-case strings (e.g.
        'object-list', 'present-value', 'units') and object identifiers as
        'type,instance' strings. Enum-form arguments raise a generic 'prop'
        error. We use the string forms throughout.
        """
        if self._app is None:
            raise RuntimeError(
                "Reader has no bacpypes3 Application attached. "
                "Call attach(app) after Discovery.start()."
            )

        device_addr = device.address
        device_oid_str = f"device,{device.device_instance}"

        # Read the object list.
        #
        # bacpypes3 0.0.10x raises `bacpypes3.primitivedata.Error(...)` for
        # protocol-level errors. Those classes derive from BaseException, NOT
        # Exception, so `except Exception` does not catch them. We catch
        # BaseException broadly and re-raise the hard interrupts explicitly.
        try:
            object_list = await self._app.read_property(device_addr, device_oid_str, "object-list")
        except BaseException as e:
            if isinstance(e, (KeyboardInterrupt, SystemExit)):
                raise
            logger.error("Failed to read object list for %s: %s", device, e)
            return []

        results: list[BACnetObject] = []
        for entry in object_list:
            # entry is an ObjectIdentifier; unpacks to (ObjectType, int).
            # str(ObjectType) gives the canonical kebab-case form directly.
            otype_raw, oinst = entry
            otype = str(otype_raw)
            if otype not in SUPPORTED_OBJECT_TYPES:
                continue
            obj = await self._read_one_object(device, otype, int(oinst))
            if obj is not None:
                results.append(obj)
        return results

    async def _read_one_object(
        self, device: BACnetDevice, object_type: str, object_instance: int
    ) -> BACnetObject | None:
        """Read object-name, description, units, present-value for a single object."""
        oid_str = f"{object_type},{object_instance}"
        addr = device.address

        async def _read(prop_name: str) -> Any:
            # bacpypes3 protocol errors derive from BaseException; see comment
            # in enumerate_objects for why we catch BaseException here.
            try:
                return await self._app.read_property(addr, oid_str, prop_name)
            except BaseException as e:
                if isinstance(e, (KeyboardInterrupt, SystemExit)):
                    raise
                logger.debug(
                    "ReadProperty failed on %s/%s prop=%s: %s",
                    object_type,
                    object_instance,
                    prop_name,
                    e,
                )
                return None

        name = await _read("object-name")
        desc = await _read("description")
        # Units only meaningful for analog
        units_raw = None
        if object_type.startswith("analog-"):
            units_raw = await _read("units")
        present = await _read("present-value")

        return BACnetObject(
            device_instance=device.device_instance,
            object_type=object_type,
            object_instance=object_instance,
            object_name=str(name) if name is not None else None,
            description=str(desc) if desc is not None else None,
            present_value=_coerce_present_value(present, object_type),
            units=str(units_raw) if units_raw is not None else None,
        )


def _coerce_present_value(raw: Any, object_type: str) -> float | int | bool | str | None:
    """Coerce a raw bacpypes value into a model-friendly Python primitive."""
    if raw is None:
        return None
    if object_type.startswith("analog-"):
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None
    if object_type.startswith("binary-"):
        # bacpypes binary present-value is BinaryPV enum; cast to bool
        try:
            return bool(int(raw))
        except (TypeError, ValueError):
            return None
    if object_type.startswith("multi-state-"):
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None
    # Schedule / Calendar / Notification Class: stringify for v0.1
    return str(raw)
