from __future__ import annotations

from dataclasses import dataclass


FILES = "abcdefgh"
RANKS = "12345678"


def square_to_index(square: str) -> tuple[int, int]:
    square = square.strip().lower()
    if len(square) != 2 or square[0] not in FILES or square[1] not in RANKS:
        raise ValueError(f"invalid square: {square!r}")
    return FILES.index(square[0]), RANKS.index(square[1])


def index_to_square(file_index: int, rank_index: int) -> str:
    if not 0 <= file_index < 8 or not 0 <= rank_index < 8:
        raise ValueError("indices must be between 0 and 7")
    return f"{FILES[file_index]}{RANKS[rank_index]}"


@dataclass(frozen=True)
class BoardCoords:
    """Simple square-to-grid mapping.

    The exact physical calibration still needs to be measured on the real board.
    """

    x_step: float = 1.0
    y_step: float = 1.0
    origin_x: float = 0.0
    origin_y: float = 0.0

    def square_to_xy(self, square: str) -> tuple[float, float]:
        file_index, rank_index = square_to_index(square)
        return (
            self.origin_x + file_index * self.x_step,
            self.origin_y + rank_index * self.y_step,
        )
