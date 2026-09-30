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
