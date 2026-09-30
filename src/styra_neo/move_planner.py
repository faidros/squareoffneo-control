from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .coords import BoardCoords


class PieceKind(str, Enum):
    PAWN = "pawn"
    KNIGHT = "knight"
    BISHOP = "bishop"
    ROOK = "rook"
    QUEEN = "queen"
    KING = "king"


class ActionType(str, Enum):
    PICK_UP = "pick_up"
    DROP = "drop"
    PARK_CAPTURED = "park_captured"
    PROMOTE = "promote"


@dataclass(frozen=True)
class PlannedAction:
    action: ActionType
    square: str | None = None
    x: float | None = None
    y: float | None = None
    detail: str | None = None


@dataclass(frozen=True)
class MovePlan:
    from_square: str
    to_square: str
    piece: PieceKind = PieceKind.PAWN
    capture_square: str | None = None
    promotion: PieceKind | None = None
    is_castle: bool = False
    actions: list[PlannedAction] = field(default_factory=list)


class MovePlanner:
    """Turns chess moves into a physical action plan.

    This first version is intentionally generic. The exact motor path can be
    replaced later once the board protocol and travel geometry are confirmed.
    """

    def __init__(self, coords: BoardCoords | None = None) -> None:
        self.coords = coords or BoardCoords()

    def plan_move(
        self,
        from_square: str,
        to_square: str,
        *,
        piece: PieceKind = PieceKind.PAWN,
        capture_square: str | None = None,
        promotion: PieceKind | None = None,
        is_castle: bool = False,
    ) -> MovePlan:
        actions: list[PlannedAction] = []

        from_x, from_y = self.coords.square_to_xy(from_square)
        to_x, to_y = self.coords.square_to_xy(to_square)
        actions.append(PlannedAction(ActionType.PICK_UP, from_square, from_x, from_y))

        if capture_square is not None:
            cap_x, cap_y = self.coords.square_to_xy(capture_square)
            actions.append(
                PlannedAction(
                    ActionType.PARK_CAPTURED,
                    capture_square,
                    cap_x,
                    cap_y,
                    detail="move captured piece off board first",
                )
            )

        actions.append(PlannedAction(ActionType.DROP, to_square, to_x, to_y))

        if promotion is not None:
            actions.append(
                PlannedAction(
                    ActionType.PROMOTE,
                    to_square,
                    to_x,
                    to_y,
                    detail=promotion.value,
                )
            )

        return MovePlan(
            from_square=from_square,
            to_square=to_square,
            piece=piece,
            capture_square=capture_square,
            promotion=promotion,
            is_castle=is_castle,
            actions=actions,
        )
