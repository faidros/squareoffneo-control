from __future__ import annotations

import argparse
import asyncio

from .move_planner import MotorRouteError, NeoMotorRoutePlanner


ADDRESS = "59140460-88DD-27DA-D0F8-3CE9D4E4609C"
MOVE_UUID = "f9664d70-93ff-4cfe-9bfe-b5866aa5bef2"
MOVE_NOTIFY_UUID = "4496994f-2600-4e7e-81d5-e0f7b67ebd48"
BOARD_STATUS_UUID = "777ac5a4-6fa8-474b-841d-091bd57d28c4"


async def run(
    address: str,
    from_square: str,
    to_square: str,
    *,
    castle: bool = False,
    capture: bool = False,
) -> None:
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

            print(f"Board state received: {len(occupied_squares)} occupied squares")

            if castle and capture:
                raise MotorRouteError("castling and capture modes are mutually exclusive")

            motor_steps: list[tuple[str, str | None, str | None, tuple[tuple[float, float], ...]]] = []
            if castle:
                castling_plan = planner.plan_castle(
                    from_square,
                    to_square,
                    occupied_squares=occupied_squares,
                )
                motor_steps.extend(
                    (
                        ("castling king", castling_plan.king.from_square, castling_plan.king.to_square, castling_plan.king.route),
                        ("castling rook", castling_plan.rook.from_square, castling_plan.rook.to_square, castling_plan.rook.route),
                    )
                )
            elif capture:
                capture_plan = planner.plan_capture(
                    from_square,
                    to_square,
                    occupied_squares=occupied_squares,
                )
                parking_file, parking_rank = capture_plan.parking_position
                parking_name = f"parking ({parking_file:g},{parking_rank:g})"
                motor_steps.extend(
                    (
                        (
                            "park captured piece",
                            capture_plan.captured_square,
                            None,
                            capture_plan.parking_route,
                        ),
                        (
                            "capturing piece",
                            from_square,
                            to_square,
                            capture_plan.capturing_route,
                        ),
                    )
                )
            else:
                route_points = planner.plan_route(
                    from_square,
                    to_square,
                    occupied_squares=occupied_squares,
                )
                route = planner.encode_route(route_points)
                await client.write_gatt_char(
                    MOVE_UUID, route.encode("ascii"), response=True
                )
                print(f"Sent motor route: {from_square}->{to_square} ({route})")

            for label, source_square, destination_square, route_points in motor_steps:
                expected_squares = set(occupied_squares)
                if source_square is not None:
                    expected_squares.remove(source_square)
                if destination_square is not None:
                    expected_squares.add(destination_square)
                expected_bitmap = frozenset(expected_squares)
                route = planner.encode_route(route_points)
                await client.write_gatt_char(
                    MOVE_UUID, route.encode("ascii"), response=True
                )
                destination_name = destination_square or parking_name
                print(f"Sent {label}: {source_square}->{destination_name} ({route})")

                got_acknowledgement = False
                got_expected_state = False
                move_deadline = asyncio.get_running_loop().time() + 20
                while not (got_acknowledgement and got_expected_state):
                    remaining = move_deadline - asyncio.get_running_loop().time()
                    if remaining <= 0:
                        break
                    try:
                        sender, data = await asyncio.wait_for(
                            notifications.get(), timeout=remaining
                        )
                    except TimeoutError:
                        break

                    text = data.decode("ascii", errors="replace").strip()
                    sender_lower = sender.lower()
                    if MOVE_NOTIFY_UUID in sender_lower and text == "OK":
                        got_acknowledgement = True
                    elif BOARD_STATUS_UUID in sender_lower:
                        try:
                            observed_squares = planner.decode_board_state(data)
                        except MotorRouteError:
                            continue
                        got_expected_state = observed_squares == expected_bitmap

                if not (got_acknowledgement and got_expected_state):
                    raise MotorRouteError(
                        f"{label} {source_square}->{destination_name} was not fully "
                        f"confirmed (OK={got_acknowledgement}, "
                        f"expected_bitmap={got_expected_state}); remaining steps "
                        "were not sent"
                    )

                occupied_squares = expected_bitmap
                print(f"Confirmed {label}: {source_square}->{destination_name}")

            if castle or capture:
                return

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
        raise SystemExit(f"Motor sequence stopped safely: {exc}") from exc
    except Exception as exc:
        raise SystemExit(f"Could not control BLE board at {address}: {exc}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a controlled Square Off Neo move")
    parser.add_argument("--address", default=ADDRESS)
    special_move_group = parser.add_mutually_exclusive_group()
    special_move_group.add_argument(
        "--castle", action="store_true", help="execute a confirmed two-step castle"
    )
    special_move_group.add_argument(
        "--capture",
        action="store_true",
        help="park the captured piece near h4, then execute the capturing move",
    )
    parser.add_argument("from_square")
    parser.add_argument("to_square")
    args = parser.parse_args()
    asyncio.run(
        run(
            args.address,
            args.from_square,
            args.to_square,
            castle=args.castle,
            capture=args.capture,
        )
    )


if __name__ == "__main__":
    main()