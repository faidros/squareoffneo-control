from __future__ import annotations

import argparse
import asyncio

from .board_ble import BoardConnectionError, discover_ble_devices
from .move_events import MoveEventParser


async def scan(timeout: float) -> None:
    try:
        devices = await discover_ble_devices(timeout)
    except BoardConnectionError as exc:
        raise SystemExit(str(exc)) from exc

    if not devices:
        print("No BLE devices found.")
        return

    for device in sorted(devices, key=lambda item: item.name or ""):
        print(f"{device.name or '(unnamed)'}\t{device.address}")


async def inspect(address: str) -> None:
    try:
        from bleak import BleakClient
    except ImportError as exc:
        raise SystemExit("bleak is required for Bluetooth discovery") from exc

    try:
        async with BleakClient(address) as client:
            print(f"Connected: {address}")
            for service in client.services:
                print(f"Service {service.uuid} {service.description}")
                for characteristic in service.characteristics:
                    properties = ",".join(characteristic.properties)
                    print(f"  Characteristic {characteristic.uuid} [{properties}]")
    except Exception as exc:
        raise SystemExit(f"Could not inspect {address}: {exc}") from exc


async def listen(address: str, timeout: float) -> None:
    try:
        from bleak import BleakClient
    except ImportError as exc:
        raise SystemExit("bleak is required for Bluetooth listening") from exc

    notifications: asyncio.Queue[tuple[str, bytes]] = asyncio.Queue()

    def on_notification(sender: object, data: bytearray) -> None:
        notifications.put_nowait((str(sender), bytes(data)))

    try:
        async with BleakClient(address) as client:
            notify_characteristics = [
                characteristic
                for service in client.services
                for characteristic in service.characteristics
                if "notify" in characteristic.properties
            ]
            for characteristic in notify_characteristics:
                await client.start_notify(characteristic.uuid, on_notification)

            print(f"Listening on {len(notify_characteristics)} notify characteristics")
            move_parser = MoveEventParser()
            end_time = asyncio.get_running_loop().time() + timeout
            while True:
                remaining = end_time - asyncio.get_running_loop().time()
                if remaining <= 0:
                    break
                try:
                    sender, data = await asyncio.wait_for(
                        notifications.get(), timeout=remaining
                    )
                except TimeoutError:
                    break
                text = data.decode("ascii", errors="replace")
                print(f"{sender}\thex={data.hex()}\ttext={text!r}", flush=True)
                for move in move_parser.feed(data):
                    print(
                        f"Internal move: {move.from_square} -> {move.to_square}",
                        flush=True,
                    )

            for characteristic in notify_characteristics:
                await client.stop_notify(characteristic.uuid)
    except Exception as exc:
        raise SystemExit(f"Could not listen to {address}: {exc}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan for nearby BLE devices")
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--address", help="Connect to this BLE address and list GATT")
    parser.add_argument("--listen", action="store_true")
    args = parser.parse_args()
    if args.address:
        if args.listen:
            asyncio.run(listen(args.address, args.timeout))
        else:
            asyncio.run(inspect(args.address))
    else:
        asyncio.run(scan(args.timeout))


if __name__ == "__main__":
    main()