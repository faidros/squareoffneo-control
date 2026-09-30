from __future__ import annotations

from dataclasses import dataclass


class ProtocolError(ValueError):
    """Raised when a board message cannot be parsed."""


@dataclass(frozen=True)
class BoardResponse:
    raw: str
    code: str
    payload: str


class BoardProtocol:
    """Helpers for the simple x...z message framing described in public repos."""

    @staticmethod
    def encode(command: str) -> str:
        command = command.strip()
        if not command:
            raise ProtocolError("command cannot be empty")
        if command.startswith("x") and command.endswith("z"):
            return command
        return f"x{command}z"

    @staticmethod
    def decode(message: str) -> BoardResponse:
        message = message.strip()
        if not message:
            raise ProtocolError("message cannot be empty")
        if message.startswith("x") and message.endswith("z") and len(message) >= 3:
            body = message[1:-1]
            code = body[:2] if len(body) >= 2 else body
            payload = body[2:] if len(body) > 2 else ""
            return BoardResponse(raw=message, code=code, payload=payload)
        raise ProtocolError(f"unsupported board message: {message!r}")

    @staticmethod
    def move_command(from_square: str, to_square: str) -> str:
        return BoardProtocol.encode(f"{from_square}{to_square}")

    @staticmethod
    def ack_command() -> str:
        return BoardProtocol.encode("OK")
