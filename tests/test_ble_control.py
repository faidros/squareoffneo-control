from __future__ import annotations

import sys
import unittest
import importlib
from types import SimpleNamespace
from unittest.mock import patch

ble_control = importlib.import_module("src.styra_neo.ble_control")
from styra_neo.coords import square_to_index


class FakeBleakClient:
    initial_occupancy = {"e1", "h1"}
    writes: list[tuple[str, str, bool]] = []

    def __init__(self, address: str) -> None:
        self.address = address
        self.occupancy = set(self.initial_occupancy)
        self.callbacks = {}
        type(self).writes = []

    async def __aenter__(self) -> FakeBleakClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def start_notify(self, uuid: str, callback: object) -> None:
        self.callbacks[uuid] = callback
        if uuid == ble_control.BOARD_STATUS_UUID:
            self._publish_board_state()

    def _publish_board_state(self) -> None:
        bitmap = ["0"] * 64
        for square in self.occupancy:
            file_index, rank_index = square_to_index(square)
            bitmap[file_index * 8 + rank_index] = "1"
        callback = self.callbacks[ble_control.BOARD_STATUS_UUID]
        callback(ble_control.BOARD_STATUS_UUID, bytearray("".join(bitmap), "ascii"))

    async def write_gatt_char(
        self, uuid: str, payload: bytes, *, response: bool
    ) -> None:
        route = payload.decode("ascii")
        type(self).writes.append((uuid, route, response))
        source, target = {
            "4,0:6.08,0|": ("e1", "g1"),
            "7,0:6.5,0.5:5.5,0.5:4.92,0|": ("h1", "f1"),
        }[route]
        self.occupancy.remove(source)
        self.occupancy.add(target)
        self.callbacks[ble_control.MOVE_NOTIFY_UUID](
            ble_control.MOVE_NOTIFY_UUID, bytearray(b"OK")
        )
        self._publish_board_state()


class CastlingBleControlTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        FakeBleakClient.initial_occupancy = {"e1", "h1"}
        FakeBleakClient.writes = []

    async def test_castling_sends_king_then_confirmed_rook_route(self) -> None:
        with patch.dict(sys.modules, {"bleak": SimpleNamespace(BleakClient=FakeBleakClient)}):
            await ble_control.run("fake", "e1", "g1", castle=True)

        self.assertEqual(
            FakeBleakClient.writes,
            [
                (ble_control.MOVE_UUID, "4,0:6.08,0|", True),
                (ble_control.MOVE_UUID, "7,0:6.5,0.5:5.5,0.5:4.92,0|", True),
            ],
        )

    async def test_blocked_castling_sends_no_motor_routes(self) -> None:
        FakeBleakClient.initial_occupancy = {"e1", "f1", "h1"}
        with patch.dict(sys.modules, {"bleak": SimpleNamespace(BleakClient=FakeBleakClient)}):
            with self.assertRaisesRegex(SystemExit, "blocked at f1"):
                await ble_control.run("fake", "e1", "g1", castle=True)

        self.assertEqual(FakeBleakClient.writes, [])


if __name__ == "__main__":
    unittest.main()
