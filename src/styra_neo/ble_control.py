from __future__ import annotations

import argparse
import asyncio

from .move_planner import MotorRouteError, NeoMotorRoutePlanner


ADDRESS = "59140460-88DD-27DA-D0F8-3CE9D4E4609C"
MOVE_UUID = "f9664d70-93ff-4cfe-9bfe-b5866aa5bef2"
MOVE_NOTIFY_UUID = "4496994f-2600-4e7e-81d5-e0f7b67ebd48"
BOARD_STATUS_UUID = "777ac5a4-6fa8-474b-841d-091bd57d28c4"


async def run(address: str, from_square: str, to_square: str) -> None:
    try:
        from bleak import BleakClient
    except ImportError as exc:
        raise SystemExit("bleak is required for Bluetooth control") from exc

    planner = NeoMotorRoutePlanner()
    notifications: asyncio.Queue[tuple[str, bytes]] = asyncio.Queue()

    def on_notification(sender: object, data: bytearray) -> None:
        notifications.put_nowait((str(sender), bytes(data)))

    try:
        async with BleakClient(address) as client:
            for uuid in (MOVE_NOTIFY_UUID, BOARD_STATUS_UUID):
                await client.start_notify(uuid, on_notification)

            print(f"Connected: {address}")
            occupied_squares: frozenset[str] | None = None
            state_deadline = asyncio.get_running_loop().time() + 5
            while occupied_squares is None:
                remaining = state_deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    break
                try:
                    sender, data = await asyncio.wait_for(
                        notifications.get(), timeout=remaining
                    )
                except TimeoutError:
                    break
                if BOARD_STATUS_UUID not in sender.lower():
                    continue
                try:
                    occupied_squares = planner.decode_board_state(data)
                except MotorRouteError:
                    continue

            if occupied_squares is None:
                raise MotorRouteError(
                    "no valid board-state bitmap received; no motor command sent"
                )

            route_points = planner.plan_route(
                from_square,
                to_square,
                occupied_squares=occupied_squares,
            )
            route = planner.encode_route(route_points)
            print(f"Board state received: {len(occupied_squares)} occupied squares")
            await client.write_gatt_char(
                MOVE_UUID, route.encode("ascii"), response=True
            )
            print(f"Sent motor route: {from_square}->{to_square} ({route})")

            end_time = asyncio.get_running_loop().time() + 10
            while asyncio.get_running_loop().time() < end_time:
                remaining = end_time - asyncio.get_running_loop().time()
                try:
                    sender, data = await asyncio.wait_for(
                        notifications.get(), timeout=remaining
                    )
                except TimeoutError:
                    break
                text = data.decode("ascii", errors="replace")
                print(f"Notification {sender}: {text!r} hex={data.hex()}")
    except MotorRouteError as exc:
        raise SystemExit(f"Not sending motor route: {exc}") from exc
    except Exception as exc:
        raise SystemExit(f"Could not control BLE board at {address}: {exc}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a controlled Square Off move")
    parser.add_argument("--address", default=ADDRESS)
    parser.add_argument("from_square")
    parser.add_argument("to_square")
    args = parser.parse_args()
    asyncio.run(run(args.address, args.from_square, args.to_square))


if __name__ == "__main__":
    main()