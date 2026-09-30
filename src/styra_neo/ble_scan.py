from __future__ import annotations

import argparse
import asyncio

from .board_ble import BoardConnectionError, discover_ble_devices


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan for nearby BLE devices")
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--address", help="Connect to this BLE address and list GATT")
    args = parser.parse_args()
    if args.address:
        asyncio.run(inspect(args.address))
    else:
        asyncio.run(scan(args.timeout))


if __name__ == "__main__":
    main()