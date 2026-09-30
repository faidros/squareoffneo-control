from __future__ import annotations

import argparse
import asyncio

from .board_ble import BoardBLEClient, BleakTransport, BoardConnectionError


ADDRESS = "59140460-88DD-27DA-D0F8-3CE9D4E4609C"
WRITE_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
NOTIFY_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
ALL_NOTIFY_UUIDS = [
    NOTIFY_UUID,
    "00002a19-0000-1000-8000-00805f9b34fb",
    "4496994f-2600-4e7e-81d5-e0f7b67ebd48",
    "777ac5a4-6fa8-474b-841d-091bd57d28c4",
]


async def run(address: str, from_square: str, to_square: str) -> None:
    transport = BleakTransport(address, WRITE_UUID, ALL_NOTIFY_UUIDS, read_timeout=2.0)
    board = BoardBLEClient(transport)
    try:
        await board.connect()
        print("Connected")
        for command in ("RSTVAR", "CONNECTED", "BOARDTYPE", "GAMEBLACK"):
            await board.send_command(command, wait_for_response=False)
            print(f"Sent setup: {command}")
            await asyncio.sleep(1)
        await board.send_command(
            f"{from_square}{to_square}", wait_for_response=False
        )
        print(f"Sent move: {from_square}->{to_square}")
        end_time = asyncio.get_running_loop().time() + 8
        while asyncio.get_running_loop().time() < end_time:
            try:
                data = await asyncio.wait_for(transport.read(), timeout=0.5)
            except (BoardConnectionError, TimeoutError):
                continue
            print(f"Notification: {data.hex()} {data!r}")
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