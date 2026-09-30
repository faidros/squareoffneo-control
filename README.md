# Styra Neo

Minimal starter for exploring direct control of a Square Off Neo chessboard.

## What is included

- BLE board wrapper stub
- Bleak-based BLE discovery and connection
- Protocol helpers for board command framing
- Coordinate helpers for board-square mapping
- Simple move planner for normal moves and common chess specials

## BLE discovery

Create or use a Python 3.14 virtual environment, install the project, and scan
for nearby boards:

```text
python -m pip install -e .
python -m styra_neo.ble_scan
```

The Square Off Neo currently identified during development is:

- Name: `Square Off Neo - aba`
- Address: `59140460-88DD-27DA-D0F8-3CE9D4E4609C`
- Nordic UART write characteristic: `6e400002-b5a3-f393-e0a9-e50e24dcca9e`
- Nordic UART notify characteristic: `6e400003-b5a3-f393-e0a9-e50e24dcca9e`
- Firmware revision: `3.0.7`
- Hardware revision: `1A1`

Inspect a device's GATT services with:

```text
python -m styra_neo.ble_scan --address 59140460-88DD-27DA-D0F8-3CE9D4E4609C
```

Inspect all Neo GATT characteristics and readable values with:

```text
python -m styra_neo.ble_probe
```

The Neo exposes a Nordic UART service, but its motorized moves use a separate
characteristic. The older `mrquincle/squareoff` protocol describes commands
such as `xd2d4z`; the Neo-specific
[protocol notes](https://github.com/karlic/MikoNeoDriver/blob/main/Documentation/MikoNeoBoardProtocol.md)
send raw coordinate routes to `f9664d70-93ff-4cfe-9bfe-b5866aa5bef2` and
receive move acknowledgements on `4496994f-2600-4e7e-81d5-e0f7b67ebd48`.
For example, `d2` to `d4` is sent as `3,1:3,2.92|`.

Listen to raw notifications for 20 seconds while making a move:

```text
python -m styra_neo.ble_scan --address 59140460-88DD-27DA-D0F8-3CE9D4E4609C --listen --timeout 20
```

Observed traffic includes events such as `e2u` (piece lifted from `e2`) and
`e4d` (piece placed on `e4`), plus a 64-character board-state bitmap.
A live capture during a physical `e2`-to-`e4` move produced `e2u` followed by
`e4d`, and the move-event parser correctly reported `e2 -> e4`.

To send one direct motor move:

```text
./.venv314/bin/python -m styra_neo.ble_control d2 d4
```

Verified on the connected board: this route returned `OK`, and the board
occupancy changed from `d2` occupied / `d4` empty to `d2` empty / `d4`
occupied.

The live occupancy preflight was also verified with `a2` to `a3`: it read the
board bitmap, sent `0,1:0,1.92|`, received `OK`, and the bitmap changed from
`a2` occupied to `a3` occupied. When the requested source square was empty, the
CLI refused to send a motor route.

The live preflight also refused `a1` to `a4` because `a3` was occupied. A
knight route from `b1` to `c3` was accepted with `OK`, and the bitmap changed
from `b1` occupied to `c3` occupied.

## Next step

`NeoMotorRoutePlanner` plans clear straight routes and routes knights around
occupied squares. It rejects captures, castling, and promotion until their
physical piece-parking and sequencing behavior is known. The BLE command now
requires a live board-state bitmap before sending a route. Next, connect this
Neo-specific transport and route planner to `NeoController`.
