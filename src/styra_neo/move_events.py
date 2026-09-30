from __future__ import annotations

import re
from dataclasses import dataclass


_MOVE_EVENT = re.compile(r"([a-h][1-8])([ud])")


@dataclass(frozen=True)
class BoardMove:
    """A move observed from the board's lift/drop notifications."""

    from_square: str
    to_square: str


class MoveEventParser:
    """Converts board notifications such as ``e2u`` and ``e4d`` to moves."""

    def __init__(self) -> None:
        self._lifted_square: str | None = None

    def feed(self, data: bytes | str) -> list[BoardMove]:
        text = data.decode("ascii", errors="ignore") if isinstance(data, bytes) else data
        moves: list[BoardMove] = []
        for match in _MOVE_EVENT.finditer(text.lower()):
            square, event_type = match.groups()
            if event_type == "u":
                self._lifted_square = square
            elif self._lifted_square is not None:
                moves.append(BoardMove(self._lifted_square, square))
                self._lifted_square = None
        return moves

    def reset(self) -> None:
        self._lifted_square = None