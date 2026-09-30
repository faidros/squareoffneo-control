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

Inspect a device's GATT services with:

```text
python -m styra_neo.ble_scan --address 59140460-88DD-27DA-D0F8-3CE9D4E4609C
```

The public `mrquincle/squareoff` research matches the services found on this
board: write to the Nordic UART RX characteristic and listen for notifications
on TX. It documents move commands such as `xd2d4z` and acknowledgements such as
`12-OK*`.

Listen to raw notifications for 20 seconds while making a move:

```text
python -m styra_neo.ble_scan --address 59140460-88DD-27DA-D0F8-3CE9D4E4609C --listen --timeout 20
```

Observed traffic includes events such as `e2u` (piece lifted from `e2`) and
`e4d` (piece placed on `e4`), plus a 64-character board-state bitmap.

## Next step

Capture notifications and confirm the command format before sending motor
commands. The exact motor sequence can then replace the planner's generic
actions.