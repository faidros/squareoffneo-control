from __future__ import annotations

import asyncio

from .board_ble import BoardBLEClient, InMemoryTransport
from .controller import NeoController
from .move_planner import PieceKind


async def main() -> None:
    transport = InMemoryTransport(inbox=[b"x12-OKz"])
    board = BoardBLEClient(transport)
    controller = NeoController.with_board(board)

    await controller.connect()
    plan = controller.plan_move("e2", "e4", piece=PieceKind.PAWN)
    print(plan)
    response = await controller.move_piece("e2", "e4", piece=PieceKind.PAWN)
    print(response)
    await controller.disconnect()


if __name__ == "__main__":
    asyncio.run(main())