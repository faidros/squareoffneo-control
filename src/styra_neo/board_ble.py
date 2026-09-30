from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

from .protocol import BoardProtocol, BoardResponse


class Transport(Protocol):
    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    async def write(self, payload: bytes) -> None: ...

    async def read(self) -> bytes: ...


class BoardConnectionError(RuntimeError):
    """Raised when the board cannot be reached or does not answer."""


@dataclass
class InMemoryTransport:
    """Small test transport for development without BLE hardware."""

    inbox: list[bytes] | None = None
    outbox: list[bytes] | None = None

    def __post_init__(self) -> None:
        self.inbox = self.inbox or []
        self.outbox = self.outbox or []

    async def connect(self) -> None:
        return None

    async def disconnect(self) -> None:
        return None

    async def write(self, payload: bytes) -> None:
        self.outbox.append(payload)

    async def read(self) -> bytes:
        if not self.inbox:
            await asyncio.sleep(0)
            return b""
        return self.inbox.pop(0)


class BleakTransport:
    """BLE transport for a board with one write and one notify characteristic."""

    def __init__(
        self,
        address: str,
        write_uuid: str,
        notify_uuid: str | None = None,
        *,
        read_timeout: float = 5.0,
    ) -> None:
        self.address = address
        self.write_uuid = write_uuid
        self.notify_uuid = notify_uuid or write_uuid
        self.read_timeout = read_timeout
        self._client = None
        self._notifications: asyncio.Queue[bytes] = asyncio.Queue()

    async def connect(self) -> None:
        try:
            from bleak import BleakClient
        except ImportError as exc:
            raise BoardConnectionError(
                "bleak is required for real Bluetooth connections"
            ) from exc

        self._client = BleakClient(self.address)
        try:
            await self._client.connect()
            await self._client.start_notify(self.notify_uuid, self._on_notification)
        except Exception as exc:
            await self.disconnect()
            raise BoardConnectionError(
                f"could not connect to BLE board at {self.address}: {exc}"
            ) from exc

    async def disconnect(self) -> None:
        if self._client is None:
            return
        try:
            if self._client.is_connected:
                await self._client.stop_notify(self.notify_uuid)
                await self._client.disconnect()
        finally:
            self._client = None

    async def write(self, payload: bytes) -> None:
        if self._client is None or not self._client.is_connected:
            raise BoardConnectionError("BLE board is not connected")
        await self._client.write_gatt_char(self.write_uuid, payload)

    async def read(self) -> bytes:
        try:
            return await asyncio.wait_for(
                self._notifications.get(), timeout=self.read_timeout
            )
        except TimeoutError as exc:
            raise BoardConnectionError("timed out waiting for BLE notification") from exc

    def _on_notification(self, _sender: object, data: bytearray) -> None:
        self._notifications.put_nowait(bytes(data))


async def discover_ble_devices(timeout: float = 8.0) -> list[object]:
    """Discover nearby BLE devices using bleak."""
    try:
        from bleak import BleakScanner
    except ImportError as exc:
        raise BoardConnectionError(
            "bleak is required for Bluetooth discovery"
        ) from exc
    return list(await BleakScanner.discover(timeout=timeout))


class BoardBLEClient:
    def __init__(self, transport: Transport) -> None:
        self.transport = transport

    async def connect(self) -> None:
        await self.transport.connect()

    async def disconnect(self) -> None:
        await self.transport.disconnect()

    async def send_command(self, command: str) -> BoardResponse | None:
        framed = BoardProtocol.encode(command)
        await self.transport.write(framed.encode("ascii"))
        response = await self.transport.read()
        if not response:
            return None
        return BoardProtocol.decode(response.decode("ascii", errors="ignore"))

    async def move(self, from_square: str, to_square: str) -> BoardResponse | None:
        return await self.send_command(f"{from_square}{to_square}")
