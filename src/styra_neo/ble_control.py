from __future__ import annotations

import argparse
import asyncio

from .board_ble import BoardBLEClient, BleakTransport, BoardConnectionError


ADDRESS = "59140460-88DD-27DA-D0F8-3CE9D4E4609C"
WRITE_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
NOTIFY_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"


async def run(address: str, from_square: str, to_square: str) -> None:
    transport = BleakTransport(address, WRITE_UUID, NOTIFY_UUID, read_timeout=8.0)
    board = BoardBLEClient(transport)
    try:
        await board.connect()
        print("Connected")
        for index, response in enumerate(await board.start_game_black(), start=1):
            print(f"Setup {index}: {response}")
        response = await board.move(from_square, to_square)
        print(f"Move {from_square}->{to_square}: {response}")
    except BoardConnectionError as exc:
        raise SystemExit(str(exc)) from exc
    finally:
        await board.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a controlled Square Off move")
    parser.add_argument("--address", default=ADDRESS)
    parser.add_argument("from_square")
    parser.add_argument("to_square")
    args = parser.parse_args()
    asyncio.run(run(args.address, args.from_square, args.to_square))


if __name__ == "__main__":
    main()