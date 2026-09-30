from __future__ import annotations

from dataclasses import dataclass

from .board_ble import BoardBLEClient
from .move_planner import MovePlan, MovePlanner, PieceKind


@dataclass
class NeoController:
    board: BoardBLEClient
    planner: MovePlanner

    @classmethod
    def with_board(cls, board: BoardBLEClient, planner: MovePlanner | None = None) -> "NeoController":
        return cls(board=board, planner=planner or MovePlanner())

    async def connect(self) -> None:
        await self.board.connect()

    async def disconnect(self) -> None:
        await self.board.disconnect()

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
        return self.planner.plan_move(
            from_square,
            to_square,
            piece=piece,
            capture_square=capture_square,
            promotion=promotion,
            is_castle=is_castle,
        )

    async def move_piece(
        self,
        from_square: str,
        to_square: str,
        *,
        piece: PieceKind = PieceKind.PAWN,
        capture_square: str | None = None,
        promotion: PieceKind | None = None,
        is_castle: bool = False,
    ):
        plan = self.plan_move(
            from_square,
            to_square,
            piece=piece,
            capture_square=capture_square,
            promotion=promotion,
            is_castle=is_castle,
        )
        return await self.board.move(plan.from_square, plan.to_square)
