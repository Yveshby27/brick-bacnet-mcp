"""BACnet/IP device discovery via Who-Is broadcast and I-Am capture.

Uses bacpypes3 to broadcast a Who-Is request and listen for I-Am responses.
Discovered devices are persisted in an in-memory cache keyed by device instance.

This is the v0.1 read-only discovery layer. No write or COV; polling-based
property reads happen in `reader.py`.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterator

from brick_bacnet_mcp.config import BACnetConfig
from brick_bacnet_mcp.models import BACnetDevice

logger = logging.getLogger(__name__)


class DeviceCache:
    """Thread-safe-enough in-memory cache of discovered BACnet devices.

    v0.1 single-process; lock-free dict access is fine. v0.2 will need a
    proper lock when multi-discovery rounds run concurrently.
    """

    def __init__(self) -> None:
        self._devices: dict[int, BACnetDevice] = {}

    def upsert(self, device: BACnetDevice) -> None:
        self._devices[device.device_instance] = device

    def get(self, device_instance: int) -> BACnetDevice | None:
        return self._devices.get(device_instance)

    def all(self) -> list[BACnetDevice]:
        return list(self._devices.values())

    def __iter__(self) -> Iterator[BACnetDevice]:
        return iter(self._devices.values())

    def __len__(self) -> int:
        return len(self._devices)

    def clear(self) -> None:
        self._devices.clear()


class Discovery:
    """Run Who-Is broadcasts and harvest I-Am replies into a DeviceCache.

    Uses bacpypes3's async Application API. Constructed lazily so tests can
    inject a fake application.

    For v0.1, the bacpypes3 Application instance is created in `start()` and
    torn down in `stop()`. v0.2 will likely hoist this to a shared application
    that discovery and reader both share, avoiding socket churn.
    """

    def __init__(self, config: BACnetConfig, cache: DeviceCache | None = None) -> None:
        self.config = config
        self.cache = cache or DeviceCache()
        self._app = None  # bacpypes3 Application; lazy-init

    async def start(self) -> None:
        """Initialize the bacpypes3 Application.

        Deferred-import of bacpypes3 so test code without the library installed
        can still import this module.

        bacpypes3 0.0.10x exposes `Application.from_args(argparse.Namespace)` as
        the canonical factory. We synthesize the Namespace from BACnetConfig
        instead of using SimpleArgumentParser so the lifecycle stays in our
        hands.
        """
        try:
            from argparse import Namespace

            from bacpypes3.app import Application
        except ImportError as e:
            raise RuntimeError(
                "bacpypes3 is required for live discovery. Install it via "
                "`pip install bacpypes3`, or use the simulator-backed test fixtures."
            ) from e

        args = Namespace(
            name="brick-bacnet-mcp",
            instance=self.config.local_device_instance,
            network=0,
            address=self.config.bind_address,
            vendoridentifier=999,
            foreign=None,
            ttl=30,
            bbmd=None,
            route_aware=None,
            debug=None,
            color=None,
            loggers=False,
        )
        self._app = Application.from_args(args)
        logger.info("BACnet discovery application started on %s", self.config.bind_address)

    async def stop(self) -> None:
        if self._app is not None:
            # bacpypes3 0.0.10x: Application.close() is a synchronous method that
            # tears down sockets. Older / future versions may make it async. Be
            # tolerant of both shapes.
            try:
                result = self._app.close()
                if asyncio.iscoroutine(result):
                    await result
            except (AttributeError, RuntimeError) as e:
                logger.debug("Application close cleanup raised %s; continuing", e)
            self._app = None

    async def discover_once(self) -> list[BACnetDevice]:
        """Send a single Who-Is broadcast and harvest I-Am responses.

        Blocks for `config.discovery_timeout_seconds` then returns the
        accumulated cache snapshot.
        """
        if self._app is None:
            raise RuntimeError("Discovery.start() must be called before discover_once()")

        from bacpypes3.pdu import Address, GlobalBroadcast

        # "255.255.255.255" routes through bacpypes3's IP-level global broadcast.
        # Any other value (subnet broadcast like 192.168.1.255, or unicast like
        # 127.0.0.1:47808) is sent as a directed Address. Required on Windows
        # where the loopback adapter blocks broadcast.
        if self.config.broadcast_address == "255.255.255.255":
            target = GlobalBroadcast()
        else:
            target = Address(self.config.broadcast_address)

        logger.info(
            "Sending Who-Is to %s; collecting I-Am for %d seconds",
            self.config.broadcast_address,
            self.config.discovery_timeout_seconds,
        )

        i_ams = await self._app.who_is(
            address=target,
            timeout=self.config.discovery_timeout_seconds,
        )

        new_devices: list[BACnetDevice] = []
        for i_am in i_ams:
            device_instance = i_am.iAmDeviceIdentifier[1]
            address_str = str(i_am.pduSource)
            vendor_id = getattr(i_am, "vendorID", None)
            device = BACnetDevice(
                device_instance=device_instance,
                address=address_str,
                vendor_id=vendor_id,
            )
            self.cache.upsert(device)
            new_devices.append(device)

        logger.info("Discovery cycle complete: %d devices in cache", len(self.cache))
        return new_devices


async def run_discovery(config: BACnetConfig) -> list[BACnetDevice]:
    """Convenience: full discover-once-and-cleanup helper."""
    discovery = Discovery(config)
    await discovery.start()
    try:
        await discovery.discover_once()
        await asyncio.sleep(0)  # let event loop drain pending callbacks
        return discovery.cache.all()
    finally:
        await discovery.stop()
