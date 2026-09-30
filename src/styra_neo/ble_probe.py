from __future__ import annotations

import argparse
import asyncio

from .board_ble import BoardConnectionError


ADDRESS = "59140460-88DD-27DA-D0F8-3CE9D4E4609C"


async def probe(address: str) -> None:
    try:
        from bleak import BleakClient
    except ImportError as exc:
        raise SystemExit("bleak is required for Bluetooth probing") from exc

    try:
        async with BleakClient(address) as client:
            print(f"Connected: {address}")
            for service in client.services:
                print(f"Service {service.uuid} {service.description}")
                for characteristic in service.characteristics:
                    properties = ",".join(characteristic.properties)
                    print(f"  {characteristic.uuid} [{properties}]")
                    if "read" in characteristic.properties:
                        try:
                            value = await client.read_gatt_char(characteristic.uuid)
                            print(f"    value={value.hex()} text={value!r}")
                        except Exception as exc:
                            print(f"    read failed: {exc}")
    except Exception as exc:
        raise SystemExit(f"Could not probe {address}: {exc}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect Square Off Neo GATT data")
    parser.add_argument("--address", default=ADDRESS)
    args = parser.parse_args()
    asyncio.run(probe(args.address))


if __name__ == "__main__":
    main()